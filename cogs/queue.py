import os

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
    name="00001",
    id=1517079490352775239
)

EMOJI_COMPLETED = discord.PartialEmoji(
    name="00002",
    id=1517079538415439963
)

EMOJI_CANCELLED = discord.PartialEmoji(
    name="00003",
    id=1517079582522474608
)


# ==========================================
# STATUS CONFIG
# ==========================================

STATUS_CONFIG = {

    "processing": {

        "category_id": PROCESSING_CATEGORY_ID,

        "message": (
            "_ _\n\n"

            "_ _      <a:002_PixelSprout:1531673663600853113>     ~~                      ~~     "
            "<a:ise_a2:1531670472155070465>    ~~                      ~~   "
            "<a:004_2_carrot:1531669152199213269>\n"

            "_ _   **noted                     processing               completed**\n\n"

            "_ _       your  order  is being processed. no refund once\n"
            "_ _ we're processing your order. do not ping the staffs\n"
            "_ _ for the mean time. the force refund cost : `P30.00`\n"

            ">   pings   :     <@&1412724532623441941>  "
            "<@&1442868959245504735> <@&1412762016753516614>\n\n"

            "_ _"
        )
    },

    "completed": {

        "category_id": COMPLETED_CATEGORY_ID,

        "message": (
            "_ _\n\n"

            "_ _      <a:002_PixelSprout:1531673663600853113>     ~~                      ~~     "
            "<a:002_PixelSprout:1531673663600853113>     ~~                      ~~   "
            "<a:ise_a2:1531670472155070465>\n"

            "_ _   **noted                     processing               completed**\n\n"

            "_ _       your  order  is now completed. please do check\n"
            "_ _ and confirm if you received the item. do not forget\n"

            "_ _ to [vouch](https://discord.com/channels/1412690271296163963/1444005812828901498). "
            "no vouch / incorrect vouch = no warranty\n"

            ">   pings   :     <@&1412724532623441941>  "
            "<@&1442868959245504735> <@&1412762016753516614>\n\n"

            "_ _"
        )
    },

    "cancelled": {

        "category_id": CANCELLED_CATEGORY_ID,

        "message": (
            "_ _\n\n"

            "_ _                           **order is cancelled**      "
            "<a:ise_a1:1531670435635265617>\n\n"

            "_ _       order is cancelled due to circumstances. please\n"
            "_ _       wait for staff to refund your payment and prepare\n"
            "_ _       force refund fee : `P30.00` upfront    thank you sm!\n"

            ">   pings   :     <@&1412724532623441941>  "
            "<@&1442868959245504735> <@&1412762016753516614>\n\n"

            "_ _"
        )
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
    # CHANNEL NAME
    # ======================================

    channel_name = f"{status}．{quantity}．{item}"


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
                f"ID: `{config['category_id']}`"
            )

        except discord.Forbidden:

            return False, (
                "I don't have permission to "
                "access that category."
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
    # MOVE CHANNEL
    # ======================================

    try:

        await ticket.edit(
            name=channel_name,
            category=category,
            reason=f"Order status changed to {status}"
        )

    except discord.Forbidden:

        return False, (
            "I don't have permission to rename "
            "or move the ticket channel.\n\n"
            "Please give the bot **Manage Channels**."
        )

    except discord.HTTPException as e:

        return False, (
            f"Discord rejected the channel update:\n"
            f"`{e}`"
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
                label="．　processing",
                value="processing",
                emoji=EMOJI_PROCESSING
            ),

            discord.SelectOption(
                label="．　completed",
                value="completed",
                emoji=EMOJI_COMPLETED
            ),

            discord.SelectOption(
                label="．　cancelled",
                value="cancelled",
                emoji=EMOJI_CANCELLED
            )
        ]

        super().__init__(
            placeholder="ONLY MEOWZ!",
            min_values=1,
            max_values=1,
            options=options
        )


    # ======================================
    # CALLBACK
    # ======================================

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        try:

            # ==================================
            # GET STATUS
            # ==================================

            status = self.values[0]

            print(
                f"[QUEUE] Selected status: {status}"
            )


            # ==================================
            # STATUS TEXT
            # ==================================

            status_text = {
                "processing": "PROCESSING",
                "completed": "COMPLETED",
                "cancelled": "CANCELLED"
            }

            new_status = status_text.get(
                status,
                status.upper()
            )


            # ==================================
            # IMMEDIATELY ACKNOWLEDGE
            # ==================================

            await interaction.response.defer(
                ephemeral=True
            )


            # ==================================
            # GET QUEUE EMBED
            # ==================================

            if not interaction.message:

                await interaction.followup.send(
                    "❌ Queue message could not be found.",
                    ephemeral=True
                )

                return


            if not interaction.message.embeds:

                await interaction.followup.send(
                    "❌ No queue embed found.",
                    ephemeral=True
                )

                return


            # ==================================
            # UPDATE QUEUE EMBED
            # ==================================

            embed = interaction.message.embeds[0]

            if embed.description:

                description = embed.description

                description = description.replace(
                    "STATUS: NOTED",
                    f"STATUS: {new_status}"
                )

                description = description.replace(
                    "STATUS: PROCESSING",
                    f"STATUS: {new_status}"
                )

                description = description.replace(
                    "STATUS: COMPLETED",
                    f"STATUS: {new_status}"
                )

                description = description.replace(
                    "STATUS: CANCELLED",
                    f"STATUS: {new_status}"
                )

                embed.description = description


            # ==================================
            # GET ORIGINAL TICKET
            # ==================================

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
                        "❌ The ticket channel no longer exists.",
                        ephemeral=True
                    )

                    return

                except discord.Forbidden:

                    await interaction.followup.send(
                        "❌ I don't have permission to access the ticket channel.",
                        ephemeral=True
                    )

                    return

                except discord.HTTPException as e:

                    await interaction.followup.send(
                        f"❌ Failed to access ticket:\n`{e}`",
                        ephemeral=True
                    )

                    return


            # ==================================
            # MOVE TICKET
            # ==================================

            success, error = await move_ticket_channel(
                interaction.client,
                ticket,
                status,
                self.quantity,
                self.item
            )


            if not success:

                await interaction.followup.send(
                    f"❌ Failed to move ticket.\n\n"
                    f"{error}",
                    ephemeral=True
                )

                return

            # ==================================
            # SEND STATUS MESSAGE
            # ==================================

            await ticket.send(
                STATUS_CONFIG[status]["message"]
            )


            # ==================================
            # UPDATE QUEUE MESSAGE
            # ==================================

            if status in ("completed", "cancelled"):
                # REMOVE DROPDOWN
                await interaction.message.edit(
                    embed=embed,
                    view=None
                )
            else:
                # KEEP DROPDOWN FOR PROCESSING
                await interaction.message.edit(
                    embed=embed,
                    view=self.view
                )


            # ==================================
            # SUCCESS
            # ==================================

            await interaction.followup.send(
                f"status changed to **{new_status}**.\n"
                f"ticket moved to **{ticket.name}**.",
                ephemeral=True
            )

        # ======================================
        # ERROR HANDLER
        # ======================================

        except discord.Forbidden as e:

            print(
                f"[QUEUE ERROR - FORBIDDEN] {e}"
            )

            if interaction.response.is_done():

                await interaction.followup.send(
                    "❌ Discord denied the bot's action. "
                    "Check the bot's permissions.",
                    ephemeral=True
                )

            else:

                await interaction.response.send_message(
                    "❌ Discord denied the bot's action. "
                    "Check the bot's permissions.",
                    ephemeral=True
                )


        except discord.HTTPException as e:

            print(
                f"[QUEUE ERROR - HTTP] {e}"
            )

            if interaction.response.is_done():

                await interaction.followup.send(
                    f"❌ Discord API error:\n`{e}`",
                    ephemeral=True
                )

            else:

                await interaction.response.send_message(
                    f"❌ Discord API error:\n`{e}`",
                    ephemeral=True
                )


        except Exception as e:

            print(
                f"[QUEUE ERROR] {type(e).__name__}: {e}"
            )

            if interaction.response.is_done():

                await interaction.followup.send(
                    f"❌ Something went wrong:\n"
                    f"`{type(e).__name__}: {e}`",
                    ephemeral=True
                )

            else:

                await interaction.response.send_message(
                    f"❌ Something went wrong:\n"
                    f"`{type(e).__name__}: {e}`",
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
        amount: int,
        quantity: str,
        item: str,
        mop: str
    ):

        # ==================================
        # ORIGINAL TICKET
        # ==================================

        ticket_channel = interaction.channel

        if ticket_channel is None:

            await interaction.response.send_message(
                "❌ Ticket channel could not be found.",
                ephemeral=True
            )

            return

        ticket_channel_id = ticket_channel.id


        # ==================================
        # GET QUEUE CHANNEL
        # ==================================

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


        # ==================================
        # CHECK QUEUE CHANNEL
        # ==================================

        if not isinstance(
            queue_channel,
            discord.TextChannel
        ):

            await interaction.response.send_message(
                "❌ QUEUE_CHANNEL_ID is not a text channel.",
                ephemeral=True
            )

            return


        # ==================================
        # GET NOTED CATEGORY
        # ==================================

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


        # ==================================
        # CHECK NOTED CATEGORY
        # ==================================

        if not isinstance(
            noted_category,
            discord.CategoryChannel
        ):

            await interaction.response.send_message(
                "❌ NOTED_CATEGORY_ID is not a category.",
                ephemeral=True
            )

            return


        # ==================================
        # MOVE TICKET TO NOTED
        # ==================================

        try:

            await ticket_channel.edit(
                name=f"noted．{quantity}．{item}",
                category=noted_category,
                reason="New order queued"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I don't have permission to rename "
                "or move the ticket channel.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            await interaction.response.send_message(
                f"❌ Failed to move ticket channel: `{e}`",
                ephemeral=True
            )

            return


        # ==================================
        # CREATE QUEUE EMBED
        # ==================================

        embed = discord.Embed(

            description=(

                "_ _\n\n"

                "_ _　　    　　　　<:apple_folder:1531585484256444567> "
                "**TOMA GOT AN ORDER!**　　　　　　　　\n"

                f"_ _　　   　　　　╰     <#{ticket_channel_id}>   𐔌\n"

                f"_ _　　    　　　　ordered : {quantity}   - [ {item} ] "
                "<:003_orangeslice:1531666035139280970>\n"

                f"_ _　　   　 　　　paid via {mop} : ₱`{amount}.00`\n"

                f"_ _　　　　　　ⓘ　　~~  ~~　　{interaction.user.mention}\n"

                "\n"

                "_ _　　　　　　　( ?  **STATUS: NOTED** )\n"

                "\n"

                "_ _"
            )
        )


        # ==================================
        # SEND QUEUE MESSAGE
        # ==================================

        try:

            await queue_channel.send(

                content=(

                    "_ _\n"

                    f"_ _  ⓘ   {user.mention}   ordered something !\n"

                    "_ _"
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
                "❌ I found the queue channel, but I don't have permission to send messages there.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            await interaction.response.send_message(
                f"❌ Discord rejected the queue message: `{e}`",
                ephemeral=True
            )

            return


        # ==================================
        # NOTED CONFIRMATION
        # ==================================

        await interaction.response.send_message(

            (
                "_ _\n\n"

                "_ _      <a:ise_a2:1531670472155070465>    ~~                       ~~     "
                "<a:004_2_carrot:1531669152199213269>    ~~                       ~~   "
                "<a:004_2_carrot:1531669152199213269>\n"

                "_ _   **noted                     processing               completed**\n\n"

                "_ _       your order  is  "
                "[queued](https://discord.com/channels/1412690271296163963/1551245952063377408) . "
                "kindly  wait  until  we\n"

                "_ _ process your order . you can check for  "
                "[updates](https://discord.com/channels/1412690271296163963/1500685002671915239)\n"

                "_ _ here. no rushing of orders, **thank you so much !**\n"

                ">   pings   :     <@&1412724532623441941>  "
                "<@&1442868959245504735> <@&1412762016753516614>\n\n"

                "_ _"
            ),
        )


# ==========================================
# SETUP
# ==========================================

async def setup(bot):

    await bot.add_cog(
        Queue(bot)
    )