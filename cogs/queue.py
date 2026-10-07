import os
import re
import asyncio

import discord

from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()


# ==========================================
# CONFIG
# ==========================================

QUEUE_CHANNEL_ID = int(
    os.getenv("QUEUE_CHANNEL_ID", 0)
)

NOTED_CATEGORY_ID = int(
    os.getenv("NOTED_CATEGORY_ID", 0)
)

PROCESSING_CATEGORY_ID = int(
    os.getenv("PROCESSING_CATEGORY_ID", 0)
)

COMPLETED_CATEGORY_ID = int(
    os.getenv("COMPLETED_CATEGORY_ID", 0)
)

CANCELLED_CATEGORY_ID = int(
    os.getenv("CANCELLED_CATEGORY_ID", 0)
)


# ==========================================
# STAFF ROLE
# ==========================================

STAFF_ROLE_ID = int(
    os.getenv("STAFF_ROLE_ID", 0)
)


# ==========================================
# CONSTANTS
# ==========================================

STATUS_TEXT = {
    "processing": "PROCESSING",
    "completed": "COMPLETED",
    "cancelled": "CANCELLED",
}


CATEGORY_IDS = {
    "noted": NOTED_CATEGORY_ID,
    "processing": PROCESSING_CATEGORY_ID,
    "completed": COMPLETED_CATEGORY_ID,
    "cancelled": CANCELLED_CATEGORY_ID,
}


# ==========================================
# STATUS MESSAGES
# ==========================================

STATUS_MESSAGES = {

    "processing": (
        "_ _\n"
        "            <a:002_PixelSprout:1531673663600853113>     ~~                     ~~   <a:ise_a2:1531670472155070465>    ~~                     ~~   <a:004_2_carrot:1531669152199213269>\n"
        "         noted                   processing             completed\n"
        "\n"
        "_ _         your [order](https://discord.com/channels/1412690271296163963/1551245952063377408) is being processed. no refunds\n"
        "_ _         once we're processing your order. thank uu\n"
        "_ _         for more [inquiries](https://discord.com/channels/1412690271296163963/1444282982746554378) ping the <@&1442868959245504735> and\n"
        "_ _         wait for our response.\n"
        "\n"
        "_ _"
    ),

    "completed": (
        "_ _\n"
        "            <a:002_PixelSprout:1531673663600853113>     ~~                     ~~   <a:002_PixelSprout:1531673663600853113>     ~~                     ~~   <a:ise_a2:1531670472155070465>\n"
        "         noted                   processing             completed\n"
        "\n"
        "_ _         kiwi delivered your order! <@&1412724532623441941> kindly\n"
        "_ _         [vouch](https://discord.com/channels/1412690271296163963/1444005812828901498) us and also leave a [feedback](https://discord.com/channels/1412690271296163963/1522878467979477032) here. ty\n"
        "_ _         for ordering @ noraneko ! see u in your next\n"
        "_ _         purchase.\n"
        "\n"
        "_ _"
    ),

    "cancelled": (
        "_ _\n"
        "_ _            order is cancelled.  <a:66cdf480:1531685109055361064>\n"
        "_ _"
    ),
}


# ==========================================
# GET CATEGORY
# ==========================================

async def get_category(
    bot: commands.Bot,
    category_id: int
):

    if not category_id:

        return None, (
            "Category ID is not configured.\n"
            f"ID: `{category_id}`"
        )


    category = bot.get_channel(
        category_id
    )


    if category is None:

        try:

            category = await bot.fetch_channel(
                category_id
            )

        except discord.NotFound:

            return None, (
                "Category does not exist.\n"
                f"ID: `{category_id}`"
            )

        except discord.Forbidden:

            return None, (
                "I don't have permission to "
                "access that category."
            )

        except discord.HTTPException as e:

            return None, (
                "Failed to access category:\n"
                f"`{e}`"
            )


    if not isinstance(
        category,
        discord.CategoryChannel
    ):

        return None, (
            f"`{category_id}` is not a category."
        )


    return category, None


# ==========================================
# GET TEXT CHANNEL
# ==========================================

