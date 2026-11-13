
import os
import json
import sqlite3
import discord

from pathlib import Path
from contextlib import closing
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()


# config
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", 0))

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
MESSAGE_DIR = BASE_DIR / "messages"

DATA_DIR.mkdir(parents=True, exist_ok=True)
MESSAGE_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "balance.db"
MESSAGE_PATH = MESSAGE_DIR / "balance_messages.json"


# load json
with open(MESSAGE_PATH, "r", encoding="utf-8") as file:
    MESSAGES = json.load(file)


# embed builder
def create_embed(key: str, **kwargs):

    config = MESSAGES[key]

    embed = discord.Embed(
        title=config.get("title", "").format(**kwargs),
        description=config.get("description", "").format(**kwargs),
        color=config.get("color", 0x800000)
    )

    for field in config.get("fields", []):

        embed.add_field(
            name=field["name"].format(**kwargs),
            value=field["value"].format(**kwargs),
            inline=field.get("inline", False)
        )

    footer = config.get("footer")

    if footer:
        embed.set_footer(text=footer.format(**kwargs))

    return embed


# database
def get_db():

    db = sqlite3.connect(DB_PATH, timeout=30)

    db.row_factory = sqlite3.Row

    db.execute("PRAGMA busy_timeout = 30000")

    return db


def init_database():

    with closing(get_db()) as db:

        db.execute("PRAGMA journal_mode = WAL")

        db.executescript("""

            CREATE TABLE IF NOT EXISTS balances (

                user_id INTEGER PRIMARY KEY,

                balance INTEGER NOT NULL DEFAULT 0,

                is_reseller INTEGER NOT NULL DEFAULT 0,

                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transactions (

                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                staff_id INTEGER NOT NULL,

                transaction_type TEXT NOT NULL,

                amount INTEGER NOT NULL,

                balance_after INTEGER NOT NULL,

                reason TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_user
            ON transactions(user_id);

        """)

        db.commit()

    print("[BALANCE] Database initialized.")



# staff check
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


# get balance
def get_balance(user_id: int):

    with closing(get_db()) as db:

        row = db.execute("""
            SELECT balance, is_reseller
            FROM balances
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if row is None:

            return {
                "balance": 0,
                "is_reseller": False
            }

        return {
            "balance": row["balance"],
            "is_reseller": bool(row["is_reseller"])
        }


# add balance
def add_balance(
    user_id: int,
    staff_id: int,
    amount: int,
    is_reseller: bool,
    reason: str
):

    with closing(get_db()) as db:

        try:

            db.execute("BEGIN IMMEDIATE")

            db.execute("""
                INSERT OR IGNORE INTO balances (
                    user_id,
                    balance,
                    is_reseller
                )
                VALUES (?, 0, ?)
            """, (user_id, int(is_reseller)))

            current = db.execute("""
                SELECT balance
                FROM balances
                WHERE user_id = ?
            """, (user_id,)).fetchone()

            new_balance = current["balance"] + amount

            db.execute("""
                UPDATE balances
                SET
                    balance = ?,
                    is_reseller = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                new_balance,
                int(is_reseller),
                user_id
            ))

            db.execute("""
                INSERT INTO transactions (
                    user_id,
                    staff_id,
                    transaction_type,
                    amount,
                    balance_after,
                    reason
                )
                VALUES (?, ?, 'ADD', ?, ?, ?)
            """, (
                user_id,
                staff_id,
                amount,
                new_balance,
                reason
            ))

            db.commit()

            return new_balance

        except Exception:

            db.rollback()
            raise

# deduct balance

