import discord
from discord.ext import commands
from dotenv import dotenv       

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot (
    command_prefix="!",
    intent=intents
)

