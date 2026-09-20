import os
import re
import discord

from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv


# ==========================================
# LOAD ENV
# ==========================================

load_dotenv()


# ==========================================
# CONFIG
# ==========================================

QUEUE_CHANNEL_ID = int(os.getenv("QUEUE_CHANNEL_ID"))

NOTED_CATEGORY_ID = int(os.getenv("NOTED_CATEGORY_ID"))
PROCESSING_CATEGORY_ID = int(os.getenv("PROCESSING_CATEGORY_ID"))
COMPLETED_CATEGORY_ID = int(os.getenv("COMPLETED_CATEGORY_ID"))
CANCELLED_CATEGORY_ID = int(os.getenv("CANCELLED_CATEGORY_ID"))


# ==========================================
# EMOJIS
# ==========================================

EMOJI_PROCESSING = discord.PartialEmoji(
    name="green",
    id=1528664601216946266
)

EMOJI_COMPLETED = discord.PartialEmoji(
    name="green",
    id=1528664601216946266
)

EMOJI_CANCELLED = discord.PartialEmoji(
    name="green",
    id=1528664601216946266
)


# ==========================================
# STATUS CONFIG
# ==========================================

STATUS_CONFIG = {

    "processing": {
        # "channel_name": f"processing．{quantity}．{item}",
        "category_id": PROCESSING_CATEGORY_ID,
        "message": "⚙️ Your order is now **processing**."
    },

    "completed": {
        # "channel_name": f"completed．{quantity}．{item}",
        "category_id": COMPLETED_CATEGORY_ID,
        "message": "✅ Your order has been **completed**."
    },

    "cancelled": {
        # "channel_name": f"cancelled．{quantity}．{item}",
        "category_id": CANCELLED_CATEGORY_ID,
        "message": "❌ Your order has been **cancelled**."
    }
}


# ==========================================
# MOVE TICKET CHANNEL
# ==========================================

async def move_ticket_channel(
    bot,
    ticket,
    status,
    quantity,
    item
):

    config = STATUS_CONFIG.get(status)

    if config is None:
        return False, "Invalid status."

    # ======================================
    # CREATE CHANNEL NAME
    # ======================================

    channel_name = (
        f"{status}．{quantity}．{item}"
    )

    # ======================================
    # GET CATEGORY
    # ======================================

    category = bot.get_channel(
        config["category_id"]
    )

    if category is None:

        try:

            category = await bot.fetch_channel(
                config["category_id"]
            )

        except discord.NotFound:

            return False, (
                f"Category does not exist.\n"
                f"Category ID: `{config['category_id']}`"
            )

        except discord.Forbidden:

            return False, (
                "I don't have permission to access "
                "that category."
            )

        except discord.HTTPException as e:

            return False, (
                f"Failed to access category: `{e}`"
            )

    # ======================================
    # CHECK CATEGORY
    # ======================================

    if not isinstance(
        category,
        discord.CategoryChannel
    ):

        return False, (
            f"`{config['category_id']}` is not a category."
        )

    # ======================================
    # MOVE + RENAME TICKET
    # ======================================

    try:

        await ticket.edit(
            name=config["channel_name"],
            category=category,
            reason=f"Order status changed to {status}"
        )

    except discord.Forbidden:

        return False, (
            "I don't have permission to rename "
            "or move the ticket channel.\n"
            "Please give me **Manage Channels** permission."
        )

    except discord.HTTPException as e:

        return False, (
            f"Discord rejected the channel update: `{e}`"
        )

    return True, None


# ==========================================
# STATUS DROPDOWN
# ==========================================

