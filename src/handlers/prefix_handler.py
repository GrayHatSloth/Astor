# ============================================================
# src/handlers/prefix_handler.py — Legacy Prefix Commands
# ============================================================
# Handles a.snipe, a.thatday, a.blacklist and the blacklist
# check that runs on every non-bot message.
# ============================================================

import os
import json
import datetime
import discord

from config import Config
from src.utils.helpers import format_duration_since


# ── Blacklist persistence ───────────────────────────────────
_DATA_FILE = Config.WHITELIST_FILE
_cmd_data: dict = {"blacklist": []}


def _load_data() -> None:
    global _cmd_data
    if os.path.exists(_DATA_FILE):
        with open(_DATA_FILE, "r") as f:
            try:
                _cmd_data = json.load(f)
            except json.JSONDecodeError:
                _cmd_data = {"blacklist": []}
    else:
        _cmd_data = {"blacklist": []}
        _save_data()

    if "blacklist" not in _cmd_data:
        _cmd_data["blacklist"] = []
        _save_data()


def _save_data() -> None:
    with open(_DATA_FILE, "w") as f:
        json.dump(_cmd_data, f, indent=4)


def _get_blacklist() -> list[str]:
    return [w.lower() for w in _cmd_data.get("blacklist", [])]


def _add_blacklist_value(value: str) -> tuple[bool, str]:
    value = value.strip()
    if not value:
        return False, "Blacklist entry cannot be empty."

    if value.lower() in [w.lower() for w in _cmd_data.get("blacklist", [])]:
        return False, "That value is already blacklisted."

    _cmd_data.setdefault("blacklist", []).append(value)
    _save_data()
    return True, value


# Load on import so the blacklist is ready immediately
_load_data()


# ── SnipeView (Close button for snipe embeds) ──────────────
class SnipeView(discord.ui.View):
    """View attached to snipe embeds — lets the invoker close it."""

    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your snipe view.", ephemeral=True
            )
            return
        await interaction.message.delete()


# ── Main handler ────────────────────────────────────────────
async def handle_prefix_command(bot, message: discord.Message) -> bool:
    """
    Process prefix commands (a.snipe, a.thatday, a.blacklist).
    Returns True if a command was handled, False otherwise.
    Only whitelisted users may use these.
    """
    content = message.content.strip()
    content_lower = content.lower()
    if not content_lower.startswith("a."):
        return False

    parts = content_lower.split(maxsplit=1)
    command = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    # Gate: only whitelisted users may use these commands
    if message.author.id not in Config.WHITELIST_IDS:
        return False

    # ── a.snipe ─────────────────────────────────────────────
    if command == "a.snipe":
        index = 1
        if arg:
            try:
                index = int(arg)
                if index < 1:
                    raise ValueError()
            except ValueError:
                await message.channel.send(
                    "⚠️ Invalid snipe number. Use `a.snipe` or `a.snipe <number>`."
                )
                return True

        deleted = getattr(bot, "deleted_messages", [])
        if index > len(deleted):
            await message.channel.send(
                f"⚠️ Only {len(deleted)} deleted message(s) available to snipe."
            )
            return True

        item = deleted[-index]
        embed = discord.Embed(
            title="🕵️ Deleted Message Sniped",
            description=f"Showing deleted message #{index}",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="Author",
            value=f"{item['author_name']}\n<{item['author_id']}>",
            inline=False,
        )
        embed.add_field(name="Channel", value=item["channel_name"], inline=True)
        if item["created_at"]:
            embed.add_field(name="Created At", value=item["created_at"], inline=True)
        if item["deleted_at"]:
            embed.add_field(name="Deleted At", value=item["deleted_at"], inline=True)

        content_text = item["content"] or "*No text content*"
        if len(content_text) > 1024:
            content_text = content_text[:1020] + "..."
        embed.add_field(name="Message Content", value=content_text, inline=False)

        if item["attachments"]:
            att_text = "\n".join(item["attachments"])
            if len(att_text) > 1024:
                att_text = att_text[:1020] + "..."
            embed.add_field(name="Attachments", value=att_text, inline=False)

        try:
            await message.delete()
        except Exception:
            pass

        await message.channel.send(embed=embed, view=SnipeView(message.author.id))
        return True

    # ── a.thatday ───────────────────────────────────────────
    if command == "a.thatday":
        if message.author.id not in Config.WHITELIST_IDS and message.author.id != Config.THATDAY_ONLY_ID:
            await message.channel.send("⚠️ You are not authorized to use `a.thatday`.")
            return True

        start = datetime.datetime(2026, 2, 24, 1, 54, tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        if now < start:
            await message.channel.send("⚠️ The date is in the future.")
            return True

        visible_time = format_duration_since(start, now)
        await message.channel.send(f"it's been {visible_time}.")
        return True

    # ── a.blacklist ─────────────────────────────────────────
    if command == "a.blacklist":
        if not arg:
            await message.channel.send(
                "⚠️ You must provide a word or mention to blacklist."
            )
            return True

        success, result = _add_blacklist_value(arg)
        if success:
            await message.channel.send(f"✅ Added to blacklist: `{result}`")
        else:
            await message.channel.send(f"⚠️ {result}")
        return True

    return False


# ── Blacklist check (called on every message) ──────────────
async def check_blacklist(message: discord.Message) -> bool:
    """
    Delete the message and DM the user if it contains a
    blacklisted word. Returns True if blocked.
    """
    if message.author.bot:
        return False
    if message.content.startswith("a."):
        return False

    content_lower = message.content.lower()
    for word in _get_blacklist():
        if word and word in content_lower:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.author.send(
                    f"⚠️ Your message contained a blacklisted word: "
                    f"`{word}` and has been deleted."
                )
            except Exception:
                pass
            return True

    return False
