import discord
from discord import app_commands
import json
import os
from datetime import datetime
import asyncio
from dotenv import load_dotenv
import pytz

# Load environment variables from .env file
load_dotenv()

# File for storing data
DATA_FILE = 'workout_data.json'

# Load/save data
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {'goal': None}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

data = load_data()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    print(f'Bot is ready: {client.user}')
    client.loop.create_task(progress_scheduler())

async def progress_scheduler():
    timezone = os.getenv('TIMEZONE', 'America/New_York')  # Default to America/New_York if not set
    tz = pytz.timezone(timezone)
    while True:
        now = datetime.now(tz)
        if now.minute == 0 and now.hour in (12, 20):
            if data['goal']:
                channel = client.get_channel(data['goal']['channel_id'])
                if channel:
                    msg = await build_everyone_daily_message(data['goal'])
                    await channel.send(f"Progress Update:\n{msg}")
        # Date-based reset at midnight
        if data['goal'] and ('last_reset' not in data['goal'] or data['goal']['last_reset'].split(' ')[0] != now.strftime('%Y-%m-%d')):
            goal = data['goal']
            # Reset daily progress and credit
            for user_id in goal['participants']:
                goal['daily_progress'][user_id] = {ex: 0.0 for ex in goal['exercises']}
                goal['daily_credit'][user_id] = 0.0
            goal['last_reset'] = now.strftime('%Y-%m-%d %H:%M:%S')
            save_data(data)
        await asyncio.sleep(60)  # Check every minute

async def build_my_progress_message(goal, user_id):
    try:
        user = await client.fetch_user(int(user_id))
        username = user.name
    except:
        username = f'Unknown User ({user_id})'
    msg = f'Your Progress for "{goal["name"]}":\nRest used: {goal["rest_used"].get(user_id, 0)}/{goal["rest"]} (Completed Days: {goal["completed_days"][user_id]}/{goal["effective_days"]})\n'
    msg += '  Daily Progress:\n'
    for ex, val in goal['daily_progress'][user_id].items():
        display_val = int(val) if val % 1 == 0 else f'{val:.1f}'
        msg += f'    {ex}: {display_val}/{goal["daily_targets"][ex]}\n'
    return msg

async def build_everyone_daily_message(goal):
    msg = f'Goal "{goal["name"]}" Daily Progress:\n'
    for user_id in goal['participants']:
        try:
            user = await client.fetch_user(int(user_id))
            username = user.name
        except:
            username = f'Unknown User ({user_id})'
        msg += f'{username} (Rest used: {goal["rest_used"].get(user_id, 0)}/{goal["rest"]} (Completed Days: {goal["completed_days"][user_id]}/{goal["effective_days"]})) :\n'
        for ex, val in goal['daily_progress'][user_id].items():
            display_val = int(val) if val % 1 == 0 else f'{val:.1f}'
            msg += f'  {ex}: {display_val}/{goal["daily_targets"][ex]}\n'
    return msg

# /create_goal
@tree.command(name='create_goal', description='Create a workout goal with per-day amounts (only if no current goal)')
@app_commands.describe(
    name='Goal name',
    exercises='Comma-separated exercise:daily_amount, e.g., situps:100,pushups:50,squats:50',
    weeks='Number of weeks (5 workout days + 2 rest per week, default 2)'
)
async def create_goal(interaction: discord.Interaction, name: str, exercises: str, weeks: int = 2):
    if data['goal']:
        await interaction.response.send_message('A goal already exists! Delete it first with /delete_goal.', ephemeral=True)
        return
    if weeks < 1:
        await interaction.response.send_message('Weeks must be at least 1!', ephemeral=True)
        return
    exercise_dict = {}
    daily_targets = {}
    for pair in exercises.split(','):
        if ':' in pair:
            ex, daily = pair.split(':')
            ex = ex.strip()
            daily_amount = float(daily.strip())
            daily_targets[ex] = daily_amount
    if not daily_targets:
        await interaction.response.send_message('Add at least one valid exercise:daily_amount pair!', ephemeral=True)
        return
    effective_days = weeks * 5
    rest = weeks * 2
    totals = {ex: daily * effective_days for ex, daily in daily_targets.items()}
    user_id = str(interaction.user.id)
    data['goal'] = {
        'name': name,
        'exercises': totals,
        'daily_targets': daily_targets,
        'effective_days': effective_days,
        'rest': rest,
        'rest_used': {user_id: 0},  # Per-person rest used
        'participants': [user_id],
        'total_progress': {user_id: {ex: 0.0 for ex in totals}},
        'daily_progress': {user_id: {ex: 0.0 for ex in totals}},
        'completed_days': {user_id: 0.0},
        'daily_credit': {user_id: 0.0},
        'channel_id': interaction.channel.id
    }
    save_data(data)
    await interaction.response.send_message(f'Goal "{name}" created! Daily amounts: {", ".join([f"{ex}:{amt}" for ex, amt in daily_targets.items()])}. Total weeks: {weeks}, Effective workout days: {effective_days}. Join with /join_goal.')

