# ============================================================
# src/commands/admin/admin_commands.py — Admin-Only Slash Commands
# ============================================================
# Shop management:  /add_shop_item, /remove_shop_item,
#   /set_role_id, /set_channel_access, /list_shop_items,
#   /set_shop_stock, /toggle_shop_item
# Nickname management: /list_nickname_requests,
#   /approve_nickname, /deny_nickname
# ============================================================

import discord
from discord import app_commands

from config import Config
from src.views.challenge_view import ChallengeCompleteView, build_challenge_completion_embed


# ── Autocomplete Helpers ────────────────────────────────────

async def _role_item_autocomplete(interaction: discord.Interaction, current: str):
    """Suggest role-type shop items."""
    sm = interaction.client.shop_manager
    items = [(iid, it["name"]) for iid, it in sm.items.items() if it.get("type") in ("role", "vip_package")]
    return [
        app_commands.Choice(name=f"{name} ({iid})", value=iid)
        for iid, name in items
        if current.lower() in iid.lower() or current.lower() in name.lower()
    ][:25]


async def _channel_item_autocomplete(interaction: discord.Interaction, current: str):
    """Suggest channel_access-type shop items."""
    sm = interaction.client.shop_manager
    items = [(iid, it["name"]) for iid, it in sm.items.items() if it.get("type") in ("channel_access", "vip_package")]
    return [
        app_commands.Choice(name=f"{name} ({iid})", value=iid)
        for iid, name in items
        if current.lower() in iid.lower() or current.lower() in name.lower()
    ][:25]


async def _all_item_autocomplete(interaction: discord.Interaction, current: str):
    """Suggest any shop item."""
    sm = interaction.client.shop_manager
    return [
        app_commands.Choice(name=f"{it['name']} ({iid})", value=iid)
        for iid, it in sm.items.items()
        if current.lower() in iid.lower() or current.lower() in it.get("name", "").lower()
    ][:25]


# ── Registration ────────────────────────────────────────────

