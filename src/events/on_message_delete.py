# ============================================================
# src/events/on_message_delete.py — Deleted Message Sniper Cache
# ============================================================
# Stores the last 50 deleted messages so a.snipe can recall them.
# ============================================================

import datetime


def setup(bot):
    """Register the on_message_delete event."""

    @bot.event
    async def on_message_delete(message):
        if not message or message.author.bot:
            return

        bot.deleted_messages.append({
            "content":      message.content,
            "author_name":  str(message.author),
            "author_id":    message.author.id,
            "channel_id":   message.channel.id if message.channel else None,
            "channel_name": getattr(message.channel, "name", "unknown"),
            "created_at":   message.created_at.isoformat() if message.created_at else None,
            "deleted_at":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "attachments":  [a.url for a in message.attachments],
            "embeds":       [e.to_dict() for e in message.embeds] if message.embeds else [],
        })

        # Keep only the most recent 50
        if len(bot.deleted_messages) > 50:
            bot.deleted_messages.pop(0)
