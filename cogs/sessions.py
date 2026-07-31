# cogs/sessions.py

import asyncio
import aiohttp
import discord
import time
from datetime import datetime, timezone
from discord.ext import commands, tasks


# ─── CONFIG ────────────────────────────────────────────────────────────────────
import os
ERLC_API_KEY      = os.environ.get("ERLC_API_KEY", "")
ERLC_API_BASE     = "https://api.erlc.gg/v1"

SESSION_CHANNEL_ID  = 1532239804719173737   # where session messages are posted
SESSION_PANEL_CH_ID = 1532239804719173737   # where the live panel lives (can be same channel)

MGMT_ROLE_ID        = 1532239870792044544   # management role — can run all commands
SESSION_ROLE_ID     = 1532239870792044544   # role pinged on session start/vote
STAFF_ROLE_ID       = 1532239870792044544   # staff role pinged in session start

REFRESH_SECONDS     = 30                    # how often the panel embed updates

FOOTER_URL = "https://media.discordapp.net/attachments/1516926965674807443/1521022754734997545/14.png?ex=6a6cd993&is=6a6b8813&hm=17bf065053eb6f558c3814703bdf558daf94f07c739fc22f7d0184a401161188&=&format=webp&quality=lossless"


# ─── PERMISSION CHECK ──────────────────────────────────────────────────────────
def has_session_perms():
    """Allows users with MGMT_ROLE_ID or Manage Channels permission."""
    async def predicate(ctx: commands.Context) -> bool:
        member = ctx.author
        if ctx.channel.permissions_for(member).manage_channels:
            return True
        if any(r.id == MGMT_ROLE_ID for r in member.roles):
            return True
        raise commands.CheckFailure("You need the Management role or Manage Channels permission.")
    return commands.check(predicate)


