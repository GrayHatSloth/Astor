# ============================================================
# src/commands/weekly/weekly_commands.py — Weekly Mode Slash Commands
# ============================================================
# /startweekly  — begin a random weekly mode + twist
# /forceweekly  — force a specific mode
# /endweekly    — manually end the current twist
# ============================================================

import discord
from discord import app_commands

from config import Config


async def setup(bot, mode_manager, twist_manager):
    """Register all weekly-related slash commands on the bot tree."""

    async def _require_admin(interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return False
        return True

    @bot.tree.command(
        name="startweekly",
        description="Start the new weekly event with a random mode",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def startweekly(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        mode_ok  = await mode_manager.start_weekly_mode()
        twist_ok = False
        if mode_ok:
            twist_ok = await twist_manager.start_twist(
                bot.get_channel(Config.GENERAL_CHANNEL_ID)
            )

        if not await _require_admin(interaction):
            return

        if mode_ok and twist_ok:
            await interaction.followup.send("✅ Weekly event started!", ephemeral=True)
        elif not mode_ok:
            await interaction.followup.send(
                "⚠️ A weekly mode is already active. Complete it first.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "⚠️ A weekly twist is already pending or active.", ephemeral=True
            )

    @bot.tree.command(
        name="forceweekly",
        description="Force a specific weekly mode",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(mode="Select the weekly mode to activate")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Invite Competition", value="invite_comp"),
        app_commands.Choice(name="Debate Week",        value="debate"),
        app_commands.Choice(name="Movie/Game Night",   value="movie_night"),
        app_commands.Choice(name="Profile Competition", value="profile_comp"),
        app_commands.Choice(name="Button Frenzy",      value="button_frenzy"),
        app_commands.Choice(name="Mystery Solving",    value="mystery"),
    ])
    async def forceweekly(interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)

        mode_ok  = await mode_manager.start_weekly_mode(forced_mode=mode.value)
        twist_ok = False
        if mode_ok:
            twist_ok = await twist_manager.start_twist(
                bot.get_channel(Config.GENERAL_CHANNEL_ID)
            )

        if not await _require_admin(interaction):
            return

        if mode_ok and twist_ok:
            await interaction.followup.send(f"✅ Forced weekly mode: {mode.name}", ephemeral=True)
        elif not mode_ok:
            await interaction.followup.send(
                "⚠️ A weekly mode is already active. Complete it first.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "⚠️ A weekly twist is already pending or active.", ephemeral=True
            )

    @bot.tree.command(
        name="endweekly",
        description="Manually end the current weekly twist",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def endweekly(interaction: discord.Interaction):
        gen = bot.get_channel(Config.GENERAL_CHANNEL_ID)
        if not await _require_admin(interaction):
            return

        if gen:
            await twist_manager.end_twist(gen)
            await interaction.response.send_message("Weekly twist ended!", ephemeral=True)
        else:
            await interaction.response.send_message("Could not find general channel!", ephemeral=True)