# /join_goal
@tree.command(name='join_goal', description='Join the current goal')
async def join_goal(interaction: discord.Interaction):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    user_id = str(interaction.user.id)
    goal = data['goal']
    if user_id in goal['participants']:
        await interaction.response.send_message('Already joined!', ephemeral=True)
        return
    goal['participants'].append(user_id)
    goal['total_progress'][user_id] = {ex: 0.0 for ex in goal['exercises']}
    goal['daily_progress'][user_id] = {ex: 0.0 for ex in goal['exercises']}
    goal['completed_days'][user_id] = 0.0
    goal['daily_credit'][user_id] = 0.0
    goal['rest_used'][user_id] = 0  # Initialize per-person rest used
    save_data(data)
    await interaction.response.send_message(f'Joined "{goal["name"]}"!')

# /record_workout
@tree.command(name='record_workout', description='Record your workout for an exercise')
@app_commands.describe(
    exercise='Exercise name',
    amount='Amount completed'
)
async def record_workout(interaction: discord.Interaction, exercise: str, amount: float):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    user_id = str(interaction.user.id)
    if user_id not in goal['total_progress'] or exercise not in goal['exercises']:
        await interaction.response.send_message('Not joined or invalid exercise!', ephemeral=True)
        return
    if amount < 0:
        await interaction.response.send_message('Amount must be positive!', ephemeral=True)
        return
    # Update daily, cap at daily_target
    current_daily = goal['daily_progress'][user_id][exercise]
    daily_target = goal['daily_targets'][exercise]
    new_daily = min(current_daily + amount, daily_target)
    added_to_daily = new_daily - current_daily
    goal['daily_progress'][user_id][exercise] = new_daily
    # Update total
    current_total = goal['total_progress'][user_id][exercise]
    total = goal['exercises'][exercise]
    new_total = min(current_total + added_to_daily, total)
    goal['total_progress'][user_id][exercise] = new_total
    save_data(data)
    status = 'Completed!' if new_total == total else f'{new_total}/{total}'
    mention = ' '.join([f'<@{uid}>' for uid in goal['participants'] if uid != user_id])
    await interaction.channel.send(f'{interaction.user.name} recorded {exercise}: +{added_to_daily}. Total Progress: {status} for "{goal["name"]}". {mention}')
    await interaction.response.send_message('Workout recorded!', ephemeral=True)

    # Check if all exercises have hit daily goals
    all_completed = all(goal['daily_progress'][user_id][ex] >= goal['daily_targets'][ex] for ex in goal['daily_targets'])
    if all_completed and goal['daily_credit'][user_id] < 1.0:
        # Mark as full day completed
        add_credit = 1.0 - goal['daily_credit'][user_id]
        goal['completed_days'][user_id] += add_credit
        goal['daily_credit'][user_id] = 1.0
        save_data(data)
        await interaction.channel.send(f'{interaction.user.name} has now completed a full workout for the day after recording! {mention}')
        if goal['completed_days'][user_id] >= goal['effective_days']:
            await interaction.channel.send(f'@everyone Congratulations {interaction.user.mention} has completed the goal with {goal["completed_days"][user_id]} days! 🎉🎊🥳')

# /fix_progress
@tree.command(name='fix_progress', description='Fix daily progress for an exercise (corrects count)')
@app_commands.describe(
    exercise='Exercise name',
    new_daily='New daily amount (will adjust total accordingly)'
)
async def fix_progress(interaction: discord.Interaction, exercise: str, new_daily: float):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    user_id = str(interaction.user.id)
    if user_id not in goal['total_progress'] or exercise not in goal['exercises']:
        await interaction.response.send_message('Not joined or invalid exercise!', ephemeral=True)
        return
    if new_daily < 0:
        await interaction.response.send_message('New daily must be non-negative!', ephemeral=True)
        return
    current_daily = goal['daily_progress'][user_id][exercise]
    daily_target = goal['daily_targets'][exercise]
    adjusted_new_daily = min(new_daily, daily_target)
    delta = adjusted_new_daily - current_daily
    goal['daily_progress'][user_id][exercise] = adjusted_new_daily
    # Adjust total
    current_total = goal['total_progress'][user_id][exercise]
    total = goal['exercises'][exercise]
    new_total = max(min(current_total + delta, total), 0.0)
    goal['total_progress'][user_id][exercise] = new_total
    save_data(data)
    status = 'Completed!' if new_total == total else f'{new_total}/{total}'
    await interaction.response.send_message(f'Fixed {exercise} daily to {adjusted_new_daily}. New total: {status}', ephemeral=True)