# ─── ERLC API ──────────────────────────────────────────────────────────────────
async def fetch_server(session: aiohttp.ClientSession) -> dict | None:
    try:
        async with session.get(
            f"{ERLC_API_BASE}/server",
            headers={"server-key": ERLC_API_KEY},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            print(f"[Sessions] /server {resp.status}: {text}")
            return None
    except Exception as e:
        print(f"[Sessions] /server error: {e}")
        return None


async def fetch_queue(session: aiohttp.ClientSession) -> int:
    try:
        async with session.get(
            f"{ERLC_API_BASE}/server/queue",
            headers={"server-key": ERLC_API_KEY},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return len(data) if isinstance(data, list) else 0
            return 0
    except Exception:
        return 0


# ─── PAYLOAD BUILDERS ──────────────────────────────────────────────────────────
def panel_payload(plrcount: int, max_players: int, queue: int, last_updated: str) -> dict:
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 12, "items": [{"media": {"url": "https://media.discordapp.net/attachments/1516926965674807443/1521022723164209302/7.png?ex=6a6cd98c&is=6a6b880c&hm=0a4595a377e35233448bd8ce682383b9ebc0af76e6054c5f41c343173dbb2555&=&format=webp&quality=lossless"}}]},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 10,
                        "content": (
                            "<:Dot:1521024677492035804> Server polls, startups, and shutdowns are posted here, whenever the in-game server is about to start, going to start, and shutdown, you'll be notified inside of this channel. While the server is shutdown, please do not join the server.\n\n"
                            "<:home:1517977032380907653>  ``Game Information:``\n"
                            "**Server Name:** Coast City Roleplay\n"
                            "**Server Owner:** BeanSypher\n"
                            "**Server Code:** CoastCtyRP\n\n"
                            "<:controller:1517977051867516979> ``Ingame Information:``\n"
                            f"**Playercount:** {plrcount} / {max_players}\n"
                            f"**Queue:** {queue}\n"
                            f"**Last Updated:** {last_updated}\n\n"
                            ":clock: ``Session Times:``\n"
                            "**Monday to Sunday** - <t:1782756000:t> & <t:1782774000:t>"
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


def panel_offline_payload() -> dict:
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 12, "items": [{"media": {"url": "https://media.discordapp.net/attachments/1516926965674807443/1521022723164209302/7.png?ex=6a6cd98c&is=6a6b880c&hm=0a4595a377e35233448bd8ce682383b9ebc0af76e6054c5f41c343173dbb2555&=&format=webp&quality=lossless"}}]},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 10,
                        "content": (
                            "<:Dot:1521024677492035804> Server polls, startups, and shutdowns are posted here, whenever the in-game server is about to start, going to start, and shutdown, you'll be notified inside of this channel. While the server is shutdown, please do not join the server.\n\n"
                            "<:home:1517977032380907653>  ``Game Information:``\n"
                            "**Server Name:** Coast City Roleplay\n"
                            "**Server Owner:** BeanSypher\n"
                            "**Server Code:** CoastCtyRP\n\n"
                            "<:controller:1517977051867516979> ``Ingame Information:``\n"
                            "**Playercount:** Unavailable\n"
                            "**Queue:** Unavailable\n"
                            f"**Last Updated:** {now}\n\n"
                            ":clock: ``Session Times:``\n"
                            "**Monday to Sunday** - <t:1782756000:t> & <t:1782774000:t>"
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


def vote_payload(votes: int, req_votes: int) -> dict:
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 12, "items": [{"media": {"url": "https://media.discordapp.net/attachments/1516926965674807443/1521022755292844117/11.png?ex=6a6cd994&is=6a6b8814&hm=770f55c6834ae0426ed0ede5968ae1a3fcf941b77a15c42293b97a9b2e96e773&=&format=webp&quality=lossless"}}]},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 10,
                        "content": (
                            f"<:intermediate:1516975224942497812>  The **Coast City Roleplay** management team is looking to start a session. "
                            f"In order for our server to go online we will need **{req_votes}** or more votes."
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {
                        "type": 1,
                        "components": [
                            {
                                "style": 1, "type": 2,
                                "label": "Vote",
                                "custom_id": "session_vote_button"
                            },
                            {
                                "style": 2, "type": 2,
                                "label": f"{votes} / {req_votes}",
                                "disabled": True,
                                "custom_id": "session_vote_count"
                            },
                            {
                                "style": 2, "type": 2,
                                "label": "View Votes",
                                "emoji": {"id": "1517977053713141834", "name": "person", "animated": False},
                                "custom_id": "session_vote_view"
                            }
                        ]
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


def vote_closed_payload(votes: int, req_votes: int) -> dict:
    """Vote embed with buttons disabled after goal is reached."""
    payload = vote_payload(votes, req_votes)
    buttons = payload["components"][0]["components"][3]["components"]
    for btn in buttons:
        btn["disabled"] = True
    return payload


def session_start_payload(plrcount: int, voter_pings: str) -> dict:
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 12, "items": [{"media": {"url": "https://media.discordapp.net/attachments/1516926965674807443/1521022719926341682/8.png?ex=6a6cd98b&is=6a6b880b&hm=1718c17921ac6bfec34676bf5cfde0c9527044bc0a933fad1d70ee9cca3af1b4&=&format=webp&quality=lossless"}}]},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 10,
                        "content": (
                            "<:online:1516975251475529909> The session vote reached our needed voting requirement to start our session. "
                            "If you reacted during the voting period, you are required to join the session for **at least** 30 minutes. "
                            "Failure to do so will result in moderation.\n\n"
                            "**Server Name:** Coast City Roleplay\n"
                            "**Server Owner:** BeanSypher\n"
                            "**Server Join Code:** CoastCtyRP\n"
                            f"**Player Count:** {plrcount}\n\n"
                            f"-# @here  |  <@&{SESSION_ROLE_ID}> {voter_pings}"
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2, "style": 5,
                                "label": "Join",
                                "emoji": {"id": "1532477665653559438", "name": "ccrp", "animated": False},
                                "url": "https://erlc.gg/join/CoastCtyRP"
                            }
                        ]
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


def session_start_manual_payload(plrcount: int) -> dict:
    """Session start payload used when triggered manually via -sessionstart (no voter pings)."""
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 12, "items": [{"media": {"url": "https://media.discordapp.net/attachments/1516926965674807443/1521022719926341682/8.png?ex=6a6cd98b&is=6a6b880b&hm=1718c17921ac6bfec34676bf5cfde0c9527044bc0a933fad1d70ee9cca3af1b4&=&format=webp&quality=lossless"}}]},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 10,
                        "content": (
                            "<:online:1516975251475529909> A session has been started! "
                            "Join us and experience Coast City Roleplay.\n\n"
                            "**Server Name:** Coast City Roleplay\n"
                            "**Server Owner:** BeanSypher\n"
                            "**Server Join Code:** CoastCtyRP\n"
                            f"**Player Count:** {plrcount}\n\n"
                            f"-# @here  |  <@&{SESSION_ROLE_ID}>"
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2, "style": 5,
                                "label": "Join",
                                "emoji": {"id": "1532477665653559438", "name": "ccrp", "animated": False},
                                "url": "https://erlc.gg/join/CoastCtyRP"
                            }
                        ]
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