def deduct_balance(
    user_id: int,
    staff_id: int,
    amount: int,
    reason: str
):

    with closing(get_db()) as db:

        try:

            db.execute("BEGIN IMMEDIATE")

            current = db.execute("""
                SELECT balance
                FROM balances
                WHERE user_id = ?
            """, (user_id,)).fetchone()

            if current is None:
                db.rollback()
                return None

            current_balance = current["balance"]

            if amount > current_balance:
                db.rollback()
                return None

            new_balance = current_balance - amount

            db.execute("""
                UPDATE balances
                SET
                    balance = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                new_balance,
                user_id
            ))

            db.execute("""
                INSERT INTO transactions (
                    user_id,
                    staff_id,
                    transaction_type,
                    amount,
                    balance_after,
                    reason
                )
                VALUES (?, ?, 'DEDUCT', ?, ?, ?)
            """, (
                user_id,
                staff_id,
                amount,
                new_balance,
                reason
            ))

            db.commit()

            return new_balance

        except Exception:

            db.rollback()
            raise


# ==========================================
# LEADERBOARD DATABASE
# ==========================================

def get_leaderboard(limit: int = 10):

    with closing(get_db()) as db:

        return db.execute("""
            SELECT
                user_id,
                balance,
                is_reseller
            FROM balances
            WHERE balance > 0
            ORDER BY balance DESC, user_id ASC
            LIMIT ?
        """, (limit,)).fetchall()


# ==========================================
# BALANCE COG
# ==========================================

class Balance(commands.Cog):

    def __init__(self, bot: commands.Bot):

        self.bot = bot

    # ======================================
    # ADD BALANCE
    # ======================================

    @app_commands.command(
        name="addbal",
        description="Add balance to a user's account."
    )

    @app_commands.describe(
        user="User receiving the balance",
        reseller="Is this user a reseller?",
        amount="Amount to add",
        reason="Reason for adding balance"
    )

    async def addbal(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reseller: bool,
        amount: app_commands.Range[int, 1, 1000000000],
        reason: str = "Balance added by staff"
    ):

        if not isinstance(interaction.user, discord.Member):
            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                MESSAGES["errors"]["not_staff"],
                ephemeral=True
            )
            return

        try:

            new_balance = add_balance(
                user_id=user.id,
                staff_id=interaction.user.id,
                amount=amount,
                is_reseller=reseller,
                reason=reason
            )

            embed = create_embed(
                "add_success",
                user=user.mention,
                amount=f"{amount:,}",
                balance=f"{new_balance:,}",
                reseller=(
                    MESSAGES["labels"]["reseller_yes"]
                    if reseller
                    else MESSAGES["labels"]["reseller_no"]
                ),
                staff=interaction.user.mention,
                reason=reason[:1024]
            )

            await interaction.response.send_message(
                embed=embed
            )

        except sqlite3.Error as e:

            print(f"[BALANCE ADD ERROR] {e}")

            await interaction.response.send_message(
                MESSAGES["errors"]["database_error"],
                ephemeral=True
            )

    # ======================================
    # DEDUCT BALANCE
    # ======================================

    @app_commands.command(
        name="deductbal",
        description="Deduct balance from a user's account."
    )

    @app_commands.describe(
        user="User to deduct balance from",
        amount="Amount to deduct",
        reason="Reason for deducting balance"
    )

    async def deductbal(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 1000000000],
        reason: str = "Balance deducted by staff"
    ):

        if not isinstance(interaction.user, discord.Member):
            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                MESSAGES["errors"]["not_staff"],
                ephemeral=True
            )
            return

        try:

            new_balance = deduct_balance(
                user_id=user.id,
                staff_id=interaction.user.id,
                amount=amount,
                reason=reason
            )

            if new_balance is None:

                current = get_balance(user.id)

                await interaction.response.send_message(
                    MESSAGES["errors"]["insufficient_balance"].format(
                        user=user.mention,
                        balance=f"{current['balance']:,}",
                        amount=f"{amount:,}"
                    ),
                    ephemeral=True
                )
                return

            embed = create_embed(
                "deduct_success",
                user=user.mention,
                amount=f"{amount:,}",
                balance=f"{new_balance:,}",
                staff=interaction.user.mention,
                reason=reason[:1024]
            )

            await interaction.response.send_message(
                embed=embed
            )

        except sqlite3.Error as e:

            print(f"[BALANCE DEDUCT ERROR] {e}")

            await interaction.response.send_message(
                MESSAGES["errors"]["database_error"],
                ephemeral=True
            )

    # ======================================
    # LEADERBOARD
    # ======================================

    @app_commands.command(
        name="leaderboard",
        description="display the top users with the highest balance."
    )

    async def leaderboard(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(interaction.user, discord.Member):
            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                MESSAGES["errors"]["not_staff"],
                ephemeral=True
            )
            return

        try:

            results = get_leaderboard(10)

            if not results:

                await interaction.response.send_message(
                    MESSAGES["errors"]["empty_leaderboard"]
                )
                return

            entries = []

            medals = MESSAGES["labels"]["leaderboard_medals"]

            for index, row in enumerate(results):

                user_id = row["user_id"]
                balance = row["balance"]
                is_reseller = bool(row["is_reseller"])

                rank = (
                    medals[index]
                    if index < len(medals)
                    else f"#{index + 1}"
                )

                reseller_label = (
                    MESSAGES["labels"]["reseller_badge"]
                    if is_reseller
                    else ""
                )

                entries.append(
                    f"{rank} <@{user_id}>\n"
                    f"　₱{balance:,}.00{reseller_label}"
                )

            embed = create_embed(
                "leaderboard",
                entries="\n\n".join(entries)
            )

            await interaction.response.send_message(
                embed=embed
            )

        except sqlite3.Error as e:

            print(f"[LEADERBOARD ERROR] {e}")

            await interaction.response.send_message(
                MESSAGES["errors"]["leaderboard_error"],
                ephemeral=True
            )


# ==========================================
# SETUP
# ==========================================

async def setup(bot: commands.Bot):

    init_database()

    await bot.add_cog(Balance(bot))

    print("[BALANCE] Balance system loaded successfully.")
