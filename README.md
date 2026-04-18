# Astor Discord Bot

Astor is a Discord bot designed for a single guild with a focus on community engagement and gamified interaction. It provides a points-based economy, daily rewards, challenge tracking, a shop system, and weekly event management.

The bot supports administrative controls for managing guild activity, including event lifecycle commands and direct adjustment of user statistics. It is built using Discord bot libraries and includes a web health endpoint for deployment environments.

Primary components:
- Points tracking with persistent user state
- Daily claim system that rewards streaks
- Randomized challenges with progress tracking
- Shop interface for item purchases and perks
- Weekly mode management and event twist handling
- Admin-only commands for configuration and moderation

This repository is structured to separate command registration, event handling, and manager logic, making it easier to maintain and extend the bot’s functionality.