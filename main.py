import discord
from discord.ext import commands
import datetime
import json
import os
import asyncio
import aiohttp

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TOKEN          = os.environ["API_KEY"]
LOG_CHANNEL_ID = 1532239804719173737
DATA_FILE      = "bot_state.json"

# ─── INTENTS ───────────────────────────────────────────────────────────────────
intents                 = discord.Intents.all()
intents.message_content = True

bot            = commands.Bot(command_prefix="-", intents=intents)
bot.start_time = datetime.datetime.now(datetime.timezone.utc)

# ─── STATE HELPERS ─────────────────────────────────────────────────────────────
def save_state(start_time: datetime.datetime):
    with open(DATA_FILE, 'w') as f:
        json.dump({'last_start': start_time.isoformat()}, f)

def get_last_uptime() -> datetime.timedelta | None:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data       = json.load(f)
                last_start = datetime.datetime.fromisoformat(data['last_start'])
                return datetime.datetime.now(datetime.timezone.utc) - last_start
        except Exception:
            return None
    return None

def format_duration(td: datetime.timedelta) -> str:
    days         = td.days
    hours, rem   = divmod(int(td.total_seconds()), 3600)
    minutes, sec = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m {sec}s"

# ─── COG LOADER ────────────────────────────────────────────────────────────────
async def load_extensions():
    if not os.path.exists('./cogs'):
        os.makedirs('./cogs')
        print("📁 Created missing 'cogs' folder.")

    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Loaded: cogs.{filename[:-3]}')
            except Exception as e:
                print(f'❌ Failed to load cogs.{filename[:-3]}: {e}')

# ─── EVENTS ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f'✅ Bot is live as {bot.user.name}')

    synced_count = 0
    try:
        synced       = await bot.tree.sync()
        synced_count = len(synced)
        print(f"🔄 Synced {synced_count} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    prev_uptime = get_last_uptime()
    prev_str    = format_duration(prev_uptime) if prev_uptime else "Unknown (First Start)"
    save_state(bot.start_time)


@bot.event
async def on_disconnect():
    print("Bot has disconnected from Discord.")

# ─── PING COMMAND ──────────────────────────────────────────────────────────────
@bot.command()
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    await ctx.reply(f"Average latency is **{latency}ms.**")

# ─── STARTUP ───────────────────────────────────────────────────────────────────
async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is shutting down…")
    except Exception as e:
        print(f"Error occurred: {e}")