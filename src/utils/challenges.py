# ============================================================
# src/utils/challenges.py — Challenge Definitions
# ============================================================
# Static data for normal and event challenges.
# Separated so managers and commands can share them cleanly.
# ============================================================

# Normal challenges — earned through everyday activity
NORMAL_CHALLENGES = [
    {"id": "chat_50",    "name": "Chatty Cathy",      "description": "Send 50 messages in any channel",              "reward": 25,  "target": 50,  "type": "messages"},
    {"id": "react_10",   "name": "Reaction Master",    "description": "Add 10 reactions to messages",                 "reward": 20,  "target": 10,  "type": "reactions"},
    {"id": "mention_5",  "name": "Social Butterfly",   "description": "Mention 5 different users in messages",        "reward": 15,  "target": 5,   "type": "mentions"},
    {"id": "emoji_20",   "name": "Emoji Enthusiast",   "description": "Use 20 different emojis in messages",          "reward": 30,  "target": 20,  "type": "emojis"},
    {"id": "voice_30",   "name": "Voice Veteran",      "description": "Spend 30 minutes in voice channels",           "reward": 40,  "target": 30,  "type": "voice_minutes"},
    {"id": "invite_2",   "name": "Community Builder",  "description": "Invite 2 new members to the server",           "reward": 50,  "target": 2,   "type": "invites"},
    {"id": "sticker_5",  "name": "Sticker Collector",  "description": "Use 5 different stickers",                     "reward": 25,  "target": 5,   "type": "stickers"},
    {"id": "thread_3",   "name": "Thread Weaver",      "description": "Create or participate in 3 different threads",  "reward": 20,  "target": 3,   "type": "threads"},
]

# Event challenges — tied to weekly modes or shop activity
EVENT_CHALLENGES = [
    {"id": "weekly_win",       "name": "Weekly Champion",  "description": "Win a weekly mode competition",        "reward": 100, "target": 1,   "type": "weekly_win"},
    {"id": "shop_purchase",    "name": "Shopaholic",       "description": "Make a purchase in the shop",           "reward": 75,  "target": 1,   "type": "shop_purchase"},
    {"id": "daily_streak_7",   "name": "Daily Devotee",    "description": "Maintain a 7-day daily login streak",   "reward": 60,  "target": 7,   "type": "daily_streak"},
    {"id": "button_click_100", "name": "Button Masher",    "description": "Click the chaos button 100 times",      "reward": 80,  "target": 100, "type": "button_clicks"},
    {"id": "role_request",     "name": "Role Seeker",      "description": "Request a custom role through the shop", "reward": 90,  "target": 1,   "type": "role_request"},
    {"id": "leaderboard_top10","name": "Rising Star",      "description": "Reach top 10 on the leaderboard",       "reward": 70,  "target": 1,   "type": "leaderboard_rank"},
]

# Points awarded for each weekly-mode win
MODE_POINTS = {
    "invite_comp":        50,
    "debate":             30,
    "movie_night":        10,
    "profile_comp":       40,
    "button_frenzy":      20,
    "button_frenzy_click": 1,
    "mystery":            25,
    "weekly_twist":       35,
}