async def get_text_channel(
    bot: commands.Bot,
    channel_id: int
):

    if not channel_id:

        return None, (
            "Channel ID is not configured."
        )


    channel = bot.get_channel(
        channel_id
    )


    if channel is not None:

        if isinstance(
            channel,
            discord.TextChannel
        ):

            return channel, None


        return None, (
            f"`{channel_id}` is not a text channel."
        )


    try:

        channel = await bot.fetch_channel(
            channel_id
        )

    except discord.NotFound:

        return None, (
            "The channel no longer exists."
        )

    except discord.Forbidden:

        return None, (
            "I don't have permission to access "
            "that channel."
        )

    except discord.HTTPException as e:

        return None, (
            "Discord API error:\n"
            f"`{e}`"
        )


    if not isinstance(
        channel,
        discord.TextChannel
    ):

        return None, (
            "The channel is not a text channel."
        )


    return channel, None


# ==========================================
# STAFF CHECK
# ==========================================

def is_staff(
    member: discord.Member
) -> bool:

    # Server owner

    if member.guild.owner_id == member.id:

        return True


    # Administrator

    if member.guild_permissions.administrator:

        return True


    # Staff role

    if STAFF_ROLE_ID:

        return any(
            role.id == STAFF_ROLE_ID
            for role in member.roles
        )


    return False


# ==========================================
# MOVE TICKET CHANNEL
# ==========================================

async def move_ticket_channel(
    bot: commands.Bot,
    ticket: discord.TextChannel,
    status: str,
    quantity: str,
    item: str
):

    category_id = CATEGORY_IDS.get(
        status
    )


    if not category_id:

        return False, (
            f"No category configured for "
            f"`{status}`."
        )


    category, error = await get_category(
        bot,
        category_id
    )


    if category is None:

        return False, error


    channel_name = (
        f"{status}．{quantity}．{item}"
    )


    try:

        await ticket.edit(
            name=channel_name,
            category=category,
            reason=(
                f"Order status changed "
                f"to {status}"
            )
        )


    except discord.Forbidden:

        return False, (
            "I don't have permission to "
            "rename or move the ticket channel.\n\n"
            "Please give the bot **Manage Channels**."
        )


    except discord.HTTPException as e:

        return False, (
            "Discord rejected the channel update:\n"
            f"`{e}`"
        )


    return True, None


# ==========================================
# UPDATE STATUS TEXT
# ==========================================

def update_status_text(
    content: str,
    status: str
) -> str:

    if not content:

        return content


    return re.sub(
        r"(status\s*:\s*\*\*__)(.*?)(__\*\*)",
        rf"\g<1>{status}\g<3>",
        content,
        flags=re.IGNORECASE
    )


# ==========================================
# STATUS BUTTON
# ==========================================

class QueueStatusButton(
    discord.ui.Button
):

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


        if not isinstance(
            view,
            QueueView
        ):

            await interaction.response.send_message(
                "❌ Queue controls are unavailable.",
                ephemeral=True
            )

            return


        # ==================================
        # STAFF CHECK
        # ==================================

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )

            return


        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ You do not have permission to "
                "change order statuses.",
                ephemeral=True
            )

            return


        await view.handle_status(
            interaction,
            self.status
        )


# ==========================================
# VIEW QUEUE BUTTON
# ==========================================

class ViewQueueButton(
    discord.ui.Button
):

    def __init__(
        self,
        url: str
    ):

        super().__init__(
            label="view order",
            style=discord.ButtonStyle.link,
            url=url
        )


# ==========================================
# QUEUE VIEW
# ==========================================

