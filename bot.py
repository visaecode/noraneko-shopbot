import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
QUEUE_CHANNEL_ID = int(os.getenv("QUEUE_CHANNEL_ID"))

# ---------
# MAIN SETUP
# ---------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

async def load_extension():

    await bot.load_extension("cogs.queue")
    await bot.load_extension("cogs.welcome")
    # await bot.load_extension("cogs.tickets")

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    await bot.tree.sync()

    print("Commands synced.")

async def main():
    async with bot:

        await load_extensions()

        await bot.start(TOKEN)

import asyncio

asyncio.run(main())