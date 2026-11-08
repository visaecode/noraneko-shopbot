
import os
import re
import json
import sqlite3
import asyncio

import discord

from pathlib import Path
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv


load_dotenv()

QUEUE_CHANNEL_ID = int(os.getenv("QUEUE_CHANNEL_ID", 0))
NOTED_CATEGORY_ID = int(os.getenv("NOTED_CATEGORY_ID", 0))
PROCESSING_CATEGORY_ID = int(os.getenv("PROCESSING_CATEGORY_ID", 0))
COMPLETED_CATEGORY_ID = int(os.getenv("COMPLETED_CATEGORY_ID", 0))
CANCELLED_CATEGORY_ID = int(os.getenv("CANCELLED_CATEGORY_ID", 0))

STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", 0))


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
MESSAGE_DIR = BASE_DIR / "messages"

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "queue.db"
MESSAGE_PATH = MESSAGE_DIR / "queue_messages.json"

STATUS_TEXT = {
    "noted": "NOTED",
    "processing": "PROCESSING",
    "completed": "COMPLETED",
    "cancelled": "CANCELLED"
}

CATEGORY_IDS = {
    "noted": NOTED_CATEGORY_ID,
    "processing": PROCESSING_CATEGORY_ID,
    "completed": COMPLETED_CATEGORY_ID,
    "cancelled": CANCELLED_CATEGORY_ID
}

with open(MESSAGE_PATH, "r", encoding="utf-8") as file:
    MESSAGES = json.load(file)


def get_message(key: str, **kwargs) -> str:
    return MESSAGES[key].format(**kwargs)

def init_database():

    with sqlite3.connect(DB_PATH) as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                queue_message_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                ticket_channel_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                quantity TEXT NOT NULL,
                item TEXT NOT NULL,
                amount INTEGER NOT NULL,
                mop TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'noted',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.commit()


def save_order(
    queue_message_id: int,
    guild_id: int,
    ticket_channel_id: int,
    customer_id: int,
    quantity: str,
    item: str,
    amount: int,
    mop: str
):

    with sqlite3.connect(DB_PATH) as db:

        db.execute("""
            INSERT INTO orders (
                queue_message_id,
                guild_id,
                ticket_channel_id,
                customer_id,
                quantity,
                item,
                amount,
                mop,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'noted')
        """, (
            queue_message_id,
            guild_id,
            ticket_channel_id,
            customer_id,
            quantity,
            item,
            amount,
            mop
        ))

        db.commit()


def update_order_status(
    queue_message_id: int,
    status: str
):

    with sqlite3.connect(DB_PATH) as db:

        cursor = db.execute("""
            UPDATE orders
            SET status = ?
            WHERE queue_message_id = ?
        """, (
            status,
            queue_message_id
        ))

        db.commit()
        return cursor.rowcount > 0


def get_saved_orders():
    with sqlite3.connect(DB_PATH) as db:

        db.row_factory = sqlite3.Row

        return db.execute("""
            SELECT *
            FROM orders
            ORDER BY created_at ASC
        """).fetchall()
    
async def get_category(
    bot: commands.Bot,
    category_id: int
):

    if not category_id:
        return None, "Category ID is not configured."

    category = bot.get_channel(category_id)

    if category is None:

        try:
            category = await bot.fetch_channel(category_id)

        except discord.NotFound:
            return None, "Category does not exist."

        except discord.Forbidden:
            return None, "I don't have permission to access that category."

        except discord.HTTPException as e:
            return None, f"Discord API error: {e}"

    if not isinstance(category, discord.CategoryChannel):
        return None, "The specified ID is not a category."

    return category, None

async def get_text_channel(
    bot: commands.Bot,
    channel_id: int
):

    if not channel_id:
        return None, "Channel ID is not configured."

    channel = bot.get_channel(channel_id)

    if channel is not None:

        if isinstance(channel, discord.TextChannel):
            return channel, None

        return None, "The specified ID is not a text channel."

    try:
        channel = await bot.fetch_channel(channel_id)

    except discord.NotFound:
        return None, "The channel no longer exists."

    except discord.Forbidden:
        return None, "I don't have permission to access that channel."

    except discord.HTTPException as e:
        return None, f"Discord API error: {e}"

    if not isinstance(channel, discord.TextChannel):
        return None, "The channel is not a text channel."

    return channel, None

def is_staff(member: discord.Member) -> bool:

    if member.guild.owner_id == member.id:
        return True

    if member.guild_permissions.administrator:
        return True

    if STAFF_ROLE_ID:
        return any(
            role.id == STAFF_ROLE_ID
            for role in member.roles
        )

    return False