class QueueView(
    discord.ui.View
):

    def __init__(
        self,
        ticket_channel_id: int,
        quantity: str,
        item: str,
        customer_id: int
    ):

        super().__init__(
            timeout=None
        )


        self.ticket_channel_id = (
            ticket_channel_id
        )

        self.quantity = quantity
        self.item = item
        self.customer_id = customer_id


        # Prevent double-clicks

        self.processing_status = False


        # ==================================
        # PROCESSING
        # ==================================

        self.add_item(
            QueueStatusButton(
                status="processing",
                label="processing"
            )
        )


        # ==================================
        # COMPLETED
        # ==================================

        self.add_item(
            QueueStatusButton(
                status="completed",
                label="completed"
            )
        )


        # ==================================
        # CANCELLED
        # ==================================

        self.add_item(
            QueueStatusButton(
                status="cancelled",
                label="cancelled"
            )
        )


    # ==========================================
    # HANDLE STATUS
    # ==========================================

    async def handle_status(
        self,
        interaction: discord.Interaction,
        status: str
    ):

        print(
            f"[QUEUE] Status selected: "
            f"{status} | "
            f"user={interaction.user} | "
            f"id={interaction.user.id}"
        )


        # ==================================
        # PREVENT DOUBLE CLICK
        # ==================================

        if self.processing_status:

            await interaction.response.send_message(
                "⚠️ This order is already being updated.",
                ephemeral=True
            )

            return


        self.processing_status = True


        # ==================================
        # ACKNOWLEDGE IMMEDIATELY
        # ==================================

        try:

            await interaction.response.defer(
                ephemeral=True
            )

        except discord.HTTPException:

            self.processing_status = False

            return


        try:

            # ==================================
            # GET TICKET
            # ==================================

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


            # ==================================
            # MOVE TICKET
            # ==================================

            success, error = (
                await move_ticket_channel(
                    interaction.client,
                    ticket,
                    status,
                    self.quantity,
                    self.item
                )
            )


            if not success:

                await interaction.followup.send(
                    "❌ Failed to move ticket.\n\n"
                    f"{error}",
                    ephemeral=True
                )

                return


            # ==================================
            # CREATE STATUS MESSAGE
            # ==================================

            if status == "cancelled":

                customer_mention = (
                    f"<@{self.customer_id}>"
                )


                message = (
                    "_ _\n"
                    "_ _            order is cancelled.  "
                    "<a:66cdf480:1531685109055361064>\n"
                    f"_ _          丶 {customer_mention}\n"
                    "\n"
                    "_ _"
                )


            else:

                message = STATUS_MESSAGES.get(
                    status,
                    "Order status updated."
                )


            # ==================================
            # SEND STATUS TO TICKET
            # ==================================

            await ticket.send(
                message
            )


            # ==================================
            # UPDATE QUEUE MESSAGE
            # ==================================

            queue_message = (
                interaction.message
            )


            if queue_message:

                content = (
                    queue_message.content
                )


                # ==================================
                # UPDATE STATUS TEXT
                # ==================================

                content = update_status_text(
                    content,
                    status
                )


                # ==================================
                # COMPLETED / CANCELLED
                # ==================================

                if status in (
                    "completed",
                    "cancelled"
                ):

                    await queue_message.edit(
                        content=content,
                        view=None
                    )


                # ==================================
                # PROCESSING
                # ==================================

                else:

                    await queue_message.edit(
                        content=content,
                        view=self
                    )


            # ==================================
            # SUCCESS
            # ==================================

            new_status = STATUS_TEXT.get(
                status,
                status.upper()
            )


            await interaction.followup.send(
                f"status changed to "
                f"**{new_status}**.\n"
                f"ticket moved to "
                f"**{ticket.name}**.",
                ephemeral=True
            )


        # ==================================
        # FORBIDDEN
        # ==================================

        except discord.Forbidden as e:

            print(
                f"[QUEUE ERROR - FORBIDDEN] "
                f"{e}"
            )


            try:

                await interaction.followup.send(
                    "❌ Discord denied the bot's action.\n"
                    "Please check the bot's permissions.",
                    ephemeral=True
                )

            except discord.HTTPException:

                pass


        # ==================================
        # HTTP ERROR
        # ==================================

        except discord.HTTPException as e:

            print(
                f"[QUEUE ERROR - HTTP] "
                f"{e}"
            )


            try:

                await interaction.followup.send(
                    "❌ Discord API error:\n"
                    f"`{e}`",
                    ephemeral=True
                )

            except discord.HTTPException:

                pass


        # ==================================
        # UNKNOWN ERROR
        # ==================================

        except Exception as e:

            print(
                f"[QUEUE ERROR] "
                f"{type(e).__name__}: {e}"
            )


            try:

                await interaction.followup.send(
                    "❌ Something went wrong:\n"
                    f"`{type(e).__name__}: {e}`",
                    ephemeral=True
                )

            except discord.HTTPException:

                pass


        finally:

            self.processing_status = False


# ==========================================
# QUEUE COG
# ==========================================