# /completed_full
@tree.command(name='completed_full', description='Record full workout complete for the day')
async def completed_full(interaction: discord.Interaction):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    user_id = str(interaction.user.id)
    if user_id not in goal['total_progress']:
        await interaction.response.send_message('Not joined!', ephemeral=True)
        return
    current_credit = goal['daily_credit'][user_id]
    if current_credit >= 1.0:
        await interaction.response.send_message('You have already completed a full day today!', ephemeral=True)
        return
    add_credit = 1.0 - current_credit
    for ex in goal['daily_targets']:
        daily_target = goal['daily_targets'][ex]
        # Set daily to max (target)
        current_daily = goal['daily_progress'][user_id][ex]
        new_daily = daily_target
        added_to_daily = new_daily - current_daily
        goal['daily_progress'][user_id][ex] = new_daily
        # Update total
        current_total = goal['total_progress'][user_id][ex]
        total = goal['exercises'][ex]
        new_total = min(current_total + added_to_daily, total)
        goal['total_progress'][user_id][ex] = new_total
    goal['completed_days'][user_id] += add_credit
    goal['daily_credit'][user_id] = 1.0
    save_data(data)
    mention = ' '.join([f'<@{uid}>' for uid in goal['participants'] if uid != user_id])
    await interaction.channel.send(f'{interaction.user.name} completed full workout for the day! {mention}')
    if goal['completed_days'][user_id] >= goal['effective_days']:
        await interaction.channel.send(f'@everyone Congratulations {interaction.user.mention} has completed the goal with {goal["completed_days"][user_id]} days! 🎉🎊🥳')
    await interaction.response.send_message('Full workout recorded!', ephemeral=True)

# /completed_half
@tree.command(name='completed_half', description='Record half workout complete for the day')
async def completed_half(interaction: discord.Interaction):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    user_id = str(interaction.user.id)
    if user_id not in goal['total_progress']:
        await interaction.response.send_message('Not joined!', ephemeral=True)
        return
    current_credit = goal['daily_credit'][user_id]
    if current_credit >= 0.5:
        await interaction.response.send_message('You have already completed at least half today! Use /completed_full if upgrading.', ephemeral=True)
        return
    add_credit = 0.5
    for ex in goal['daily_targets']:
        daily_target = goal['daily_targets'][ex]
        add_amount = daily_target / 2
        # Add to daily, cap at target
        current_daily = goal['daily_progress'][user_id][ex]
        new_daily = min(current_daily + add_amount, daily_target)
        added_to_daily = new_daily - current_daily
        goal['daily_progress'][user_id][ex] = new_daily
        # Add to total
        current_total = goal['total_progress'][user_id][ex]
        total = goal['exercises'][ex]
        new_total = min(current_total + added_to_daily, total)
        goal['total_progress'][user_id][ex] = new_total
    goal['completed_days'][user_id] += add_credit
    goal['daily_credit'][user_id] = 0.5
    save_data(data)
    mention = ' '.join([f'<@{uid}>' for uid in goal['participants'] if uid != user_id])
    await interaction.channel.send(f'{interaction.user.name} completed half workout for the day! {mention}')
    if goal['completed_days'][user_id] >= goal['effective_days']:
        await interaction.channel.send(f'@everyone Congratulations {interaction.user.mention} has completed the goal with {goal["completed_days"][user_id]} days! 🎉🎊🥳')
    await interaction.response.send_message('Half workout recorded!', ephemeral=True)

# /view_progress
@tree.command(name='view_progress', description='View progress for the current goal')
@app_commands.describe(scope='View scope: me or everyone')
@app_commands.choices(scope=[
    app_commands.Choice(name='Me', value='me'),
    app_commands.Choice(name='Everyone', value='everyone')
])
async def view_progress(interaction: discord.Interaction, scope: str):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    user_id = str(interaction.user.id)
    if scope == 'me':
        msg = await build_my_progress_message(goal, user_id)
    elif scope == 'everyone':
        msg = await build_everyone_daily_message(goal)
    else:
        await interaction.response.send_message('Invalid scope! Use me or everyone.', ephemeral=True)
        return
    await interaction.response.send_message(msg, ephemeral=True)

