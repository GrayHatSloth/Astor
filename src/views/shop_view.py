# ============================================================
# src/views/shop_view.py — Paginated Shop UI
# ============================================================
# PaginatedShopView displays shop items as buy-buttons with
# pagination.  ShopButton handles purchases; nickname items
# open a NicknameRequestModal instead.
# ============================================================

import discord

from src.views.challenge_view import (
    ChallengeCompleteView,
    build_challenge_completion_embed,
)


# ── Embed builder ───────────────────────────────────────────

def build_shop_embed(shop_manager, user_id: int, page: int, items_per_page: int) -> discord.Embed:
    """Create the shop embed for a given page."""
    total = shop_manager.total_pages(items_per_page)
    embed = discord.Embed(
        title=f"🛒 Astor Shop — Page {page + 1}/{total}",
        description="Purchase items with your points!",
        color=discord.Color.blue(),
    )
    page_items = shop_manager.get_paged_items(page, items_per_page)
    if not page_items:
        embed.description = "No items available right now!"
    else:
        for _item_id, item in page_items:
            stock_text = "∞" if item["stock"] == -1 else str(item["stock"])
            embed.add_field(
                name=f"{item['name']} - {item['price']} points",
                value=f"{item['description']}\nStock: {stock_text}",
                inline=False,
            )

    user_points = shop_manager.bot.points_manager.get_points(user_id)["points"]
    embed.set_footer(text=f"Your points: {user_points} | Page {page + 1}/{total}")
    return embed


# ── Base view with ownership check ─────────────────────────

class ShopView(discord.ui.View):
    def __init__(self, shop_manager, user_id: int):
        super().__init__(timeout=300)
        self.shop_manager = shop_manager
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This shop is not for you!", ephemeral=True)
            return False
        return True


# ── Nickname request modal (for "nickname" type items) ──────

class NicknameRequestModal(discord.ui.Modal, title="Custom Nickname Request"):
    nickname = discord.ui.TextInput(label="Desired Nickname", min_length=1, max_length=32)

    def __init__(self, item_id: str, shop_manager, user_id: int, item_name: str):
        super().__init__()
        self.item_id = item_id
        self.shop_manager = shop_manager
        self.user_id = user_id
        self.item_name = item_name

    async def on_submit(self, interaction: discord.Interaction):
        requested = self.nickname.value.strip()
        success, message, completions = await self.shop_manager.purchase_item(
            self.user_id, self.item_id, requested
        )

        if success:
            embed = discord.Embed(
                title="✅ Purchase Successful!",
                description=(
                    f"You bought **{self.item_name}** and requested "
                    f"the nickname **{requested}**."
                ),
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Purchase Failed",
                description=message,
                color=discord.Color.red(),
            )

        user_points = self.shop_manager.bot.points_manager.get_points(self.user_id)["points"]
        embed.set_footer(text=f"Your points: {user_points}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        if success and completions:
            for comp in completions:
                c_embed = build_challenge_completion_embed(
                    interaction.user, comp["name"], comp["reward"]
                )
                await interaction.followup.send(
                    embed=c_embed,
                    view=ChallengeCompleteView(interaction.user.id),
                    ephemeral=True,
                )


# ── Buy button (one per item) ──────────────────────────────

class ShopButton(discord.ui.Button):
    def __init__(self, item_id: str, item: dict, shop_manager, user_id: int):
        super().__init__(
            label=f"Buy {item['name']}",
            style=discord.ButtonStyle.primary,
            custom_id=f"shop_{item_id}",
        )
        self.item_id = item_id
        self.item = item
        self.shop_manager = shop_manager
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This shop is not for you!", ephemeral=True)
            return

        # Nickname items open a modal instead of buying directly
        if self.item["type"] == "nickname":
            modal = NicknameRequestModal(
                self.item_id, self.shop_manager, self.user_id, self.item["name"]
            )
            await interaction.response.send_modal(modal)
            return

        success, message, completions = await self.shop_manager.purchase_item(
            self.user_id, self.item_id
        )

        if success:
            embed = discord.Embed(
                title="✅ Purchase Successful!",
                description=f"You bought **{self.item['name']}** for {self.item['price']} points!",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Purchase Failed",
                description=message,
                color=discord.Color.red(),
            )

        user_points = self.shop_manager.bot.points_manager.get_points(self.user_id)["points"]
        embed.set_footer(text=f"Your points: {user_points}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        if success and completions:
            for comp in completions:
                c_embed = build_challenge_completion_embed(
                    interaction.user, comp["name"], comp["reward"]
                )
                await interaction.followup.send(
                    embed=c_embed,
                    view=ChallengeCompleteView(interaction.user.id),
                    ephemeral=True,
                )


# ── Pagination buttons ──────────────────────────────────────

class _PrevButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.page > 0:
            self.parent_view.page -= 1
            self.parent_view.update_items()
            await self.parent_view.update_message(interaction)
        else:
            await interaction.response.defer()


class _NextButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        total = self.parent_view.shop_manager.total_pages(self.parent_view.items_per_page)
        if self.parent_view.page + 1 < total:
            self.parent_view.page += 1
            self.parent_view.update_items()
            await self.parent_view.update_message(interaction)
        else:
            await interaction.response.defer()


class _CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.delete()


# ── Paginated shop view (main entry point) ──────────────────

class PaginatedShopView(ShopView):
    """Full shop UI with buy-buttons and page navigation."""

    def __init__(self, shop_manager, user_id: int, page: int = 0):
        super().__init__(shop_manager, user_id)
        self.page = page
        self.items_per_page = 4
        self.update_items()

    def update_items(self):
        self.clear_items()
        page_items = self.shop_manager.get_paged_items(self.page, self.items_per_page)
        for item_id, item in page_items:
            self.add_item(ShopButton(item_id, item, self.shop_manager, self.user_id))
        self.add_item(_PrevButton(self))
        self.add_item(_NextButton(self))
        self.add_item(_CloseButton())

    async def update_message(self, interaction: discord.Interaction):
        embed = build_shop_embed(
            self.shop_manager, self.user_id, self.page, self.items_per_page
        )
        await interaction.response.edit_message(embed=embed, view=self)