class QueueStatusSelection(discord.ui.Select):

    def __init__(
            self, 
            ticket_channel_id,
            quantity,
            item
        ):

        self.ticket_channel_id = ticket_channel_id
        self.quantity = quantity
        self.item = item

        options = [

            discord.SelectOption(
                label="toma is processing your order",
                value="processing",
                emoji=EMOJI_PROCESSING
            ),

            discord.SelectOption(
                label="toma completed your order",
                value="completed",
                emoji=EMOJI_COMPLETED
            ),

            discord.SelectOption(
                label="toma cancelled the transaction",
                value="cancelled",
                emoji=EMOJI_CANCELLED
            )
        ]

        super().__init__(
            placeholder="ONLY MEOWZ!",
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        # ======================================
        # ACKNOWLEDGE DROPDOWN
        # ======================================

        await interaction.response.defer(
            ephemeral=True
        )

        status = self.values[0]

        # ======================================
        # STATUS TEXT
        # ======================================

        status_text = {
            "processing": "PROCESSING",
            "completed": "COMPLETED",
            "cancelled": "CANCELLED"
        }

        new_status = status_text.get(
            status,
            status.upper()
        )

        # ======================================
        # GET QUEUE EMBED
        # ======================================

        if not interaction.message.embeds:

            await interaction.followup.send(
                "❌ No queue embed found.",
                ephemeral=True
            )

            return

        embed = interaction.message.embeds[0]

        # ======================================
        # UPDATE STATUS IN DESCRIPTION
        # ======================================

        if embed.description:

            new_description = re.sub(
                r"STATUS\s*:\s*\**\s*[A-Za-z_]+\s*\**",
                f"STATUS: {new_status}",
                embed.description,
                count=1,
                flags=re.IGNORECASE
            )

            embed.description = new_description

        # ======================================
        # UPDATE QUEUE MESSAGE
        # ======================================

        try:

            await interaction.message.edit(
                embed=embed,
                view=self.view
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission to edit the queue message.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            await interaction.followup.send(
                f"❌ Failed to update queue message: `{e}`",
                ephemeral=True
            )

            return

        # ======================================
        # GET ORIGINAL TICKET
        # ======================================

        ticket = interaction.client.get_channel(
            self.ticket_channel_id
        )

        if ticket is None:

            try:

                ticket = await interaction.client.fetch_channel(
                    self.ticket_channel_id
                )

            except discord.NotFound:

                await interaction.followup.send(
                    "⚠️ Status updated, but the original ticket channel no longer exists.",
                    ephemeral=True
                )

                return

            except discord.Forbidden:

                await interaction.followup.send(
                    "⚠️ Status updated, but I don't have permission to access the ticket channel.",
                    ephemeral=True
                )

                return

            except discord.HTTPException as e:

                await interaction.followup.send(
                    f"⚠️ Status updated, but I failed to access the ticket channel: `{e}`",
                    ephemeral=True
                )

                return

        # ======================================
        # MOVE ORIGINAL TICKET
        # ======================================

        success, error = await move_ticket_channel(
            interaction.client,
            ticket,
            status,
            self.quantity,
            self.item
        )

        if not success:

            await interaction.followup.send(
                f"⚠️ Queue status was updated to **{new_status}**, "
                f"but the ticket could not be moved.\n\n"
                f"{error}",
                ephemeral=True
            )

            return

        # ======================================
        # SEND STATUS MESSAGE IN TICKET
        # ======================================

        try:

            await ticket.send(
                STATUS_CONFIG[status]["message"]
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "⚠️ Ticket was moved, but I can't send messages in the ticket.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            await interaction.followup.send(
                f"⚠️ Ticket was moved, but the status message failed: `{e}`",
                ephemeral=True
            )

            return

        # ======================================
        # CONFIRM
        # ======================================

        await interaction.followup.send(
            f"✅ Status changed to **{new_status}**.\n"
            f"📁 Ticket moved to **"
            f"{STATUS_CONFIG[status]['channel_name']}**.",
            ephemeral=True
        )


# ==========================================
# QUEUE VIEW
# ==========================================

class QueueView(discord.ui.View):

    def __init__(
        self,
        ticket_channel_id,
        quantity,
        item
    ):

        super().__init__(
            timeout=None
        )

        self.add_item(
            QueueStatusSelection(
                ticket_channel_id,
                quantity,
                item
            )
        )


# ==========================================
# QUEUE COG
# ==========================================

class Queue(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # ======================================
    # /QUEUE
    # ======================================

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
        amount: float,
        quantity: str,
        item: str,
        mop: str
    ):

        # ======================================
        # ORIGINAL TICKET CHANNEL
        # ======================================

        ticket_channel = interaction.channel

        if ticket_channel is None:

            await interaction.response.send_message(
                "❌ Ticket channel could not be found.",
                ephemeral=True
            )

            return

        ticket_channel_id = ticket_channel.id

        # ======================================
        # GET QUEUE CHANNEL
        # ======================================

        queue_channel = self.bot.get_channel(
            QUEUE_CHANNEL_ID
        )

        if queue_channel is None:

            try:

                queue_channel = await self.bot.fetch_channel(
                    QUEUE_CHANNEL_ID
                )

            except discord.NotFound:

                await interaction.response.send_message(
                    f"❌ Queue channel does not exist.\n"
                    f"ID: `{QUEUE_CHANNEL_ID}`",
                    ephemeral=True
                )

                return

            except discord.Forbidden:

                await interaction.response.send_message(
                    "❌ I don't have permission to access the queue channel.",
                    ephemeral=True
                )

                return

            except discord.HTTPException as e:

                await interaction.response.send_message(
                    f"❌ Failed to access queue channel: `{e}`",
                    ephemeral=True
                )

                return

        # ======================================
        # CHECK QUEUE CHANNEL TYPE
        # ======================================

        if not isinstance(
            queue_channel,
            discord.TextChannel
        ):

            await interaction.response.send_message(
                f"❌ QUEUE_CHANNEL_ID is not a text channel.\n"
                f"ID: `{QUEUE_CHANNEL_ID}`",
                ephemeral=True
            )

            return

        # ======================================
        # GET NOTED CATEGORY
        # ======================================

        noted_category = self.bot.get_channel(
            NOTED_CATEGORY_ID
        )

        if noted_category is None:

            try:

                noted_category = await self.bot.fetch_channel(
                    NOTED_CATEGORY_ID
                )

            except discord.NotFound:

                await interaction.response.send_message(
                    f"❌ Noted category does not exist.\n"
                    f"ID: `{NOTED_CATEGORY_ID}`",
                    ephemeral=True
                )

                return

            except discord.Forbidden:

                await interaction.response.send_message(
                    "❌ I don't have permission to access the Noted category.",
                    ephemeral=True
                )

                return

            except discord.HTTPException as e:

                await interaction.response.send_message(
                    f"❌ Failed to access Noted category: `{e}`",
                    ephemeral=True
                )

                return

        # ======================================
        # CHECK NOTED CATEGORY
        # ======================================

        if not isinstance(
            noted_category,
            discord.CategoryChannel
        ):

            await interaction.response.send_message(
                f"NOTED_CATEGORY_ID is not a category.\n"
                f"ID: `{NOTED_CATEGORY_ID}`",
                ephemeral=True
            )

            return

        # ======================================
        # MOVE TICKET TO NOTED
        # ======================================

        try:

            await ticket_channel.edit(
                name=f"noted．{quantity}．{item}",
                category=noted_category,
                reason="New order queued"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "I don't have permission to rename "
                "or move the ticket channel.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            await interaction.response.send_message(
                f"Failed to move ticket channel: `{e}`",
                ephemeral=True
            )

            return

        # ======================================
        # CREATE QUEUE EMBED
        # ======================================

        embed = discord.Embed(
            description=(
                "_ _\n"
                "\n"
                "_ _　　    　　　　<:apple_folder:1531585484256444567>   **TOMA GOT AN ORDER!** 　　　　　 　　\n"
                f"_ _　　   　 　　　╰     <#{ticket_channel_id}>    𐔌 \n"
                f"_ _　　    　　　　{quantity}   - [ {item} ]  <:003_orangeslice:1531666035139280970>  \n"
                f"_ _　　   　 　　　paid via {mop} : ₱`{amount}` \n"
                f"_ _　　　　　　ⓘ　　~~　~~　　{interaction.user.mention}  \n"
                "\n"
                "_ _　　　　　　　( ?  **STATUS: NOTED**) \n"
                "\n"
                "_ _"
            ),
        )

        # ======================================
        # SEND TO QUEUE CHANNEL
        # ======================================

        try:

            await queue_channel.send(
                content=(
                    " _ _ "
                    " _ _ \n "
                    f" _ _  ⓘ   {user.mention}   ordered  something !   \n "
                    " _ _ "
                ),
                embed=embed,
                view=QueueView(
                    ticket_channel_id,
                    quantity,
                    item
                )
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "I found the queue channel, but I don't have permission to send messages there.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            await interaction.response.send_message(
                f"Discord rejected the queue message: `{e}`",
                ephemeral=True
            )

            return

        # ======================================
        # SUCCESS
        # ======================================

        await interaction.response.send_message(
            "Order added to the queue.",
            ephemeral=True
        )


# ==========================================
# SETUP
# ==========================================

async def setup(bot):

    await bot.add_cog(
        Queue(bot)
    )