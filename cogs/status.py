import os
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# CONFIG
# =========================================================

TIMEZONE = ZoneInfo("Asia/Manila")

SHOP_STATUS_CHANNEL_ID = int(
    os.getenv("SHOP_STATUS_CHANNEL_ID", "0")
)

# Link used by the button
SHOP_ORDER_URL = os.getenv(
    "SHOP_ORDER_URL",
    "https://discord.com/channels/1412690271296163963/1503647974062952549"
)

# Automatic shop schedule
OPEN_HOUR = int(
    os.getenv("SHOP_OPEN_HOUR", "10")
)

OPEN_MINUTE = int(
    os.getenv("SHOP_OPEN_MINUTE", "0")
)

CLOSE_HOUR = int(
    os.getenv("SHOP_CLOSE_HOUR", "22")
)

CLOSE_MINUTE = int(
    os.getenv("SHOP_CLOSE_MINUTE", "0")
)

# File used to remember status
DATA_FILE = "shop_status.json"


# =========================================================
# SHOP STATUS COG
# =========================================================

class ShopStatus(commands.Cog):

    shop = app_commands.Group(
        name="shop",
        description="Manage the shop status."
    )

    def __init__(self, bot: commands.Bot):

        self.bot = bot

        self.status = "closed"

        # True when staff manually opened/closed the shop
        self.manual_override = False

        # Discord message ID of the current status message
        self.status_message_id = None

        self.last_automatic_state = None
        self.last_announcement_date = None

        self.load_data()

        self.shop_scheduler.start()

    # =====================================================
    # COG UNLOAD
    # =====================================================

    def cog_unload(self):

        self.shop_scheduler.cancel()

    # =====================================================
    # DATA
    # =====================================================

    def load_data(self):

        if not os.path.exists(DATA_FILE):
            return

        try:

            with open(
                DATA_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            self.status = data.get(
                "status",
                "closed"
            )

            self.manual_override = data.get(
                "manual_override",
                False
            )

            self.status_message_id = data.get(
                "status_message_id"
            )

            self.last_automatic_state = data.get(
                "last_automatic_state"
            )

            self.last_announcement_date = data.get(
                "last_announcement_date"
            )

        except Exception as e:

            print(
                f"[SHOP STATUS] "
                f"Failed to load data: {e}"
            )

    def save_data(self):

        data = {
            "status": self.status,

            "manual_override":
                self.manual_override,

            "status_message_id":
                self.status_message_id,

            "last_automatic_state":
                self.last_automatic_state,

            "last_announcement_date":
                self.last_announcement_date
        }

        try:

            with open(
                DATA_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    data,
                    file,
                    indent=4
                )

        except Exception as e:

            print(
                f"[SHOP STATUS] "
                f"Failed to save data: {e}"
            )

    # =====================================================
    # CHANNEL
    # =====================================================

    async def get_status_channel(self):

        if SHOP_STATUS_CHANNEL_ID == 0:

            print(
                "[SHOP STATUS] "
                "SHOP_STATUS_CHANNEL_ID "
                "has not been configured."
            )

            return None

        channel = self.bot.get_channel(
            SHOP_STATUS_CHANNEL_ID
        )

        if channel is not None:
            return channel

        try:

            channel = await self.bot.fetch_channel(
                SHOP_STATUS_CHANNEL_ID
            )

            return channel

        except Exception as e:

            print(
                f"[SHOP STATUS] "
                f"Could not find channel: {e}"
            )

            return None

    # =====================================================
    # DELETE PREVIOUS STATUS MESSAGE
    # =====================================================

    async def delete_previous_status_message(self):

        if not self.status_message_id:
            return

        channel = await self.get_status_channel()

        if channel is None:
            return

        try:

            message = await channel.fetch_message(
                self.status_message_id
            )

            await message.delete()

            print(
                "[SHOP STATUS] "
                "Previous status message deleted."
            )

        except discord.NotFound:

            print(
                "[SHOP STATUS] "
                "Previous status message was already deleted."
            )

        except discord.Forbidden:

            print(
                "[SHOP STATUS] "
                "Bot does not have permission "
                "to delete the previous message."
            )

        except discord.HTTPException as e:

            print(
                f"[SHOP STATUS] "
                f"Failed to delete previous message: {e}"
            )

        finally:

            self.status_message_id = None

            self.save_data()

    # =====================================================
    # TIME
    # =====================================================

    def now(self):

        return datetime.now(TIMEZONE)

    def get_open_time(self):

        return time(
            OPEN_HOUR,
            OPEN_MINUTE
        )

    def get_close_time(self):

        return time(
            CLOSE_HOUR,
            CLOSE_MINUTE
        )

    def is_within_schedule(self):

        current = self.now().time()

        open_time = self.get_open_time()
        close_time = self.get_close_time()

        # Normal same-day schedule
        if open_time < close_time:

            return (
                open_time
                <= current
                < close_time
            )

        # Overnight schedule
        return (
            current >= open_time
            or current < close_time
        )

    def format_time(
        self,
        hour,
        minute
    ):

        dt = datetime(
            2000,
            1,
            1,
            hour,
            minute
        )

        return dt.strftime(
            "%I:%M %p"
        ).lstrip("0")

    # =====================================================
    # BUTTON
    # =====================================================

    def create_button_view(self):

        view = discord.ui.View(
            timeout=None
        )

        if SHOP_ORDER_URL:

            button = discord.ui.Button(
                label="daily!",
                style=discord.ButtonStyle.link,
                url=SHOP_ORDER_URL
            )

            view.add_item(button)

        return view

    # =====================================================
    # OPEN MESSAGE
    # =====================================================

    def get_open_message(
        self,
        automatic=False
    ):

        message = (
            "_ _\n"
            "## _ _⠀         ⠀__noraneko is now open__\n"
            "-# _ _ ⠀⠀ ⠀⠀⠀⠀ check [#dailies]"
            "(https://discord.com/channels/"
            "1412690271296163963/"
            "1503647974062952549)"
            " for available items\n"
            "_ _\n"
            "_ _⠀⠀⠀         [drop]"
            "(https://discord.com/channels/"
            "1412690271296163963/"
            "1444293920832884736)"
            " order now. do not forget\n"
            "_ _⠀⠀⠀         to [ask]"
            "(https://discord.com/channels/"
            "1412690271296163963/"
            "1444282982746554378)"
            " for availability of items\n"
            "_ _⠀⠀⠀         ping the "
            "<@&1412762016753516614> / "
            "<@&1442868959245504735>\n"
            "_ _⠀⠀⠀         for assistance and questions\n"
            "_ _\n"
            "-# _ _⠀⠀⠀ ⠀⠀⠀⠀ ⠀ **cc** : "
            "<@&1412724532623441941> "
            "<@&1442868494143328381>\n"
            "_ _"
        )

        return message

    # =====================================================
    # CLOSED MESSAGE
    # =====================================================

    def get_close_message(
        self,
        automatic=False
    ):

        message = (
            "_ _\n"
            "## _ _⠀         ⠀__noraneko is now ~~closed~~__\n"
            "-# _ _ ⠀⠀ ⠀⠀⠀⠀ thank you for "
            "[today]"
            "(https://discord.com/channels/"
            "1412690271296163963/"
            "1500685002671915239)"
            ", our <@&1412724532623441941>\n"
            "_ _\n"
            "_ _⠀⠀⠀          staffs  are out now, "
            "[all orders]"
            "(https://discord.com/channels/"
            "1412690271296163963/"
            "1551245952063377408)\n"
            "_ _⠀⠀⠀          will continue processing "
            "tomm\n"
            "_ _⠀⠀⠀          for  assistance  and   questions\n"
            "_ _⠀⠀⠀          please do wait "
            "[us]"
            "(https://discord.com/channels/"
            "1412690271296163963/"
            "1452355932540506193)"
            " to assist you\n"
            "_ _\n"
            "-# _ _⠀⠀⠀ ⠀⠀⠀⠀ ⠀ **cc** : "
            "<@&1412724532623441941> "
            "<@&1442868494143328381>\n"
            "_ _"
        )

        return message

    # =====================================================
    # SEND ANNOUNCEMENT
    # =====================================================

    async def send_announcement(
        self,
        status: str,
        automatic=False
    ):

        channel = await self.get_status_channel()

        if channel is None:
            return False

        try:

            # ---------------------------------------------
            # DELETE OLD STATUS MESSAGE FIRST
            # ---------------------------------------------

            await self.delete_previous_status_message()

            # ---------------------------------------------
            # CREATE NEW MESSAGE
            # ---------------------------------------------

            if status == "open":

                content = self.get_open_message(
                    automatic
                )

            else:

                content = self.get_close_message(
                    automatic
                )

            # ---------------------------------------------
            # CREATE BUTTON
            # ---------------------------------------------

            view = self.create_button_view()

            # ---------------------------------------------
            # SEND NEW MESSAGE
            # ---------------------------------------------

            message = await channel.send(
                content=content,
                view=view
            )

            # ---------------------------------------------
            # SAVE MESSAGE ID
            # ---------------------------------------------

            self.status_message_id = message.id

            self.save_data()

            print(
                "[SHOP STATUS] "
                f"{status.upper()} message sent. "
                f"Message ID: {message.id}"
            )

            return True

        except discord.Forbidden:

            print(
                "[SHOP STATUS] "
                "Bot does not have permission "
                "to send/delete messages."
            )

        except discord.HTTPException as e:

            print(
                f"[SHOP STATUS] "
                f"Discord error: {e}"
            )

        return False

    # =====================================================
    # AUTOMATIC SCHEDULER
    # =====================================================

    @tasks.loop(seconds=30)
    async def shop_scheduler(self):

        try:

            if not self.bot.is_ready():
                return

            current_time = self.now()

            current_date = (
                current_time
                .date()
                .isoformat()
            )

            scheduled_open = (
                self.is_within_schedule()
            )

            desired_status = (
                "open"
                if scheduled_open
                else "closed"
            )

            # ---------------------------------------------
            # MANUAL OVERRIDE
            # ---------------------------------------------

            if self.manual_override:
                return

            # ---------------------------------------------
            # NOTHING CHANGED
            # ---------------------------------------------

            if self.status == desired_status:

                return

            # ---------------------------------------------
            # CHANGE STATUS
            # ---------------------------------------------

            self.status = desired_status

            self.last_automatic_state = (
                desired_status
            )

            self.last_announcement_date = (
                current_date
            )

            self.save_data()

            await self.send_announcement(
                desired_status,
                automatic=True
            )

            print(
                "[SHOP STATUS] "
                f"Automatically changed to "
                f"{desired_status.upper()} at "
                f"{current_time.strftime('%I:%M:%S %p')}"
            )

        except Exception as e:

            print(
                "[SHOP STATUS] "
                f"Scheduler error: {e}"
            )

    @shop_scheduler.before_loop
    async def before_scheduler(self):

        await self.bot.wait_until_ready()

    # =====================================================
    # /SHOP OPEN
    # =====================================================

    @shop.command(
        name="open",
        description="Manually open the shop."
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def shop_open(
        self,
        interaction: discord.Interaction
    ):

        if self.status == "open":

            await interaction.response.send_message(
                "the shop is already **open**.",
                ephemeral=True
            )

            return

        self.status = "open"

        self.manual_override = True

        self.save_data()

        sent = await self.send_announcement(
            "open",
            automatic=False
        )

        if sent:

            await interaction.response.send_message(
                "shop is now **open**.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "shop status changed to **open**, "
                "but I couldn't send the announcement.",
                ephemeral=True
            )

    # =====================================================
    # /SHOP CLOSE
    # =====================================================

    @shop.command(
        name="close",
        description="Manually close the shop."
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def shop_close(
        self,
        interaction: discord.Interaction
    ):

        if self.status == "closed":

            await interaction.response.send_message(
                "the shop is already **closed**.",
                ephemeral=True
            )

            return

        self.status = "closed"

        self.manual_override = True

        self.save_data()

        sent = await self.send_announcement(
            "closed",
            automatic=False
        )

        if sent:

            await interaction.response.send_message(
                "shop has been **closed**.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "shop status changed to **closed**, "
                "but I couldn't send the announcement.",
                ephemeral=True
            )

    # =====================================================
    # /SHOP AUTO
    # =====================================================

    @shop.command(
        name="auto",
        description="Return the shop to the automatic schedule."
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def shop_auto(
        self,
        interaction: discord.Interaction
    ):

        self.manual_override = False

        scheduled_open = (
            self.is_within_schedule()
        )

        desired_status = (
            "open"
            if scheduled_open
            else "closed"
        )

        self.status = desired_status

        self.save_data()

        await self.send_announcement(
            desired_status,
            automatic=True
        )

        await interaction.response.send_message(
            "⚙️ Automatic shop schedule has been "
            "**restored**.",
            ephemeral=True
        )

    # =====================================================
    # /SHOP STATUS
    # =====================================================

    @shop.command(
        name="status",
        description="Check the current shop status."
    )
    async def shop_status(
        self,
        interaction: discord.Interaction
    ):

        if self.status == "open":

            message = (
                "**SHOP STATUS: OPEN**\n\n"
                "you can currently place orders."
            )

        else:

            message = (
                "**SHOP STATUS: CLOSED**\n\n"
                "the shop is currently unavailable."
            )

        await interaction.response.send_message(
            message
        )

    # =====================================================
    # /SHOP SCHEDULE
    # =====================================================

    @shop.command(
        name="schedule",
        description="View the shop schedule."
    )
    async def shop_schedule(
        self,
        interaction: discord.Interaction
    ):

        message = (
            "**our shop schedule**\n\n"
            f"opening hours: "
            f"**{self.format_time(OPEN_HOUR, OPEN_MINUTE)}**\n"
            f"closing hours: "
            f"**{self.format_time(CLOSE_HOUR, CLOSE_MINUTE)}**\n\n"
            "timezone: **Asia/Manila**"
        )

        await interaction.response.send_message(
            message
        )

    # =====================================================
    # ERROR HANDLER
    # =====================================================

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):

        if isinstance(
            error,
            app_commands.MissingPermissions
        ):

            await interaction.response.send_message(
                "❌ You need **Manage Server** "
                "permission to use this command.",
                ephemeral=True
            )

            return

        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot: commands.Bot):

    await bot.add_cog(
        ShopStatus(bot)
    )