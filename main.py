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
BOT_PREFIX     = os.environ.get("BOT_PREFIX", "-")
DATA_FILE      = "bot_state.json"

# ─── INTENTS ───────────────────────────────────────────────────────────────────
intents                 = discord.Intents.all()
intents.message_content = True

bot            = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)
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

    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        async with aiohttp.ClientSession() as session:
            token = bot.http.token
            # Send the plain text ping as a separate message first
            async with session.post(
                f"https://discord.com/api/v10/channels/{LOG_CHANNEL_ID}/messages",
                headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
                json={"content": "<@703059363312697404> The bot is back online."},
            ) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    print(f"❌ Failed to send ping message: {resp.status}: {text}")
            payload = {
                "flags": 32768,
                "components": [
                    {
                        "type": 17,
                        "components": [
                            {
                                "type": 10,
                                "content": "**Service Status**\n-# The bot has restarted and is now operational."
                            },
                            {"type": 14, "spacing": 1},
                            {
                                "type": 1,
                                "components": [
                                    {
                                        "style": 2, "type": 2,
                                        "label": f"Latency: {round(bot.latency * 1000)}ms",
                                        "custom_id": "status_latency",
                                        "disabled": True
                                    },
                                    {
                                        "style": 2, "type": 2,
                                        "label": f"{synced_count} commands synced",
                                        "custom_id": "status_synced",
                                        "disabled": True
                                    },
                                    {
                                        "style": 2, "type": 2,
                                        "label": f"Previous uptime: {prev_str}",
                                        "custom_id": "status_uptime",
                                        "disabled": True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            async with session.post(
                f"https://discord.com/api/v10/channels/{LOG_CHANNEL_ID}/messages",
                headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    print(f"❌ Failed to send online status: {resp.status}: {text}")


@bot.event
async def on_disconnect():
    print("Bot has disconnected from Discord.")

# ─── PING COMMAND ──────────────────────────────────────────────────────────────
@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    await ctx.reply(f"Average latency is **{latency}ms.**")

@ping.error
async def ping_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"You are on cooldown. Try again in {error.retry_after:.1f}s.")

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