async def move_ticket_channel(
    bot: commands.Bot,
    ticket: discord.TextChannel,
    status: str,
    quantity: str,
    item: str
):

    category_id = CATEGORY_IDS.get(status)

    if not category_id:
        return False, f"No category configured for {status}."

    category, error = await get_category(
        bot,
        category_id
    )

    if category is None:
        return False, error

    channel_name = f"{status}．{quantity}．{item}"

    try:

        await ticket.edit(
            name=channel_name[:100],
            category=category,
            reason=f"Order status changed to {status}"
        )

    except discord.Forbidden:

        return False, (
            "I don't have permission to rename or move "
            "the ticket channel.\n"
            "Please give the bot Manage Channels."
        )

    except discord.HTTPException as e:

        return False, f"Discord API error: {e}"

    return True, None

def update_status_text(
    content: str,
    status: str
) -> str:

    return re.sub(
        r"(status\s*:\s*\*\*__).*?(__\*\*)",
        lambda match: (
            f"{match.group(1)}{status}{match.group(2)}"
        ),
        content,
        count=1,
        flags=re.IGNORECASE
    )

class QueueStatusButton(discord.ui.Button):

    def __init__(
        self,
        status: str,
        label: str
    ):

        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            custom_id=f"queue_status_{status}"
        )

        self.status = status

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        view = self.view

        if not isinstance(view, QueueView):

            await interaction.response.send_message(
                "❌ Queue controls are unavailable.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.user, discord.Member):

            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                MESSAGES["errors"]["not_staff"],
                ephemeral=True
            )
            return

        await view.handle_status(
            interaction,
            self.status
        )

class ViewQueueButton(discord.ui.Button):

    def __init__(self, url: str):

        super().__init__(
            label="view order",
            style=discord.ButtonStyle.link,
            url=url
        )

class QueueView(discord.ui.View):

    def __init__(
        self,
        ticket_channel_id: int,
        quantity: str,
        item: str,
        customer_id: int,
        queue_message_id: int = None,
        status: str = "noted"
    ):

        super().__init__(timeout=None)

        self.ticket_channel_id = ticket_channel_id
        self.quantity = quantity
        self.item = item
        self.customer_id = customer_id
        self.queue_message_id = queue_message_id

        self.status = status
        self.processing_status = False

        self.add_item(
            QueueStatusButton(
                "processing",
                "processing"
            )
        )

        self.add_item(
            QueueStatusButton(
                "completed",
                "completed"
            )
        )

        self.add_item(
            QueueStatusButton(
                "cancelled",
                "cancelled"
            )
        )

        # Disable buttons for finalized orders
        if status in ("completed", "cancelled"):

            for button in self.children:
                button.disabled = True

    async def handle_status(
        self,
        interaction: discord.Interaction,
        status: str
    ):

        print(
            f"[QUEUE] Status selected: {status} | "
            f"user={interaction.user} | "
            f"id={interaction.user.id}"
        )

        # Prevent simultaneous updates
        if self.processing_status:

            await interaction.response.send_message(
                MESSAGES["errors"]["already_updating"],
                ephemeral=True
            )
            return

        # Prevent changing finalized orders
        if self.status in ("completed", "cancelled"):

            await interaction.response.send_message(
                MESSAGES["errors"]["already_finalized"],
                ephemeral=True
            )
            return

        self.processing_status = True

        try:

            await interaction.response.defer(
                ephemeral=True
            )

            ticket, error = await get_text_channel(
                interaction.client,
                self.ticket_channel_id
            )

            if ticket is None:

                await interaction.followup.send(
                    f"❌ {error}",
                    ephemeral=True
                )
                return


            success, error = await move_ticket_channel(
                interaction.client,
                ticket,
                status,
                self.quantity,
                self.item
            )

            if not success:

                await interaction.followup.send(
                    f"❌ Failed to move ticket.\n\n{error}",
                    ephemeral=True
                )
                return


            message = get_message(
                status,
                customer=f"<@{self.customer_id}>"
            )

            await ticket.send(message)

            queue_message = interaction.message

            if queue_message is not None:

                content = update_status_text(
                    queue_message.content,
                    status
                )

                # disable buttons 
                if status in ("completed", "cancelled"):

                    for button in self.children:
                        button.disabled = True

                await queue_message.edit(
                    content=content,
                    view=self
                )

            self.status = status

            update_order_status(
                self.queue_message_id,
                status
            )

            new_status = STATUS_TEXT.get(
                status,
                status.upper()
            )

            await interaction.followup.send(
                f"status changed to **{new_status}**.\n"
                f"ticket moved to **{ticket.name}**.",
                ephemeral=True
            )

        except discord.Forbidden as e:

            print(f"[QUEUE ERROR - FORBIDDEN] {e}")

            await interaction.followup.send(
                "❌ Discord denied the bot's action.\n"
                "Please check the bot's permissions.",
                ephemeral=True
            )

        except discord.HTTPException as e:

            print(f"[QUEUE ERROR - HTTP] {e}")

            await interaction.followup.send(
                f"❌ Discord API error:\n`{e}`",
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[QUEUE ERROR] "
                f"{type(e).__name__}: {e}"
            )

            try:

                await interaction.followup.send(
                    f"❌ Something went wrong:\n"
                    f"`{type(e).__name__}: {e}`",
                    ephemeral=True
                )

            except discord.HTTPException:
                pass

        finally:

            self.processing_status = False

