# ============================================================
# src/commands/economy/shop_commands.py — Shop Slash Commands
# ============================================================
# /shop — browse and buy items (paginated with buttons)
# ============================================================

import discord

from config import Config
from src.views.shop_view import PaginatedShopView, build_shop_embed


async def setup(bot, shop_manager):
    """Register shop commands on the bot tree."""

    @bot.tree.command(
        name="shop",
        description="Browse and purchase items from the shop",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def shop_cmd(interaction: discord.Interaction):
        view  = PaginatedShopView(shop_manager, interaction.user.id)
        embed = build_shop_embed(shop_manager, interaction.user.id, view.page, view.items_per_page)
        await interaction.response.send_message(embed=embed, view=view)
