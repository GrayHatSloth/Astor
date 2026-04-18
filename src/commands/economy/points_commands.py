# ============================================================
# src/commands/economy/points_commands.py — Points Slash Commands
# ============================================================
# /points         — view your (or another user's) points
# /leaderboard    — paginated leaderboard
# /winner         — manually award a weekly-mode win
# /daily          — claim daily reward with streak
# /challenge      — get a new challenge
# /trackchallenges — view active challenge progress
# ============================================================

import time

import discord
from discord import app_commands

from config import Config
from src.utils.helpers import create_progress_bar
from src.views.leaderboard_view import LeaderboardView
from src.views.challenge_view import (
    ChallengeCompleteView,
    ChallengeRerollView,
    build_challenge_completion_embed,
)


async def setup(bot, points_manager):
    """Register all economy slash commands on the bot tree."""

    # ── /points ─────────────────────────────────────────────

    @bot.tree.command(
        name="points",
        description="Check your or another user's points",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(user="The user to check (default: yourself)")
    async def points_cmd(interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        data = points_manager.get_points(user.id)

        embed = discord.Embed(title=f"🪙 {user.display_name}'s Points", color=discord.Color.blue())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="💰 Total Points", value=f"**{data['points']}** 🪙", inline=True)
        embed.add_field(name="🏆 Wins",         value=f"**{data['wins']}** 🏆",   inline=True)

        # Rank
        lb = points_manager.leaderboard()
        rank = next((r for r, (uid, _) in enumerate(lb, 1) if uid == str(user.id)), None)
        if rank:
            embed.add_field(name="📈 Rank", value=f"**#{rank}** of {len(lb)}", inline=True)

        embed.add_field(
            name="📊 Stats",
            value=f"Total users: **{len(points_manager.data)}**\nPoints this week: **{data.get('weekly_points', 0)}**",
            inline=False,
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        try:
            await interaction.response.defer()
            await interaction.followup.send(embed=embed)
        except (discord.NotFound, discord.HTTPException) as exc:
            print(f"[CMD] points_cmd error: {exc}")

    # ── /leaderboard ────────────────────────────────────────

    @bot.tree.command(
        name="leaderboard",
        description="Show the top users by points",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def lb_cmd(interaction: discord.Interaction):
        view  = LeaderboardView(points_manager, interaction.user.id, bot)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view)

    # ── /winner ─────────────────────────────────────────────

    @bot.tree.command(
        name="winner",
        description="Manually assign a weekly mode winner",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(mode="Select the weekly mode", user="Select the winner")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Invite Competition", value="invite_comp"),
        app_commands.Choice(name="Debate Week",        value="debate"),
        app_commands.Choice(name="Movie/Game Night",   value="movie_night"),
        app_commands.Choice(name="Profile Competition", value="profile_comp"),
        app_commands.Choice(name="Button Frenzy",      value="button_frenzy"),
        app_commands.Choice(name="Mystery Solving",    value="mystery"),
    ])
    async def winner_cmd(interaction: discord.Interaction, mode: app_commands.Choice[str], user: discord.Member):
        pts = points_manager.add_points(user.id, mode.value)
        points_manager.add_win(user.id)
        _, completion = points_manager.update_challenge_progress(user.id, "event", "weekly_win")
        data = points_manager.get_points(user.id)

        embed = discord.Embed(
            title="🎉 Winner Awarded!",
            description=f"**{user.display_name}** has been awarded **{pts} points** for **{mode.name}**!",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="🏆 New Total Points", value=f"**{data['points']}** 🪙", inline=True)
        embed.add_field(name="🎯 Total Wins",       value=f"**{data['wins']}** 🏆",   inline=True)
        embed.add_field(name="📊 Mode",              value=mode.name,                  inline=True)
        embed.set_footer(text=f"Awarded by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

        if completion:
            ce = build_challenge_completion_embed(user, completion["name"], completion["reward"])
            await interaction.followup.send(embed=ce, view=ChallengeCompleteView(user.id))

    # ── /daily ──────────────────────────────────────────────

    @bot.tree.command(
        name="daily",
        description="Claim your daily points reward",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def daily_cmd(interaction: discord.Interaction):
        success, pts, streak, wait, completion = points_manager.claim_daily(interaction.user.id)

        if not success:
            h, rem = divmod(wait, 3600)
            m, _ = divmod(rem, 60)
            embed = discord.Embed(
                title="⏰ Daily Reward Cooldown",
                description="You've already claimed your daily reward today!",
                color=discord.Color.red(),
            )
            embed.add_field(name="⏳ Time Remaining", value=f"**{h}h {m}m**",     inline=True)
            embed.add_field(name="🔥 Current Streak", value=f"**{streak}** days", inline=True)
            embed.add_field(name="💡 Tip", value="Come back tomorrow for your next reward!", inline=False)
            await interaction.response.send_message(embed=embed)
            return

        mult = min(1.0 + (min(streak, 30) // 5) * 0.1, 2.0)
        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=f"You've claimed your daily reward of **{pts} points**!",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🔥 Streak",       value=f"**{streak}** days", inline=True)
        embed.add_field(name="⚡ Multiplier",    value=f"**{mult:.1f}x**",  inline=True)
        embed.add_field(name="💰 Points Earned", value=f"**{pts}** 🪙",     inline=True)

        next_ms = ((streak // 5) + 1) * 5
        if next_ms <= 30:
            next_mult = min(1.0 + (next_ms // 5) * 0.1, 2.0)
            embed.add_field(
                name="🎯 Next Milestone",
                value=f"Reach **{next_ms}** days for **{next_mult:.1f}x** multiplier!",
                inline=False,
            )
        embed.set_footer(text="Keep your streak going! Next reward in 24 hours")
        await interaction.response.send_message(embed=embed)

        if completion:
            ce = build_challenge_completion_embed(interaction.user, completion["name"], completion["reward"])
            await interaction.followup.send(embed=ce, view=ChallengeCompleteView(interaction.user.id))

    # ── /challenge ──────────────────────────────────────────

    @bot.tree.command(
        name="challenge",
        description="Get a random challenge to earn extra points",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(type="Choose challenge type")
    @app_commands.choices(type=[
        app_commands.Choice(name="Normal Challenge", value="normal"),
        app_commands.Choice(name="Event Challenge",  value="event"),
    ])
    async def challenge_cmd(interaction: discord.Interaction, type: app_commands.Choice[str]):
        challenges = points_manager.get_user_challenges(interaction.user.id)
        current = challenges.get(f"current_{type.value}")

        if current is not None:
            cost = points_manager.get_challenge_reroll_cost(interaction.user.id, type.value)
            cost_text = "Free" if cost == 0 else f"{cost} points"
            embed = discord.Embed(
                title="⏰ Active Challenge Found",
                description=(
                    "You already have an active challenge. "
                    "Would you like to reroll it for a fresh one?"
                ),
                color=discord.Color.orange(),
            )
            embed.add_field(name="Current Challenge", value=f"**{current['name']}**\n{current['description']}", inline=False)
            embed.add_field(name="Reroll Cost", value=f"**{cost_text}**", inline=True)
            embed.set_footer(text="First reroll is free for a new challenge assignment.")

            view = ChallengeRerollView(interaction.user.id, type.value, points_manager, cost)
            await interaction.response.send_message(embed=embed, view=view)
            return

        ok, result = points_manager.assign_random_challenge(interaction.user.id, type.value)

        if not ok:
            embed = discord.Embed(title="⏰ Challenge Cooldown", description=result, color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
            return

        ch = result
        embed = discord.Embed(
            title=f"🎯 New {type.name}!",
            description=f"**{ch['name']}**\n{ch['description']}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="🎁 Reward",   value=f"**{ch['reward']}** 🪙",                     inline=True)
        embed.add_field(name="🎯 Progress", value=f"**0/{ch['target']}**",                       inline=True)
        embed.add_field(name="📊 Type",     value=ch["type"].replace("_", " ").title(),           inline=True)
        embed.set_footer(text="Use /trackchallenges to view your progress!")
        await interaction.response.send_message(embed=embed)

    # ── /trackchallenges ────────────────────────────────────

    @bot.tree.command(
        name="trackchallenges",
        description="View your current challenges and progress",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def track_cmd(interaction: discord.Interaction):
        challenges = points_manager.get_user_challenges(interaction.user.id)
        embed = discord.Embed(
            title="🎯 Your Challenges",
            description="Track your progress on active challenges",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        # Normal challenge
        nc = challenges.get("current_normal")
        if nc:
            bar = create_progress_bar(nc["progress"], nc["target"])
            embed.add_field(
                name=f"🔹 {nc['name']} (Normal)",
                value=f"{nc['description']}\n{bar} **{nc['progress']}/{nc['target']}**\n🎁 **{nc['reward']}** 🪙",
                inline=False,
            )
        else:
            embed.add_field(name="🔹 Normal Challenge", value="*No active challenge*\nUse `/challenge` to get one!", inline=False)

        # Event challenge
        ec = challenges.get("current_event")
        if ec:
            bar = create_progress_bar(ec["progress"], ec["target"])
            embed.add_field(
                name=f"🎪 {ec['name']} (Event)",
                value=f"{ec['description']}\n{bar} **{ec['progress']}/{ec['target']}**\n🎁 **{ec['reward']}** 🪙",
                inline=False,
            )
        else:
            embed.add_field(name="🎪 Event Challenge", value="*No active challenge*\nUse `/challenge` to get one!", inline=False)

        # Recent completions
        completed = challenges.get("completed", [])
        if completed:
            recent = completed[-3:]
            text = ""
            for c in recent:
                hrs = (int(time.time()) - c["timestamp"]) // 3600
                text += f"✅ {c['name']} (+{c['reward']} 🪙) {hrs}h ago\n"
            embed.add_field(name="🏆 Recent Completions", value=text, inline=False)

        embed.set_footer(text="Complete challenges to earn bonus points!")
        await interaction.response.send_message(embed=embed)
