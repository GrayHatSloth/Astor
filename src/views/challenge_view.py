# ============================================================
# src/views/challenge_view.py — Challenge Completion UI
# ============================================================
# Embed builder and button view shown when a user completes
# a challenge (inline notification with a "View Challenges" hint).
# ============================================================

import discord


def build_challenge_completion_embed(
    user: discord.User, challenge_name: str, reward: int
) -> discord.Embed:
    """Build the embed shown when a user finishes a challenge."""
    embed = discord.Embed(
        title="🎉 Challenge Completed!",
        description=f"**{challenge_name}** is complete!",
        color=discord.Color.green(),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="🏅 Reward", value=f"**{reward}** points", inline=True)
    embed.add_field(
        name="📌 Next Step",
        value="Use `/trackchallenges` to view your next challenge.",
        inline=False,
    )
    embed.set_footer(text="Great work! Keep completing challenges for bonus points.")
    return embed


class ChallengeCompleteView(discord.ui.View):
    """Attached to challenge-completion messages — lets user see their challenges."""

    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label="View Challenges", style=discord.ButtonStyle.primary)
    async def view_challenges(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your challenge notification.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Use `/trackchallenges` to see your current and completed challenges.",
            ephemeral=True,
        )


class ChallengeRerollView(discord.ui.View):
    """View shown when a user can choose to reroll an active challenge."""

    def __init__(self, user_id: int, challenge_type: str, points_manager, cost: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.challenge_type = challenge_type
        self.points_manager = points_manager
        self.cost = cost
        self.reroll_button.label = (
            "Reroll (Free)" if cost == 0 else f"Reroll ({cost} points)"
        )

    def disable_all_items(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your reroll prompt.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.primary)
    async def reroll_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        success, result, cost = self.points_manager.reroll_challenge(
            interaction.user.id, self.challenge_type
        )
        if not success:
            await interaction.response.send_message(result, ephemeral=True)
            return

        self.disable_all_items()
        embed = discord.Embed(
            title="🎲 Challenge Rerolled!",
            description=f"**{result['name']}**\n{result['description']}",
            color=discord.Color.green(),
        )
        embed.add_field(name="🎁 Reward", value=f"**{result['reward']}** 🪙", inline=True)
        embed.add_field(name="🎯 Progress", value=f"**0/{result['target']}**", inline=True)
        embed.add_field(name="📊 Type", value=result["type"].replace("_", " ").title(), inline=True)
        embed.set_footer(
            text=(
                "Your first reroll was free!"
                if cost == 0
                else f"{cost} points were deducted for this reroll."
            )
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Keep Current", style=discord.ButtonStyle.secondary)
    async def keep_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.disable_all_items()
        await interaction.response.edit_message(
            content="Keeping your current challenge.",
            view=self,
        )
