# Workout Tracker Bot

This Discord bot helps groups set shared workout goals, track progress, claim rest days (per person), and get notifications. It runs in Docker and uses a configurable .env file for the Discord token and timezone.

## Setup Instructions
### 1. Clone the Repository
- Install Git: `sudo apt update && sudo apt install git`
- Clone:
  `git clone https://github.com/moviemakr1620/FitBot.git`
  `cd FitBot`

### 2. Install Docker and Docker Compose
- Docker: `sudo apt update && sudo apt install docker.io`
- Docker Compose: `sudo apt install docker-compose`
- Start Docker: `sudo systemctl start docker && sudo systemctl enable docker`

### 3. Configure
- Copy the example .env file and rename it:
  `cp .env.example .env`
- Edit .env:
  DISCORD_TOKEN=your_discord_bot_token_here
  TIMEZONE=America/New_York
- **Get a Discord Token**:
  - Go to [discord.com/developers](https://discord.com/developers).
  - Create a new application.
  - Go to Bot > Add Bot > Copy Token (keep it secret!).
  - Enable Intents: Message Content in Bot settings.
  - Go to OAuth2 > URL Generator, select bot and applications.commands scopes, add Read/Send Messages and Embed Links permissions, and use the generated URL to invite the bot to your server.

- (Optional) If using a backup, copy workout_data.json into the directory; otherwise, it will be auto-generated on first run.

### 4. Build and Run
- Using Docker Compose:
  `docker-compose up -d --build`
- Logs: `docker-compose logs -f`
- Stop: `docker-compose down`

### 5. Updating the Bot
- Pull updates from GitHub:
  `git pull`
- Rebuild and redeploy:
  `docker-compose up -d --build`
- Check logs for errors.

## User Guide
### Getting Started
- Invite the bot to your server using the OAuth2 URL.
- Use a channel (e.g., #workout-tracker) for commands.
- Reset: Daily at midnight in the configured timezone (default EDT).
- Rest Days: Per person (2 per week).
- Decimals: Shown for fractional amounts (e.g., 2.5 minutes).

### Commands
- /create_goal: Create a goal. Params: name, exercises (e.g., "situps:100,pushups:50"), weeks (default 2).
- /join_goal: Join the current goal.
- /record_workout: Log exercise. Params: exercise, amount (supports decimals).
- /fix_progress: Correct daily progress. Params: exercise, new_daily.
- /completed_full: Mark full day (adds 1 to completed days).
- /completed_half: Mark half day (adds 0.5).
- /view_progress: View daily totals. Scope: me or everyone. Shows rest used and completed days.
- /view_goal: View daily targets (private).
- /delete_goal: Delete the current goal.
- /list_participants: List users (private).
- /claim_rest: Claim a rest day (per person).
- /change_goal: Change daily targets. Params: exercises (e.g., "situps:50,pushups:25").

### Features
- Per-person rest days (claim with /claim_rest).
- Daily reset at midnight in the configured timezone.
- Decimal support for time-based workouts (e.g., 2.5 minutes).
- Completed days shown in /view_progress.
- Notifications ping participants.

### Troubleshooting
- Offline: Check Docker with docker ps.
- Errors: View logs with docker-compose logs.
- Time: Ensure TIMEZONE in .env is valid (e.g., America/New_York).
- Data: Edit workout_data.json carefully, back up before changes.

Stay fit! 💪
