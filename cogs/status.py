# cogs/status.py

import discord
from discord.ext import commands, tasks


# ─── CONFIG ────────────────────────────────────────────────────────────────────

ACTIVITY_TYPE = "Watching"  # Playing | Watching | Listening | Competing
ACTIVITY_EMOJI_ID = 1519024410281906297  # Custom emoji ID
STATUS        = "online"  # online | idle | dnd | invisible

# List of statuses to rotate through — add/remove as many as you like
STATUS_MESSAGES = [
    "Watching over {count} members",
]

ROTATE_SECONDS = 5  # how often to switch to the next status in the list


# ─── COG ───────────────────────────────────────────────────────────────────────
ACTIVITY_MAP = {
    "Playing":   discord.ActivityType.playing,
    "Watching":  discord.ActivityType.watching,
    "Listening": discord.ActivityType.listening,
    "Competing": discord.ActivityType.competing,
}

class BotStatus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self._index = 0

    def cog_unload(self):
        if self.rotate_status.is_running():
            self.rotate_status.cancel()

    def _member_count(self) -> int:
        return sum(guild.member_count or 0 for guild in self.bot.guilds)

    async def _apply_status(self):
        emoji  = self.bot.get_emoji(ACTIVITY_EMOJI_ID)
        prefix = f"{emoji} " if emoji else ""

        raw_text = STATUS_MESSAGES[self._index % len(STATUS_MESSAGES)]
        text     = raw_text.format(count=f"{self._member_count():,}")

        activity = discord.Activity(
            type=ACTIVITY_MAP.get(ACTIVITY_TYPE, discord.ActivityType.playing),
            name=f"{prefix}{text}",
        )
        await self.bot.change_presence(
            status=discord.Status[STATUS],
            activity=activity,
        )

        self._index += 1

    @commands.Cog.listener()
    async def on_ready(self):
        # Guard against on_ready firing multiple times (reconnects) and double-starting the loop
        if not self.rotate_status.is_running():
            self.rotate_status.start()

    @tasks.loop(seconds=ROTATE_SECONDS)
    async def rotate_status(self):
        await self._apply_status()

    @rotate_status.before_loop
    async def before_rotate(self):
        await self.bot.wait_until_ready()


# ─── SETUP ─────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(BotStatus(bot))