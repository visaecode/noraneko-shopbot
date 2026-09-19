import os
import discord

from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

QUEUE_CHANNEL_ID = int(os.getenv("QUEUE_CHANNEL_ID"))
EMOJI_PROCESSING = os.getenv("EMOJI_PROCESSING")
EMOJI_COMPLETED = os.getenv("EMOJI_COMPLETED")
EMOJI_CANCELLED = os.getenv("EMOJI_CANCELLED")

class QueueStatusSelection(discord.ui.Select):

    def __init__(self, ticket_channel_id):

        self.ticket_channel_id = ticket_channel_id

        options = [
            discord.SelectOption(
                label="toma is processing your order",
                value="processing",
                emoji=EMOJI_PROCESSING
            ),

            discord.SelectOption(
                label="toma completed your order",
                value="processing",
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

    async def callback(self, interaction: discord.Interaction):

        status = self.value[0]

        # CURRENT EMBED GETTER
        embed = interaction.message.embeds[0]

        for i, field in enumerate(embed.fields):

            if field.name == "status":

                embed.set_field_at(
                    i,
                    name="Status",
                    value=f"**{status}**",
                    inline=True
                )

            break

        # UPDATING THE MESSAGE
        await interaction.message.edit(
            embed=embed,
            view=self.view
        )

        # TICKET CHANNEL
        ticket = interaction.client.get_channel(
            self.ticket_channel_id
        )

        if ticket:

            messages = {
                "processing" :
                    "Your order is now processing"
            }
