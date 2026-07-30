import discord
from discord.ext import commands
import datetime
import time
import json
import os
import asyncio
import aiohttp

# ─── CONFIG ────────────────────────────────────────────────────────────────────

TOKEN          = os.environ["API_KEY"]
LOG_CHANNEL_ID = 1512641589032386601
DATA_FILE      = "bot_state.json"

# ─── INTENTS ───────────────────────────────────────────────────────────────────
intents                 = discord.Intents.all()
intents.message_content = True

bot           = commands.Bot(command_prefix="-", intents=intents)
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

# ─── RAW REST ──────────────────────────────────────────────────────────────────
async def raw_send(session: aiohttp.ClientSession, channel_id: int, payload: dict):
    token = bot.http.token
    async with session.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        json=payload,
    ) as resp:
        if resp.status not in (200, 201):
            text = await resp.text()
            raise RuntimeError(f"Discord API {resp.status}: {text}")

# ─── V2 PAYLOAD BUILDERS ───────────────────────────────────────────────────────
def online_status_payload(
    latency:      int,
    synced_count: int,
    prev_uptime:  str,
    start_unix:   int,
    avatar_url:   str,
) -> dict:
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 10,
                        "content": "# 🔄️ Automation Service Status\n-# Live, operational"
                    },
                    {
                        "type": 9,
                        "components": [
                            {
                                "type": 10,
                                "content": "**Latency**\n-# *How long it takes for the bot to respond to an action*"
                            }
                        ],
                        "accessory": {
                            "style": 2,
                            "type": 2,
                            "label": f"{latency}ms",
                            "custom_id": "p_status_latency",
                            "disabled": True
                        }
                    },
                    {
                        "type": 9,
                        "components": [
                            {
                                "type": 10,
                                "content": "**Slash Commands Synced**\n-# *How many slash commands were synced*"
                            }
                        ],
                        "accessory": {
                            "style": 2,
                            "type": 2,
                            "label": f"{synced_count} commands",
                            "custom_id": "p_status_synced",
                            "disabled": True
                        }
                    },
                    {
                        "type": 14,
                        "divider": False,
                        "spacing": 1
                    },
                    {
                        "type": 10,
                        "content": f"-# Started <t:{start_unix}:F>"
                    },
                    {"type": 14, "spacing": 2},
                    {
                        "type": 12,
                        "items": [
                            {
                                "media": {
                                    "url": "https://cdn.discordapp.com/attachments/1512646621924692039/1512647098930302986/smallbanner.png?ex=6a24d9e4&is=6a238864&hm=619a0ede3798a510db7a0cf9d2a56ac1987a0227fdd04dc9ca7e22ca1d0f307b&"
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }


def ping_payload(
    latency:     int,
    uptime_str:  str,
    start_unix:  int,
    author_name: str,
    avatar_url:  str,
    unix_now:    int,
) -> dict:
    filled    = max(1, min(10, round(latency / 50)))
    bar       = "█" * filled + "░" * (10 - filled)
    if latency < 100:
        quality = "Excellent"
    elif latency < 200:
        quality = "Good"
    elif latency < 400:
        quality = "Fair"
    else:
        quality = "Poor"

    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [

                    # ── Title + avatar ──
                    {
                        "type": 9,
                        "components": [
                            {
                                "type": 10,
                                "content": (
                                    "# 🏓  Pong!\n"
                                    f"-# Requested by {author_name} · <t:{unix_now}:R>"
                                )
                            }
                        ],
                        "accessory": {
                            "type": 11,
                            "media": {"url": avatar_url},
                        }
                    },

                    {"type": 14, "spacing": 1},

                    # ── Latency bar ──
                    {
                        "type": 10,
                        "content": (
                            f"**Latency**\n"
                            f"`{bar}` **{latency}ms** — {quality}"
                        )
                    },

                    {"type": 14, "spacing": 1},

                    # ── Uptime ──
                    {
                        "type": 10,
                        "content": (
                            f"**Uptime**\n"
                            f"`{uptime_str}`\n\n"
                            f"**Online Since**\n"
                            f"<t:{start_unix}:F>"
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {
                        "type": 12,
                        "items": [
                            {
                                "media": {
                                    "url": "https://cdn.discordapp.com/attachments/1512646621924692039/1512647098930302986/smallbanner.png?ex=6a24d9e4&is=6a238864&hm=619a0ede3798a510db7a0cf9d2a56ac1987a0227fdd04dc9ca7e22ca1d0f307b&"
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }


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
        payload = online_status_payload(
            latency      = round(bot.latency * 1000),
            synced_count = synced_count,
            prev_uptime  = prev_str,
            start_unix   = int(bot.start_time.timestamp()),
            avatar_url   = str(bot.user.display_avatar.url),
        )
        async with aiohttp.ClientSession() as session:
            try:
                await raw_send(session, LOG_CHANNEL_ID, payload)
            except RuntimeError as e:
                print(f"❌ Failed to send online status: {e}")


@bot.event
async def on_disconnect():
    print("Bot has disconnected from Discord.")


# ─── PING COMMAND ──────────────────────────────────────────────────────────────
@bot.command()
async def ping(ctx: commands.Context):
    """Shows bot latency and uptime."""
    now      = datetime.datetime.now(datetime.timezone.utc)
    latency  = round(bot.latency * 1000)
    uptime   = format_duration(now - bot.start_time)
    unix_now = int(now.timestamp())

    payload = ping_payload(
        latency     = latency,
        uptime_str  = uptime,
        start_unix  = int(bot.start_time.timestamp()),
        author_name = ctx.author.name,
        avatar_url  = str(ctx.author.display_avatar.url),
        unix_now    = unix_now,
    )

    async with aiohttp.ClientSession() as session:
        try:
            await raw_send(session, ctx.channel.id, payload)
        except RuntimeError as e:
            await ctx.send(f"❌ Failed to send ping response: {e}")


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