def session_low_payload(plrcount: int) -> dict:
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 12, "items": [{"media": {"url": "https://media.discordapp.net/attachments/1516926965674807443/1521022720714870935/10.png?ex=6a6cd98b&is=6a6b880b&hm=53e4feea6ae1602291db5180d00de06b8870f7e3610915ddc74f96b3e25a86aa&=&format=webp&quality=lossless"}}]},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 10,
                        "content": (
                            f"<:Dot:1521024677492035804> Our in-game server is sitting at **{plrcount}** players! "
                            "Come join and have some fantastic roleplays with us.\n\n"
                            "<:home:1517977032380907653>  ``Game Information:``\n"
                            "**Server Name:** Coast City Roleplay\n"
                            "**Server Owner:** BeanSypher\n"
                            "**Server Code:** CoastCtyRP"
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


def session_end_payload() -> dict:
    return {
        "flags": 32768,
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 12, "items": [{"media": {"url": "https://media.discordapp.net/attachments/1516926965674807443/1521022720299499620/9.png?ex=6a6cd98b&is=6a6b880b&hm=6bdc2eb1e40ee1413619ff908a14117fcea63badd1c9d9b0f4da58e0c939bb0f&=&format=webp&quality=lossless"}}]},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 10,
                        "content": (
                            "<:offline:1516975248631664832> Our server is now offline, we will see you soon! "
                            "Please do not join the server whilst it is shutdown. "
                            "Keep an eye on this channel for the next session."
                        )
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


def view_votes_payload(voters: list[discord.Member]) -> dict:
    """Ephemeral embed listing all current voters."""
    if voters:
        voter_list = "\n".join(f"<@{m.id}> — {m.display_name}" for m in voters)
    else:
        voter_list = "No votes yet."

    return {
        "flags": 32768 | 64,  # ephemeral
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 10, "content": f"**Current Voters** ({len(voters)})\n\n{voter_list}"},
                    {"type": 14, "spacing": 2},
                    {"type": 12, "items": [{"media": {"url": FOOTER_URL}}]}
                ]
            }
        ]
    }


