# Astor Discord Bot

This repo is now configured for Render deployment via GitHub.

## What changed
- Added a small Flask health endpoint in `bot.py` so Render can run a web service.
- Added `Flask` to `requirements.txt`.
- Added `.gitignore` to keep secrets and runtime files out of Git.
- Added `render.yaml` for Render web service configuration.
- Added `.env.example` to document required local environment variables.

## Local development
1. Copy `.env.example` to `.env`.
2. Fill in `DISCORD_BOT_TOKEN` and optionally `GUILD_ID`.
3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Run locally:
   ```bash
   python bot.py
   ```
5. Visit `http://localhost:5000/` to confirm the health endpoint responds.

## GitHub + Render setup
1. Create a GitHub repository for this project.
2. Initialize Git, commit, and push the repo:
   ```bash
   git init
   git add .
   git commit -m "Render-ready Discord bot"
   git branch -M main
   git remote add origin <YOUR_GITHUB_REPO_URL>
   git push -u origin main
   ```
3. On Render, create a new **Web Service** from your GitHub repo.
4. Set the build command to:
   ```bash
   pip install -r requirements.txt
   ```
5. Set the start command to:
   ```bash
   python bot.py
   ```
6. Add Render environment variables:
   - `DISCORD_BOT_TOKEN`
   - `GUILD_ID`
7. Deploy.

## Render notes
- Render exposes the app on a public URL and requires a web service.
- The Flask endpoint at `/` is used for health checks and uptime pings.
- `UptimeRobot` can ping the Render URL every 5 minutes if you want external keep-alive monitoring.

## Important
- Do not commit `.env` with secrets.
- Render environment variables are the correct place for production tokens.
- `data/points.json` is ignored because runtime state should not be committed.
