# ============================================================
# src/commands/utility/utility_commands.py — General Utility Commands
# ============================================================
# /botstatus — show PID, latency, guild, and session info
# ============================================================

import datetime
import os
import time

import discord

from config import Config


async def setup(bot):
    """Register utility slash commands on the bot tree."""

    @bot.tree.command(
        name="timeouttoken",
        description="Use a timeout token to mute another member for 5 minutes",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    @discord.app_commands.describe(target="The member to timeout")
    async def timeout_token(interaction: discord.Interaction, target: discord.Member):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        shop_manager = interaction.client.shop_manager
        if not shop_manager.has_timeout_token(interaction.user.id):
            await interaction.response.send_message(
                "You do not own a timeout token. Purchase one from the shop first.",
                ephemeral=True,
            )
            return

        now = int(datetime.datetime.utcnow().timestamp())
        last_use = shop_manager.get_last_timeout_use(interaction.user.id)
        cooldown = 3600
        if last_use and now - last_use < cooldown:
            remaining = cooldown - (now - last_use)
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(
                f"You can use another timeout token in {minutes}m {seconds}s.",
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.get_member(interaction.client.user.id)
        if not bot_member or not bot_member.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "I need the Moderate Members permission to use timeout tokens.",
                ephemeral=True,
            )
            return

        if target.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot timeout yourself with a timeout token.",
                ephemeral=True,
            )
            return

        if target.bot:
            await interaction.response.send_message(
                "You cannot target bots with a timeout token.",
                ephemeral=True,
            )
            return

        if getattr(target, "timed_out_until", None) and target.timed_out_until > datetime.datetime.now(datetime.timezone.utc):
            await interaction.response.send_message(
                "That member is already timed out.",
                ephemeral=True,
            )
            return

        timeout_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
        try:
            await target.timeout(
                timeout_until,
                reason=f"{interaction.user.display_name} used a timeout token on you!",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I cannot timeout that member. Check my role position and permissions.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.response.send_message(
                f"Could not timeout the member: {exc}",
                ephemeral=True,
            )
            return

        shop_manager.consume_owned_item(interaction.user.id, "timeout_token")
        shop_manager.record_timeout_use(interaction.user.id)

        await interaction.response.send_message(
            f"{target.mention} has been timed out for 5 minutes.",
            ephemeral=True,
        )

    @bot.tree.command(
        name="inventory",
        description="View your owned shop items",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def inventory(interaction: discord.Interaction):
        shop_manager = interaction.client.shop_manager
        owned = shop_manager.data.get("owned_items", {}).get(str(interaction.user.id), {})

        if not owned:
            await interaction.response.send_message(
                "You do not own any shop items right now.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🧾 Your Shop Inventory",
            description="Items you currently own from the shop",
            color=discord.Color.blue(),
        )

        for item_id, count in owned.items():
            item = shop_manager.get_item(item_id)
            name = item["name"] if item else item_id
            embed.add_field(name=name, value=f"Quantity: {count}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @bot.tree.command(
        name="state",
        description="Show the current weekly mode, twist, and active enforcement",
        guild=discord.Object(id=Config.GUILD_ID),
    )
    async def state(interaction: discord.Interaction):
        mm = interaction.client.mode_manager
        tm = interaction.client.weekly_twist_manager
        em = interaction.client.effect_manager

        embed = discord.Embed(title="Bot State", color=discord.Color.blurple())

        # ── Weekly mode ──────────────────────────────────────────
        mode = mm.active_mode
        if mode:
            mode_type = mode["type"].replace("_", " ").title()
            detail    = ""
            if mode["type"] == "debate":
                detail = f"\nTopic: **{mode.get('topic', '?')}**"
            elif mode["type"] == "profile_comp":
                detail = f"\nCategory: **{mode.get('category', '?').upper()}**"
            elif mode["type"] == "mystery":
                day   = mode.get("current_day", -1) + 1
                total = len(mode.get("mysteries", []))
                solved = mode.get("solved", True)
                status = "Solved" if solved else "Active — guesses open"
                detail = f"\nDay **{day}/{total}** — {status}"
            elif mode["type"] == "button_frenzy":
                clicks = mode.get("clicks", {})
                detail = f"\nTotal button presses: **{sum(clicks.values())}**"
            embed.add_field(name="Weekly Mode", value=f"**{mode_type}**{detail}", inline=False)
        else:
            embed.add_field(name="Weekly Mode", value="None active", inline=False)

        # ── Weekly twist ─────────────────────────────────────────
        twist = tm.active_twist
        if twist:
            twist_label = twist["type"].replace("_", " ").title()
            if twist["type"] == "first_to_x":
                twist_label += f" ({tm.first_to_x_target} messages)"
            embed.add_field(name="Weekly Twist", value=f"**{twist_label}**", inline=False)
        elif tm.pending_twist:
            embed.add_field(name="Weekly Twist", value="Pending (button not yet clicked)", inline=False)
        else:
            embed.add_field(name="Weekly Twist", value="None active", inline=False)

        # ── Active chaos effect ───────────────────────────────────
        effect = em.active_effect
        if effect and em.effect_end_time:
            remaining_secs = max(0, int(em.effect_end_time - time.time()))
            mins, secs     = divmod(remaining_secs, 60)
            effect_label   = effect["type"].replace("_", " ").title()
            if effect["type"] == "must_include":
                effect_label += f" '{effect.get('word', '')}'"
            elif effect["type"] == "max_words":
                effect_label += f" ({effect.get('limit', '?')} words)"
            elif effect["type"] == "no_letter":
                effect_label += f" '{effect.get('letter', '')}'"
            embed.add_field(
                name="Chaos Effect",
                value=f"**{effect_label}** — expires in {mins}m {secs}s",
                inline=False,
            )
        else:
            embed.add_field(name="Chaos Effect", value="None active", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