# ─── COG ───────────────────────────────────────────────────────────────────────
class Sessions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.session: aiohttp.ClientSession | None = None

        # Live panel state
        self.panel_message_id: int | None = None
        self.panel_channel_id: int | None = SESSION_PANEL_CH_ID or None

        # Active vote state
        self.vote_message_id: int | None  = None
        self.vote_channel_id: int | None  = None
        self.vote_req: int                = 0
        self.voters: dict[int, discord.Member] = {}  # user_id -> Member

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.panel_loop.cancel()
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    # ── Raw REST ───────────────────────────────────────────────────────────────
    async def raw_send(self, channel_id: int, payload: dict) -> dict:
        import json as _j
        token = self.bot.http.token
        async with self.session.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            text = await resp.text()
            if resp.status not in (200, 201):
                raise RuntimeError(f"Discord {resp.status}: {text}")
            return _j.loads(text)

    async def raw_edit(self, channel_id: int, message_id: int, payload: dict):
        token = self.bot.http.token
        async with self.session.patch(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise RuntimeError(f"Discord {resp.status}: {text}")

    async def raw_interaction_reply(self, interaction: discord.Interaction, payload: dict):
        token = self.bot.http.token
        async with self.session.post(
            f"https://discord.com/api/v10/interactions/{interaction.id}/{interaction.token}/callback",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json={"type": 4, "data": payload},
        ) as resp:
            if resp.status not in (200, 201, 204):
                text = await resp.text()
                raise RuntimeError(f"Interaction reply failed {resp.status}: {text}")

    # ── Build live panel ───────────────────────────────────────────────────────
    async def build_panel_payload(self) -> dict:
        info = await fetch_server(self.session)
        queue = await fetch_queue(self.session)
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")

        if info is None:
            return panel_offline_payload()

        return panel_payload(
            plrcount=int(info.get("CurrentPlayers", 0)),
            max_players=int(info.get("MaxPlayers", 0)),
            queue=queue,
            last_updated=now,
        )

    # ── Panel refresh loop ─────────────────────────────────────────────────────
    @tasks.loop(seconds=REFRESH_SECONDS)
    async def panel_loop(self):
        if not self.panel_channel_id or not self.panel_message_id:
            return
        try:
            payload = await self.build_panel_payload()
            await self.raw_edit(self.panel_channel_id, self.panel_message_id, payload)
        except RuntimeError as e:
            print(f"[Sessions] Panel update failed: {e}")

    @panel_loop.before_loop
    async def before_panel_loop(self):
        await self.bot.wait_until_ready()

    # ── Trigger auto session start when votes hit goal ─────────────────────────
    async def trigger_session_start(self, channel: discord.TextChannel):
        # Snapshot voters before resetting state
        voter_ids    = list(self.voters.keys())
        voter_pings  = " ".join(f"<@{uid}>" for uid in voter_ids)

        # 1. Disable the vote embed
        if self.vote_message_id:
            try:
                await self.raw_edit(
                    self.vote_channel_id, self.vote_message_id,
                    vote_closed_payload(len(self.voters), self.vote_req)
                )
            except RuntimeError as e:
                print(f"[Sessions] Failed to close vote embed: {e}")

        # 2. Fetch live player count
        info     = await fetch_server(self.session)
        plrcount = int(info.get("CurrentPlayers", 0)) if info else 0

        # 3. Send plain text ping first (separate message so mentions actually fire)
        #    Components V2 embeds can't use the content field, so pings must be standalone.
        ping_line = f"@here <@&{SESSION_ROLE_ID}> {voter_pings}"
        try:
            ch = self.bot.get_channel(SESSION_CHANNEL_ID)
            if ch:
                await ch.send(
                    ping_line,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=True,
                        roles=True,
                        users=True,
                    )
                )
        except Exception as e:
            print(f"[Sessions] Failed to send session start pings: {e}")

        # 4. Post the session start V2 embed (voter pings shown inside as subtext)
        payload = session_start_payload(plrcount, voter_pings)
        payload["allowed_mentions"] = {"parse": []}  # pings already sent above
        try:
            await self.raw_send(SESSION_CHANNEL_ID, payload)
        except RuntimeError as e:
            print(f"[Sessions] Failed to send session start embed: {e}")

        # 5. Reset vote state
        self.vote_message_id = None
        self.vote_channel_id = None
        self.vote_req        = 0
        self.voters          = {}

    # ── Interaction listener (vote buttons) ────────────────────────────────────
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        cid = interaction.data.get("custom_id", "")

        # ── Vote button ──
        if cid == "session_vote_button":
            if self.vote_message_id is None:
                await self.raw_interaction_reply(interaction, {
                    "flags": 64,
                    "content": "There is no active vote right now."
                })
                return

            uid = interaction.user.id
            if uid in self.voters:
                del self.voters[uid]
                msg = "Your vote has been removed."
            else:
                self.voters[uid] = interaction.user
                msg = "Your vote has been counted."

            # Check if goal is reached BEFORE updating the embed
            goal_reached = len(self.voters) >= self.vote_req

            if goal_reached:
                # Acknowledge the interaction first, then handle the start flow
                await self.raw_interaction_reply(interaction, {
                    "flags": 64,
                    "content": "Vote counted! The goal has been reached — starting the session."
                })
                channel = self.bot.get_channel(self.vote_channel_id)
                if channel:
                    await self.trigger_session_start(channel)
            else:
                # Update the vote count on the embed
                try:
                    await self.raw_edit(
                        self.vote_channel_id, self.vote_message_id,
                        vote_payload(len(self.voters), self.vote_req)
                    )
                except RuntimeError as e:
                    print(f"[Sessions] Failed to update vote embed: {e}")

                await self.raw_interaction_reply(interaction, {"flags": 64, "content": msg})

        # ── View votes button ──
        elif cid == "session_vote_view":
            members = list(self.voters.values())
            try:
                await self.raw_interaction_reply(interaction, view_votes_payload(members))
            except RuntimeError as e:
                print(f"[Sessions] View votes reply failed: {e}")

    # ── Commands ───────────────────────────────────────────────────────────────
    @commands.command(name="sessionpanel")
    @has_session_perms()
    async def cmd_session_panel(self, ctx: commands.Context):
        """Post the live session info panel and start auto-refresh."""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        payload = await self.build_panel_payload()
        try:
            sent = await self.raw_send(SESSION_PANEL_CH_ID, payload)
        except RuntimeError as e:
            await ctx.send(f"Failed to post panel: {e}", delete_after=8)
            return

        self.panel_message_id = int(sent["id"])
        self.panel_channel_id = SESSION_PANEL_CH_ID

        if not self.panel_loop.is_running():
            self.panel_loop.start()

        await ctx.send("Session panel posted and live updates started.", delete_after=5)

    @commands.command(name="sessionvote")
    @has_session_perms()
    async def cmd_session_vote(self, ctx: commands.Context, req_votes: int):
        """Start a session vote. Usage: -sessionvote <required_votes>"""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        if req_votes < 1:
            await ctx.send("Required votes must be at least 1.", delete_after=5)
            return

        self.vote_req  = req_votes
        self.voters    = {}

        payload = vote_payload(0, req_votes)
        payload["allowed_mentions"] = {"parse": ["everyone", "roles"]}

        try:
            sent = await self.raw_send(SESSION_CHANNEL_ID, payload)
        except RuntimeError as e:
            await ctx.send(f"Failed to post vote: {e}", delete_after=8)
            return

        self.vote_message_id = int(sent["id"])
        self.vote_channel_id = SESSION_CHANNEL_ID

        # Ping session role in a separate plain message
        try:
            ch = self.bot.get_channel(SESSION_CHANNEL_ID)
            if ch:
                await ch.send(
                    f"<@&{SESSION_ROLE_ID}> — a session vote has started!",
                    allowed_mentions=discord.AllowedMentions(roles=True)
                )
        except Exception as e:
            print(f"[Sessions] Failed to send vote ping: {e}")

    @commands.command(name="sessionstart")
    @has_session_perms()
    async def cmd_session_start(self, ctx: commands.Context):
        """Manually start a session (no voter pings)."""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        info = await fetch_server(self.session)
        plrcount = int(info.get("CurrentPlayers", 0)) if info else 0

        payload = session_start_manual_payload(plrcount)
        payload["allowed_mentions"] = {"parse": ["everyone", "roles"]}

        try:
            await self.raw_send(SESSION_CHANNEL_ID, payload)
        except RuntimeError as e:
            await ctx.send(f"Failed to post session start: {e}", delete_after=8)

    @commands.command(name="sessionlow")
    @has_session_perms()
    async def cmd_session_low(self, ctx: commands.Context):
        """Post a low player count alert."""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        info = await fetch_server(self.session)
        plrcount = int(info.get("CurrentPlayers", 0)) if info else 0

        payload = session_low_payload(plrcount)
        payload["allowed_mentions"] = {"parse": ["everyone", "roles"]}

        try:
            await self.raw_send(SESSION_CHANNEL_ID, payload)
        except RuntimeError as e:
            await ctx.send(f"Failed to post low player alert: {e}", delete_after=8)

    @commands.command(name="sessionend")
    @has_session_perms()
    async def cmd_session_end(self, ctx: commands.Context):
        """Post the session offline embed."""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        payload = session_end_payload()
        payload["allowed_mentions"] = {"parse": []}

        try:
            await self.raw_send(SESSION_CHANNEL_ID, payload)
        except RuntimeError as e:
            await ctx.send(f"Failed to post session end: {e}", delete_after=8)

    # ── Error handler ──────────────────────────────────────────────────────────
    @cmd_session_panel.error
    @cmd_session_vote.error
    @cmd_session_start.error
    @cmd_session_low.error
    @cmd_session_end.error
    async def session_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.reply("You don't have permission to use this command.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Missing argument. Usage: `-{ctx.command.name} <required_votes>`", delete_after=5)
        elif isinstance(error, commands.BadArgument):
            await ctx.reply("Invalid argument. Please provide a number.", delete_after=5)


# ─── SETUP ─────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Sessions(bot))