async def setup(bot, shop_manager):
    """Register all admin slash commands on the bot tree."""

    # ── /add_shop_item ──────────────────────────────────────

    @bot.tree.command(
        name="add_shop_item",
        description="Add a new item to the shop (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(
        item_id="Unique ID for the item",
        name="Display name",
        description="What the item does",
        price="Price in points",
        item_type="Type (role, nickname, booster, emoji, color_role)",
    )
    async def add_item_cmd(interaction: discord.Interaction, item_id: str, name: str,
                           description: str, price: int, item_type: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        if item_id in shop_manager.items:
            await interaction.response.send_message("❌ Item ID already exists!", ephemeral=True)
            return

        shop_manager.items[item_id] = {
            "name": name, "description": description,
            "price": price, "type": item_type,
            "stock": -1, "enabled": True,
        }
        shop_manager.save_shop()
        await interaction.response.send_message(f"✅ Added item: {name}", ephemeral=True)

    # ── /remove_shop_item ───────────────────────────────────

    @bot.tree.command(
        name="remove_shop_item",
        description="Remove an item from the shop (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(item_id="ID of the item to remove")
    @app_commands.autocomplete(item_id=_all_item_autocomplete)
    async def remove_item_cmd(interaction: discord.Interaction, item_id: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        if item_id not in shop_manager.items:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        del shop_manager.items[item_id]
        shop_manager.save_shop()
        await interaction.response.send_message(f"✅ Removed item: {item_id}", ephemeral=True)

    # ── /set_role_id ────────────────────────────────────────

    @bot.tree.command(
        name="set_role_id",
        description="Set the role for a role-type shop item (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(item_id="Role item ID", role="The role to assign")
    @app_commands.autocomplete(item_id=_role_item_autocomplete)
    async def set_role_cmd(interaction: discord.Interaction, item_id: str, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        if item_id not in shop_manager.items:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        if shop_manager.items[item_id]["type"] not in ("role", "vip_package"):
            await interaction.response.send_message("❌ This item is not a role type!", ephemeral=True)
            return
        shop_manager.items[item_id]["role_id"] = role.id
        shop_manager.save_shop()
        await interaction.response.send_message(f"✅ Set role for {item_id} to {role.name}", ephemeral=True)

    # ── /set_channel_access ─────────────────────────────────

    @bot.tree.command(
        name="set_channel_access",
        description="Set the channel for channel-access shop items (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(item_id="Channel access item ID", channel="The channel to grant access to")
    @app_commands.autocomplete(item_id=_channel_item_autocomplete)
    async def set_channel_cmd(interaction: discord.Interaction, item_id: str, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        if item_id not in shop_manager.items:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        if shop_manager.items[item_id]["type"] not in ("channel_access", "vip_package"):
            await interaction.response.send_message("❌ This item is not a channel access type!", ephemeral=True)
            return
        shop_manager.items[item_id]["channel_id"] = channel.id
        shop_manager.save_shop()
        await interaction.response.send_message(f"✅ Set channel for {item_id} to {channel.mention}", ephemeral=True)

    # ── /list_shop_items ────────────────────────────────────

    @bot.tree.command(
        name="list_shop_items",
        description="List all shop items and config (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def list_items_cmd(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        embed = discord.Embed(title="🛒 Shop Items Configuration", color=discord.Color.blue())

        if not shop_manager.items:
            embed.description = "No items configured!"
        else:
            for iid, item in shop_manager.items.items():
                status = "✅ Enabled" if item.get("enabled") else "❌ Disabled"
                stock  = "∞" if item["stock"] == -1 else str(item["stock"])
                info   = f"Price: {item['price']} | Stock: {stock} | {status}"

                if item["type"] in ("role",) and item.get("role_id"):
                    role = interaction.guild.get_role(item["role_id"])
                    info += f"\nRole: {role.name if role else 'Not set'}"

                if item["type"] == "vip_package":
                    if item.get("role_id"):
                        role = interaction.guild.get_role(item["role_id"])
                        info += f"\nRole: {role.name if role else 'Not set'}"
                    if item.get("channel_id"):
                        ch = interaction.guild.get_channel(item["channel_id"])
                        info += f", Channel: {ch.mention if ch else 'Not set'}"

                embed.add_field(
                    name=f"{item['name']} ({iid})",
                    value=f"**{item['description']}**\n{info}",
                    inline=False,
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /list_nickname_requests ─────────────────────────────

    @bot.tree.command(
        name="list_nickname_requests",
        description="List pending nickname requests (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def list_nicks(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return

        reqs = shop_manager.data.get("nickname_requests", {})
        if not reqs:
            await interaction.response.send_message("✅ No pending nickname requests.", ephemeral=True)
            return

        embed = discord.Embed(title="📝 Nickname Requests", color=discord.Color.blue())
        for uid, req in reqs.items():
            member = interaction.guild.get_member(int(uid))
            name   = member.display_name if member else f"Unknown ({uid})"
            nick   = req.get("requested_nickname") or "(not set yet)"
            embed.add_field(name=name, value=f"Nickname: {nick}\nStatus: {req.get('status', 'pending')}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /approve_nickname ───────────────────────────────────

    @bot.tree.command(
        name="approve_nickname",
        description="Approve a pending nickname request (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(user="The user whose nickname to approve")
    async def approve_nick(interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        req = shop_manager.data.get("nickname_requests", {}).get(str(user.id))
        if not req:
            await interaction.response.send_message("❌ No pending request for that user.", ephemeral=True)
            return
        nick = req.get("requested_nickname")
        if not nick:
            await interaction.response.send_message("❌ Request has no nickname set yet.", ephemeral=True)
            return
        try:
            await user.edit(nick=nick)
            req["status"] = "approved"
            shop_manager.save_data()
            await interaction.response.send_message(f"✅ Nickname set to {nick}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to set nickname: {e}", ephemeral=True)

    # ── /deny_nickname ──────────────────────────────────────

    @bot.tree.command(
        name="deny_nickname",
        description="Deny a pending nickname request (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(user="The user whose request to deny")
    async def deny_nick(interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        req = shop_manager.data.get("nickname_requests", {}).get(str(user.id))
        if not req:
            await interaction.response.send_message("❌ No pending request for that user.", ephemeral=True)
            return
        req["status"] = "denied"
        shop_manager.save_data()
        await interaction.response.send_message(f"✅ Denied nickname request for {user.display_name}", ephemeral=True)

    # ── /set_shop_stock ─────────────────────────────────────

    @bot.tree.command(
        name="set_shop_stock",
        description="Set stock for a shop item (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(item_id="Item ID", stock="New stock (-1 for unlimited)")
    @app_commands.autocomplete(item_id=_all_item_autocomplete)
    async def set_stock(interaction: discord.Interaction, item_id: str, stock: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        if item_id not in shop_manager.items:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        shop_manager.items[item_id]["stock"] = stock
        shop_manager.save_shop()
        await interaction.response.send_message(f"✅ Set stock for {item_id} to {stock}", ephemeral=True)

    # ── /toggle_shop_item ───────────────────────────────────

    @bot.tree.command(
        name="toggle_shop_item",
        description="Enable or disable a shop item (Admin only)",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @app_commands.describe(item_id="Item ID to toggle")
    @app_commands.autocomplete(item_id=_all_item_autocomplete)
    async def toggle_item(interaction: discord.Interaction, item_id: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
        if item_id not in shop_manager.items:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        shop_manager.items[item_id]["enabled"] = not shop_manager.items[item_id].get("enabled", False)
        shop_manager.save_shop()
        state = "enabled" if shop_manager.items[item_id]["enabled"] else "disabled"
        await interaction.response.send_message(f"✅ {item_id} is now {state}", ephemeral=True)