class Queue(commands.Cog):

    def __init__(self, bot: commands.Bot):

        self.bot = bot

    @app_commands.command(
        name="queue",
        description="Add an order to the queue."
    )

    @app_commands.describe(
        user="Customer",
        item="Item",
        quantity="Quantity",
        amount="Amount",
        mop="Mode of Payment"
    )

    async def queue(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        quantity: str,
        item: str,
        mop: str
    ):

        await interaction.response.defer()

        if interaction.guild is None:

            await interaction.followup.send(
                "❌ This command must be used in a server.",
                ephemeral=True
            )
            return


        if not isinstance(interaction.user, discord.Member):
            return

        if not is_staff(interaction.user):

            await interaction.followup.send(
                MESSAGES["errors"]["not_staff"],
                ephemeral=True
            )
            return


        ticket_channel = interaction.channel

        if not isinstance(ticket_channel, discord.TextChannel):

            await interaction.followup.send(
                MESSAGES["errors"]["not_text_channel"],
                ephemeral=True
            )
            return

        ticket_channel_id = ticket_channel.id

        queue_channel, error = await get_text_channel(
            self.bot,
            QUEUE_CHANNEL_ID
        )

        if queue_channel is None:

            await interaction.followup.send(
                f"❌ Failed to access queue channel.\n\n{error}",
                ephemeral=True
            )
            return
    
        noted_category, error = await get_category(
            self.bot,
            NOTED_CATEGORY_ID
        )

        if noted_category is None:

            await interaction.followup.send(
                f"❌ Failed to access Noted category.\n\n{error}",
                ephemeral=True
            )
            return
        

        try:

            await ticket_channel.edit(
                name=f"noted．{quantity}．{item}"[:100],
                category=noted_category,
                reason="New order queued"
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission to rename or move the ticket.",
                ephemeral=True
            )
            return

        except discord.HTTPException as e:

            await interaction.followup.send(
                f"❌ Failed to move ticket:\n`{e}`",
                ephemeral=True
            )
            return
        

        view = QueueView(
            ticket_channel_id=ticket_channel_id,
            quantity=quantity,
            item=item,
            customer_id=user.id
        )


        queue_content = get_message(
            "queue",
            ticket_channel_id=ticket_channel_id,
            quantity=quantity,
            item=item,
            mop=mop,
            amount=amount,
            customer=user.mention
        )


        try:

            queue_message = await queue_channel.send(
                content=queue_content,
                view=view
            )

            # Save queue message ID
            view.queue_message_id = queue_message.id

            # Save order in database
            save_order(
                queue_message_id=queue_message.id,
                guild_id=interaction.guild.id,
                ticket_channel_id=ticket_channel_id,
                customer_id=user.id,
                quantity=quantity,
                item=item,
                amount=amount,
                mop=mop
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission to send messages in the queue channel.",
                ephemeral=True
            )
            return

        except (discord.HTTPException, sqlite3.Error) as e:

            print(f"[QUEUE SAVE ERROR] {e}")

            await interaction.followup.send(
                f"❌ Failed to create or save queue order:\n`{e}`",
                ephemeral=True
            )
            return

        # ==================================
        # CREATE VIEW ORDER LINK
        # ==================================

        queue_url = (
            f"https://discord.com/channels/"
            f"{interaction.guild.id}/"
            f"{QUEUE_CHANNEL_ID}/"
            f"{queue_message.id}"
        )

        confirmation_view = discord.ui.View(
            timeout=None
        )

        confirmation_view.add_item(
            ViewQueueButton(queue_url)
        )

        # ==================================
        # CONFIRMATION
        # ==================================

        confirmation = get_message(
            "confirmation",
            customer=user.mention
        )

        await interaction.followup.send(
            confirmation,
            view=confirmation_view
        )


# ==========================================
# RESTORE PERSISTENT VIEWS
# ==========================================

async def restore_queue_views(bot: commands.Bot):

    orders = get_saved_orders()

    restored = 0
    skipped = 0

    for order in orders:

        status = order["status"]

        # Ignore finalized orders
        if status in ("completed", "cancelled"):
            skipped += 1
            continue

        view = QueueView(
            ticket_channel_id=order["ticket_channel_id"],
            quantity=order["quantity"],
            item=order["item"],
            customer_id=order["customer_id"],
            queue_message_id=order["queue_message_id"],
            status=status
        )

        try:

            bot.add_view(
                view,
                message_id=order["queue_message_id"]
            )

            restored += 1

        except Exception as e:

            print(
                f"[QUEUE RESTORE ERROR] "
                f"Message {order['queue_message_id']}: {e}"
            )

    print(
        f"[QUEUE] Restored {restored} active orders. "
        f"Skipped {skipped} finalized orders."
    )


# ==========================================
# SETUP
# ==========================================

async def setup(bot: commands.Bot):

    init_database()

    await bot.add_cog(Queue(bot))

    await restore_queue_views(bot)

    print("[QUEUE] Queue system loaded successfully.")
