# ============================================================
# src/commands/utility/utility_commands.py — General Utility Commands
# ============================================================
# /botstatus — show PID, latency, guild, and session info
# ============================================================

import os

import discord

from config import Config


async def setup(bot):
    """Register utility slash commands on the bot tree."""

    @bot.tree.command(
        name="botstatus",
        description="Show the current bot process and session info",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def botstatus(interaction: discord.Interaction):
        pid = os.getpid()
        conn = getattr(bot, "_connection", None)
        session = getattr(conn, "session_id", "unknown") if conn else "unknown"

        text = (
            f"PID: {pid}\n"
            f"Bot: {bot.user}\n"
            f"Guild: {bot.guild.name if bot.guild else 'None'}\n"
            f"Latency: {bot.latency:.3f}s\n"
            f"Session: {session}"
        )
        await interaction.response.send_message(text, ephemeral=True)
