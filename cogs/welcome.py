# cogs/welcome.py

import asyncio
import aiohttp
import discord
from discord.ext import commands


# ─── CONFIG ────────────────────────────────────────────────────────────────────
WELCOME_CHANNEL_ID = 1532239804719173737  # Replace with your welcome channel ID


# ─── PAYLOAD ───────────────────────────────────────────────────────────────────
def welcome_payload(member: discord.Member) -> dict:
    member_count = member.guild.member_count

    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 1,
                        "components": [
                            {
                                "style": 2,
                                "type": 2,
                                "label": f"{member_count} Members",
                                "disabled": True,
                                "custom_id": "p_290956969273987073",
                                "emoji": {
                                    "id": "1516928560168702062",
                                    "name": "COASTCITY",
                                    "animated": False
                                }
                            },
                            {
                                "type": 2,
                                "style": 5,
                                "label": "Server Guide",
                                "url": "https://discord.com/channels/1516926962885464186/1516926964114395258",
                            },
                            {
                                "type": 2,
                                "style": 5,
                                "label": "Roblox Group",
                                "url": "https://www.roblox.com/communities/32567705/ER-LC-Coast-City-Roleplay#!/about",
                            }
                        ]
                    }
                ]
            }
        ]
    }


# ─── COG ───────────────────────────────────────────────────────────────────────
class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    async def raw_send(self, channel_id: int, payload: dict):
        token = self.bot.http.token
        async with self.session.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise RuntimeError(f"Discord API {resp.status}: {text}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not WELCOME_CHANNEL_ID:
            print("[Welcome] WELCOME_CHANNEL_ID is not set.")
            return

        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            print("[Welcome] Could not find welcome channel.")
            return

        try:
            # Send ping first so the notification lands, then the V2 embed
            await channel.send(f"Welcome to **Coast City Roleplay**, {member.mention} !")
            await self.raw_send(WELCOME_CHANNEL_ID, welcome_payload(member))
        except RuntimeError as e:
            print(f"[Welcome] Failed to send welcome message: {e}")


# ─── SETUP ─────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))