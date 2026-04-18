# ============================================================
# src/views/leaderboard_view.py — Paginated Leaderboard UI
# ============================================================
# LeaderboardView with Previous / Next / Refresh / Close
# buttons.  Creates and updates the leaderboard embed.
# ============================================================

import discord


# ── Pagination buttons ──────────────────────────────────────

class PreviousPageButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.page > 0:
            self.parent_view.page -= 1
            await self.parent_view.update_message(interaction)
        else:
            await interaction.response.defer()


class NextPageButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        top = self.parent_view.points_manager.leaderboard()
        total_pages = (len(top) + self.parent_view.per_page - 1) // self.parent_view.per_page
        if self.parent_view.page + 1 < total_pages:
            self.parent_view.page += 1
            await self.parent_view.update_message(interaction)
        else:
            await interaction.response.defer()


class RefreshLeaderboardButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="🔄 Refresh", style=discord.ButtonStyle.primary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.points_manager.invalidate_leaderboard_cache()
        await self.parent_view.update_message(interaction)


class CloseLeaderboardButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="❌ Close", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.delete()


# ── Main view ───────────────────────────────────────────────

class LeaderboardView(discord.ui.View):
    """Paginated leaderboard with navigation buttons."""

    def __init__(self, points_manager, user_id: int, bot=None):
        super().__init__(timeout=300)
        self.points_manager = points_manager
        self.user_id = user_id
        self.bot = bot
        self.page = 0
        self.per_page = 10
        self.update_buttons()

    # Rebuild button row based on current page
    def update_buttons(self):
        self.clear_items()
        top = self.points_manager.leaderboard()
        total_pages = (len(top) + self.per_page - 1) // self.per_page
        if self.page > 0:
            self.add_item(PreviousPageButton(self))
        if self.page + 1 < total_pages:
            self.add_item(NextPageButton(self))
        self.add_item(RefreshLeaderboardButton(self))
        self.add_item(CloseLeaderboardButton())

    # Build the embed for the current page
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Points Leaderboard",
            description="Top players by total points earned",
            color=discord.Color.gold(),
        )
        top = self.points_manager.leaderboard()
        if not top:
            embed.description = (
                "No points yet! Start participating in weekly modes to earn points!"
            )
            embed.set_footer(text="Be the first to earn some points! 🎯")
            return embed

        start = self.page * self.per_page
        end = start + self.per_page
        page_entries = top[start:end]

        medals = {1: "🥇 ", 2: "🥈 ", 3: "🥉 "}
        lines = []
        for i, (uid, stats) in enumerate(page_entries, start + 1):
            medal = medals.get(i, "")
            lines.append(
                f"{medal}**#{i}** <@{uid}> — **{stats['points']}** 🪙 "
                f"(**{stats['wins']}** wins)"
            )

        embed.add_field(
            name="📊 Rankings",
            value="\n".join(lines) or "No entries on this page",
            inline=False,
        )

        total_pages = (len(top) + self.per_page - 1) // self.per_page
        total_points = sum(s["points"] for _, s in top)
        total_wins = sum(s["wins"] for _, s in top)
        embed.add_field(
            name="📈 Statistics",
            value=(
                f"**Total Players:** {len(top)}\n"
                f"**Total Points:** {total_points} 🪙\n"
                f"**Total Wins:** {total_wins} 🏆"
            ),
            inline=True,
        )

        # Show the invoker's rank
        user_rank = None
        for rank, (uid, _) in enumerate(top, 1):
            if uid == str(self.user_id):
                user_rank = rank
                break
        if user_rank and user_rank <= 50:
            embed.add_field(
                name="🎯 Your Rank", value=f"You're **#{user_rank}**!", inline=True
            )
        elif user_rank:
            embed.add_field(
                name="🎯 Your Rank",
                value=f"You're **#{user_rank}** (not shown on this page)",
                inline=True,
            )

        embed.set_footer(text=f"Page {self.page + 1}/{total_pages} • Updated just now")
        return embed

    async def update_message(self, interaction: discord.Interaction):
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