# /view_goal
@tree.command(name='view_goal', description='View the daily goals for the current goal')
async def view_goal(interaction: discord.Interaction):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    msg = f'Current Goal "{goal["name"]}":\nDaily Goals:\n'
    for ex, amt in goal['daily_targets'].items():
        display_amt = int(amt) if amt % 1 == 0 else f'{amt:.1f}'
        msg += f'  {ex}: {display_amt}\n'
    await interaction.response.send_message(msg, ephemeral=True)

# /delete_goal
@tree.command(name='delete_goal', description='Delete the current goal')
async def delete_goal(interaction: discord.Interaction):
    if not data['goal']:
        await interaction.response.send_message('No active goal to delete!', ephemeral=True)
        return
    data['goal'] = None
    save_data(data)
    await interaction.response.send_message('Goal deleted!')

# /list_participants
@tree.command(name='list_participants', description='List who has joined the current goal')
async def list_participants(interaction: discord.Interaction):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    msg = f'Participants in "{goal["name"]}":\n'
    for user_id in goal['participants']:
        try:
            user = await client.fetch_user(int(user_id))
            msg += f'- {user.name}\n'
        except:
            msg += f'- Unknown User ({user_id})\n'
    await interaction.response.send_message(msg, ephemeral=True)

# /claim_rest
@tree.command(name='claim_rest', description='Claim a rest day')
async def claim_rest(interaction: discord.Interaction):
    if not data['goal']:
        await interaction.response.send_message('No active goal!', ephemeral=True)
        return
    goal = data['goal']
    user_id = str(interaction.user.id)
    if user_id not in goal['rest_used']:
        await interaction.response.send_message('Not joined!', ephemeral=True)
        return
    if goal['rest_used'][user_id] >= goal['rest']:
        await interaction.response.send_message(f'No more rest days available for you! You have used {goal["rest_used"][user_id]} out of {goal["rest"]}.', ephemeral=True)
        return
    goal['rest_used'][user_id] += 1
    save_data(data)
    mention = f'{interaction.user.mention} ' + ' '.join([f'<@{uid}>' for uid in goal['participants'] if uid != user_id])
    await interaction.channel.send(f'{interaction.user.name} claimed a rest day! Rest used for {interaction.user.name}: {goal["rest_used"][user_id]}/{goal["rest"]}. {mention}')
    await interaction.response.send_message('Rest day claimed!')

# /change_goal
@tree.command(name='change_goal', description='Modify the current goal\'s daily targets (affects current day and forward)')
@app_commands.describe(
    exercises='Comma-separated exercise:new_daily_target, e.g., situps:50,pushups:25'
)
async def change_goal(interaction: discord.Interaction, exercises: str):
    if not data['goal']:
        await interaction.response.send_message('No active goal to modify!', ephemeral=True)
        return
    goal = data['goal']
    new_daily_targets = {}
    changes_made = False

    for pair in exercises.split(','):
        if ':' in pair:
            ex, new_daily = pair.split(':')
            ex = ex.strip()
            new_daily = float(new_daily.strip())
            if ex in goal['daily_targets']:
                old_daily = goal['daily_targets'][ex]
                if new_daily != old_daily:
                    new_daily_targets[ex] = new_daily
                    changes_made = True

    if not changes_made:
        await interaction.response.send_message('No valid changes detected! Use format exercise:new_daily_target.', ephemeral=True)
        return

    # Apply changes to daily targets only
    for ex, new_daily in new_daily_targets.items():
        goal['daily_targets'][ex] = new_daily

    # Adjust current daily progress for affected exercises
    for user_id in goal['participants']:
        for ex in new_daily_targets:
            current_daily = goal['daily_progress'][user_id][ex]
            new_daily_target = goal['daily_targets'][ex]
            # Update daily progress to reflect new target (keep current progress if below, cap if above)
            if current_daily > new_daily_target:
                goal['daily_progress'][user_id][ex] = new_daily_target
            # No change to total or past days, only daily target affects future capping

    save_data(data)
    changes = ', '.join([f"{ex}: {old_daily} → {new_daily}" for ex, new_daily in new_daily_targets.items()])
    await interaction.response.send_message(f'Goal updated! Changed daily targets: {changes}. Affects current day and forward. Notify participants.', ephemeral=True)
    mention = ' '.join([f'<@{uid}>' for uid in goal['participants']])
    await interaction.channel.send(f'Goal "{goal["name"]}" updated! New daily targets: {changes}. Affects today onward. {mention}')

# Run the bot with the token from the .env file
client.run(os.getenv('DISCORD_TOKEN'))