class Queue(
    commands.Cog
):

    def __init__(
        self,
        bot: commands.Bot
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
        amount: int,
        quantity: str,
        item: str,
        mop: str
    ):

        # ==================================
        # ACKNOWLEDGE IMMEDIATELY
        # ==================================

        await interaction.response.defer()


        # ==================================
        # ORIGINAL TICKET
        # ==================================

        ticket_channel = (
            interaction.channel
        )


        if not isinstance(
            ticket_channel,
            discord.TextChannel
        ):

            await interaction.followup.send(
                "❌ This command must be used "
                "inside a text channel.",
                ephemeral=True
            )

            return


        ticket_channel_id = (
            ticket_channel.id
        )


        # ==================================
        # GET QUEUE CHANNEL
        # ==================================

        queue_channel, error = (
            await get_text_channel(
                self.bot,
                QUEUE_CHANNEL_ID
            )
        )


        if queue_channel is None:

            await interaction.followup.send(
                "❌ Failed to access "
                "queue channel.\n\n"
                f"{error}",
                ephemeral=True
            )

            return


        # ==================================
        # GET NOTED CATEGORY
        # ==================================

        noted_category, error = (
            await get_category(
                self.bot,
                NOTED_CATEGORY_ID
            )
        )


        if noted_category is None:

            await interaction.followup.send(
                "❌ Failed to access "
                "Noted category.\n\n"
                f"{error}",
                ephemeral=True
            )

            return


        # ==================================
        # MOVE TICKET TO NOTED
        # ==================================

        try:

            await ticket_channel.edit(
                name=(
                    f"noted．"
                    f"{quantity}．"
                    f"{item}"
                ),
                category=noted_category,
                reason="New order queued"
            )


        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission "
                "to rename or move the "
                "ticket channel.",
                ephemeral=True
            )

            return


        except discord.HTTPException as e:

            await interaction.followup.send(
                "❌ Failed to move "
                "ticket channel:\n"
                f"`{e}`",
                ephemeral=True
            )

            return


        # ==================================
        # CREATE QUEUE VIEW
        # ==================================

        view = QueueView(
            ticket_channel_id=(
                ticket_channel_id
            ),
            quantity=quantity,
            item=item,
            customer_id=user.id
        )


        # ==================================
        # QUEUE MESSAGE
        # ==================================

        queue_content = (
            "_ _\n"
            f"　　　　 ฅ  　 "
            f"<#{ticket_channel_id}> \n"
            f"　　　　 [ {quantity} ] 　"
            f"{item} \n"
            f"　　　　 via  {mop} — "
            f"**₱ {amount}.00** \n"
            f"　　　　 丶 status : "
            f"**__noted__** \n"
            f"　　　　"
            f"<a:001_appletv:1531665532015611935>"
            f"  :  {user.mention} \n"
            "\n"
            "_ _"
        )


        # ==================================
        # SEND QUEUE MESSAGE
        # ==================================

        try:

            await queue_channel.send(
                content=queue_content,
                view=view
            )


        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I found the queue channel, "
                "but I don't have permission "
                "to send messages there.",
                ephemeral=True
            )

            return


        except discord.HTTPException as e:

            await interaction.followup.send(
                "❌ Discord rejected the "
                "queue message:\n"
                f"`{e}`",
                ephemeral=True
            )

            return


        # ==================================
        # CREATE VIEW QUEUE LINK
        # ==================================

        queue_url = (
            f"https://discord.com/channels/"
            f"{interaction.guild.id}/"
            f"{QUEUE_CHANNEL_ID}"
        )


        confirmation_view = discord.ui.View(
            timeout=None
        )


        confirmation_view.add_item(
            ViewQueueButton(
                queue_url
            )
        )


        # ==================================
        # CONFIRMATION
        # ==================================

        await interaction.followup.send(
            (
                "_ _\n"
                "_ _           kiwi noted ur order.  "
                "<a:f_inouestrawberry:1557076560391962744>\n"
                f"_ _          丶 {user.mention}\n"
                "_ _"
            ),
            view=confirmation_view
        )


# ==========================================
# SETUP
# ==========================================

async def setup(
    bot: commands.Bot
):

    await bot.add_cog(
        Queue(bot)
    )