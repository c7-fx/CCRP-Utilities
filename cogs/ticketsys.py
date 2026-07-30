# cogs/tickets.py

import asyncio
import time
import io
import aiohttp
import discord
from discord import app_commands, Interaction
from discord.ext import commands


# ─── CONFIG ────────────────────────────────────────────────────────────────────
TICKET_CATEGORY_ID = 1532487653159866429
TICKET_LOG_CHANNEL = 1532488621699895396
TICKET_COOLDOWN_S  = 120  # 2 minutes

# Roles that can see every ticket (add your staff role IDs here)
STAFF_ROLE_IDS: list[int] = [1532239870792044544]

# ── Banner URLs — change these to update all embeds at once ──────────────────
BANNER_HEADER = "https://media.discordapp.net/attachments/1516926965674807443/1521022722057175040/4.png?ex=6a6cd98c&is=6a6b880c&hm=cdbd3c02d0665483563b1c3cf95fee576ae20f96073134d9bbeecfc22c39e161&format=webp&quality=lossless&width=1775&height=533&"
BANNER_FOOTER = "https://media.discordapp.net/attachments/1516926965674807443/1521022754734997545/14.png?ex=6a6cd993&is=6a6b8813&hm=17bf065053eb6f558c3814703bdf558daf94f07c739fc22f7d0184a401161188&format=webp&quality=lossless&width=1775&height=133&"

TICKET_TYPES = {
    "general": {"label": "General",          "short": "gen"},
    "department":      {"label": "Department", "short": "dept"},
    "management":      {"label": "Management", "short": "mgmt"},
}

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def strip_link_custom_ids(components: list) -> list:
    """Recursively remove custom_id from style-5 (link) buttons."""
    cleaned = []
    for component in components:
        c = dict(component)
        if "components" in c:
            c["components"] = strip_link_custom_ids(c["components"])
        if "accessory" in c and isinstance(c["accessory"], dict):
            acc = dict(c["accessory"])
            if acc.get("type") == 2 and acc.get("style") == 5:
                acc.pop("custom_id", None)
            c["accessory"] = acc
        if c.get("type") == 2 and c.get("style") == 5:
            c.pop("custom_id", None)
        cleaned.append(c)
    return cleaned



# ─── LOG PAYLOADS ──────────────────────────────────────────────────────────────
def log_open_payload(
    user: discord.Member,
    ticket_ch: discord.TextChannel,
    full_name: str,
    reason: str,
    proof_url: str | None,
) -> dict:
    unix_now   = int(time.time())
    proof_line = f"\n> **Proof:** {proof_url}" if proof_url else ""

    return {
        "flags": 32768,
        "allowed_mentions": {"parse": []},
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 10,
                        "content": (
                            f"## 📂  Ticket Opened\n"
                            f"> **Channel:** <#{ticket_ch.id}> — `{ticket_ch.name}`\n"
                            f"> **Opened by:** <@{user.id}> — `{user}` (`{user.id}`)\n"
                            f"> **Type:** {full_name}\n"
                            f"> **Opened:** <t:{unix_now}:F>\n"
                            f"### Reason\n"
                            f"```\n{reason}\n```"
                            f"{proof_line}"
                        )
                    },
                    {"type": 14, "spacing": 1},
                    {
                        "type": 12,
                        "items": [{"media": {"url": BANNER_FOOTER}}]
                    }
                ]
            }
        ]
    }


def log_close_payload(
    closer: discord.Member,
    channel_name: str,
    reason_str: str,
    message_count: int,
) -> dict:
    unix_now = int(time.time())

    return {
        "flags": 32768,
        "allowed_mentions": {"parse": []},
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 10,
                        "content": (
                            f"## 🔒  Ticket Closed\n"
                            f"> **Channel:** `{channel_name}`\n"
                            f"> **Closed by:** <@{closer.id}> — `{closer}` (`{closer.id}`)\n"
                            f"> **Messages in transcript:** {message_count}\n"
                            f"> **Closed:** <t:{unix_now}:F>\n"
                            f"### Closure Reason\n"
                            f"```\n{reason_str}\n```"
                        )
                    },
                    {"type": 14, "spacing": 1},
                    {
                        "type": 12,
                        "items": [{"media": {"url": BANNER_FOOTER}}]
                    }
                ]
            }
        ]
    }


async def build_transcript(channel: discord.TextChannel) -> tuple[io.BytesIO, int]:
    """
    Fetch all non-bot messages from the channel, format them into a plain
    text transcript, and return a BytesIO buffer + the message count.
    """
    lines: list[str] = []
    lines.append(f"TICKET TRANSCRIPT — #{channel.name}")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    lines.append("=" * 60)
    lines.append("")

    messages: list[discord.Message] = []
    async for msg in channel.history(limit=None, oldest_first=True):
        if not msg.author.bot:
            messages.append(msg)

    for msg in messages:
        ts        = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        author    = f"{msg.author} ({msg.author.id})"
        content   = msg.content or "(no text content)"
        attachments = (
            "\n  ".join(a.url for a in msg.attachments)
            if msg.attachments else ""
        )

        lines.append(f"[{ts}] {author}")
        lines.append(f"  {content}")
        if attachments:
            lines.append(f"  Attachments:\n  {attachments}")
        lines.append("")

    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.seek(0)
    return buf, len(messages)


# ─── PAYLOADS ──────────────────────────────────────────────────────────────────
def support_panel_payload() -> dict:
    raw = {
        "flags": 32768,
        "allowed_mentions": {"parse": []},
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 12,
                        "items": [{"media": {"url": BANNER_HEADER}}]
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 10, "content": "# Support System"},
                    {
                        "type": 9,
                        "components": [{"type": 10, "content": "**General**\n-# *For simple questions or low urgency matters*"}],
                        "accessory": {
                            "style": 2, "type": 2,
                            "disabled": False,
                            "custom_id": "ticket_open_general",
                            "label": "Open"
                        }
                    },
                    {
                        "type": 9,
                        "components": [{"type": 10, "content": "**Internal Affairs**\n-# *For staff reports or member reports*"}],
                        "accessory": {
                            "style": 2, "type": 2,
                            "disabled": False,
                            "custom_id": "ticket_open_ia",
                            "label": "Open"
                        }
                    },
                    {"type": 14, "spacing": 2},
                    {
                        "type": 12,
                        "items": [{"media": {"url": BANNER_FOOTER}}]
                    }
                ]
            }
        ]
    }
    raw["components"] = strip_link_custom_ids(raw["components"])
    return raw


def ticket_panel_payload(description: str, proof_url: str | None) -> dict:
    inner = [
        {"type": 10, "content": "# Ticket Management Panel"},
        {
            "type": 9,
            "components": [{"type": 10, "content": "**Close Ticket**\n-# *Close the ticket immediately with an optional reason*"}],
            "accessory": {
                "style": 2, "type": 2,
                "emoji": {"name": "🔒"},
                "disabled": False,
                "custom_id": "ticket_close"
            }
        },
        {
            "type": 9,
            "components": [{"type": 10, "content": "**Request Ticket Closure**\n-# *Request to close the ticket*"}],
            "accessory": {
                "style": 2, "type": 2,
                "emoji": {"name": "📩"},
                "disabled": False,
                "custom_id": "ticket_request_close"
            }
        },
        {"type": 14, "spacing": 2},
        {"type": 10, "content": "**Ticket Description**"},
        {"type": 10, "content": description},
    ]

    if proof_url:
        inner.append({
            "type": 12,
            "items": [{"media": {"url": proof_url}}]
        })

    inner += [
        {"type": 14, "spacing": 2},
        {
            "type": 12,
            "items": [{"media": {"url": BANNER_FOOTER}}]
        }
    ]

    return {"flags": 32768,
        "allowed_mentions": {"parse": []}, "components": [{"type": 17, "components": inner}]}


def closure_request_payload(req_message: str) -> dict:
    """V2 embed posted when a user requests ticket closure."""
    return {
        "flags": 32768,
        "allowed_mentions": {"parse": []},
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 10, "content": "# Closure Request"},
                    {
                        "type": 9,
                        "components": [{"type": 10, "content": "**Close Ticket**\n-# *Accept the closure request*"}],
                        "accessory": {
                            "style": 2, "type": 2,
                            "emoji": {"name": "✅"},
                            "disabled": False,
                            "custom_id": "ticket_close_accept"
                        }
                    },
                    {
                        "type": 9,
                        "components": [{"type": 10, "content": "**Deny Request**\n-# *Deny the closure request*"}],
                        "accessory": {
                            "style": 2, "type": 2,
                            "emoji": {"name": "🔒"},
                            "disabled": False,
                            "custom_id": "ticket_close_deny"
                        }
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 10, "content": "**Request Message**"},
                    {"type": 10, "content": req_message},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 12,
                        "items": [{"media": {"url": BANNER_FOOTER}}]
                    }
                ]
            }
        ]
    }


def closure_request_payload_disabled() -> dict:
    """Same embed as closure_request_payload but with both buttons disabled."""
    return {
        "flags": 32768,
        "allowed_mentions": {"parse": []},
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 10, "content": "# Closure Request"},
                    {
                        "type": 9,
                        "components": [{"type": 10, "content": "**Close Ticket**\n-# *Accept the closure request*"}],
                        "accessory": {
                            "style": 2, "type": 2,
                            "emoji": {"name": "✅"},
                            "disabled": True,
                            "custom_id": "ticket_close_accept"
                        }
                    },
                    {
                        "type": 9,
                        "components": [{"type": 10, "content": "**Deny Request**\n-# *Deny the closure request*"}],
                        "accessory": {
                            "style": 2, "type": 2,
                            "emoji": {"name": "🔒"},
                            "disabled": True,
                            "custom_id": "ticket_close_deny"
                        }
                    },
                    {"type": 14, "spacing": 2},
                    {"type": 10, "content": "**Request Message**"},
                    {"type": 10, "content": "*(Request denied)*"},
                    {"type": 14, "spacing": 2},
                    {
                        "type": 12,
                        "items": [{"media": {"url": BANNER_FOOTER}}]
                    }
                ]
            }
        ]
    }



class TicketModal(discord.ui.Modal):
    reason = discord.ui.TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph,
        placeholder="Describe your issue (minimum 15 characters)…",
        min_length=15,
        max_length=1000,
        required=True,
    )
    proof_url = discord.ui.TextInput(
        label="Proof URL (optional)",
        style=discord.TextStyle.short,
        placeholder="Paste a direct image/video URL if you have proof",
        required=False,
        max_length=500,
    )

    def __init__(self, ticket_type: str, cog: "Tickets"):
        super().__init__(title=f"Open {TICKET_TYPES[ticket_type]['label']} Ticket")
        self.ticket_type = ticket_type
        self.cog = cog

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.create_ticket(
            interaction,
            self.ticket_type,
            self.reason.value.strip(),
            self.proof_url.value.strip() or None,
        )


class CloseTicketModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(
        label="Closure Reason (optional)",
        style=discord.TextStyle.paragraph,
        placeholder="Provide a reason for closing this ticket…",
        required=False,
        max_length=500,
    )

    def __init__(self, cog: "Tickets"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.close_ticket(interaction, self.reason.value.strip() or None)


class RequestCloseModal(discord.ui.Modal, title="Request Ticket Closure"):
    reason = discord.ui.TextInput(
        label="Reason (optional)",
        style=discord.TextStyle.paragraph,
        placeholder="Why are you requesting this ticket be closed?",
        required=False,
        max_length=500,
    )

    def __init__(self, cog: "Tickets"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        req_message = self.reason.value.strip() or "No reason provided."
        payload = closure_request_payload(req_message)
        try:
            await self.cog.raw_send(interaction.channel_id, payload)
            await interaction.followup.send("✅ Closure request sent.", ephemeral=True)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ Failed to send request: {e}", ephemeral=True)


# ─── COG ───────────────────────────────────────────────────────────────────────
class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.session: aiohttp.ClientSession | None = None
        # user_id -> unix timestamp of last ticket open
        self._cooldowns: dict[int, float] = {}

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    # ── Raw REST ───────────────────────────────────────────────────────────────
    async def raw_send(self, channel_id: int, payload: dict) -> dict:
        token = self.bot.http.token
        async with self.session.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            text = await resp.text()
            if resp.status not in (200, 201):
                raise RuntimeError(f"Discord API {resp.status}: {text}")
            import json as _json
            return _json.loads(text)

    # ── Raw REST edit ─────────────────────────────────────────────────────────
    async def raw_edit(self, channel_id: int, message_id: int, payload: dict):
        token = self.bot.http.token
        async with self.session.patch(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Discord API {resp.status}: {text}")

    # ── Cooldown check ─────────────────────────────────────────────────────────
    def check_cooldown(self, user_id: int) -> float | None:
        """Returns seconds remaining if on cooldown, else None."""
        last = self._cooldowns.get(user_id)
        if last is None:
            return None
        remaining = TICKET_COOLDOWN_S - (time.monotonic() - last)
        return remaining if remaining > 0 else None

    def set_cooldown(self, user_id: int):
        self._cooldowns[user_id] = time.monotonic()

    # ── Create ticket ──────────────────────────────────────────────────────────
    async def create_ticket(
        self,
        interaction: Interaction,
        ticket_type: str,
        reason: str,
        proof_url: str | None,
    ):
        user  = interaction.user
        guild = interaction.guild

        # ── Cooldown guard ──
        remaining = self.check_cooldown(user.id)
        if remaining is not None:
            await interaction.followup.send(
                f"⏳ You're on cooldown. Please wait **{remaining:.0f}s** before opening another ticket.",
                ephemeral=True,
            )
            return

        category  = guild.get_channel(TICKET_CATEGORY_ID)
        log_ch    = guild.get_channel(TICKET_LOG_CHANNEL)
        short     = TICKET_TYPES[ticket_type]["short"]
        full_name = TICKET_TYPES[ticket_type]["label"]
        ch_name   = f"{short}-{user.name[:5].lower()}"

        if category is None:
            await interaction.followup.send(
                "❌ Ticket category not found. Please contact an administrator.",
                ephemeral=True,
            )
            return

        # ── Permissions ──
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }
        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                )

        try:
            ticket_ch = await guild.create_text_channel(
                name=ch_name,
                category=category,
                overwrites=overwrites,
                topic=f"{full_name} ticket — opened by {user} ({user.id})",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to create channels in that category.",
                ephemeral=True,
            )
            return

        # ── Post V2 panel embed ──
        try:
            await self.raw_send(ticket_ch.id, ticket_panel_payload(reason, proof_url))
        except RuntimeError as e:
            await interaction.followup.send(f"❌ Failed to post ticket panel: {e}", ephemeral=True)
            return

        # ── Ping opener ──
        await ticket_ch.send(
            f"{user.mention} <@&1484028039179534367> — your **{full_name}** ticket has been opened. "
            f"Staff will be with you shortly."
        )

        # ── Log ticket open ──
        if log_ch:
            try:
                await self.raw_send(log_ch.id, log_open_payload(user, ticket_ch, full_name, reason, proof_url))
            except RuntimeError as e:
                print(f"[Tickets] Failed to send open log: {e}")

        # ── Set cooldown after successful open ──
        self.set_cooldown(user.id)

        await interaction.followup.send(
            f"✅ Your ticket has been opened: {ticket_ch.mention}",
            ephemeral=True,
        )

    # ── Close ticket ───────────────────────────────────────────────────────────
    async def close_ticket(self, interaction: Interaction, reason: str | None):
        channel    = interaction.channel
        closer     = interaction.user
        log_ch     = interaction.guild.get_channel(TICKET_LOG_CHANNEL)
        reason_str = reason or "No reason provided."

        await channel.send(
            f"🔒 This ticket is being closed by {closer.mention}.\n"
            f"**Reason:** {reason_str}\n"
            f"-# Generating transcript…"
        )

        # ── Build transcript before deleting ──
        transcript_buf, msg_count = await build_transcript(channel)
        transcript_file = discord.File(
            transcript_buf,
            filename=f"transcript-{channel.name}.txt",
        )

        # ── Send clean V2 log embed + transcript file ──
        if log_ch:
            try:
                await self.raw_send(
                    log_ch.id,
                    log_close_payload(closer, channel.name, reason_str, msg_count),
                )
                await log_ch.send(file=transcript_file)
            except RuntimeError as e:
                print(f"[Tickets] Failed to send close log: {e}")

        await asyncio.sleep(2)

        try:
            await channel.delete(reason=f"Ticket closed by {closer}: {reason_str}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to delete this channel.", ephemeral=True
            )

    # ── Interaction router ─────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        cid = interaction.data.get("custom_id", "")

        if cid == "ticket_open_general":
            await interaction.response.send_modal(TicketModal("general", self))

        elif cid == "ticket_open_ia":
            await interaction.response.send_modal(TicketModal("ia", self))

        elif cid == "ticket_open_mgmt":
            await interaction.response.send_modal(TicketModal("mgmt", self))

        elif cid == "ticket_close":
            await interaction.response.send_modal(CloseTicketModal(self))

        elif cid == "ticket_request_close":
            await interaction.response.send_modal(RequestCloseModal(self))

        elif cid == "ticket_close_accept":
            # Any staff / the original opener clicking accept on the request embed
            await interaction.response.defer(ephemeral=True)
            await self.close_ticket(interaction, "Closure request accepted.")

        elif cid == "ticket_close_deny":
            await interaction.response.defer(ephemeral=True)
            # Rebuild the closure request embed with both buttons disabled
            msg     = interaction.message
            payload = closure_request_payload_disabled()
            try:
                await self.raw_edit(interaction.channel_id, msg.id, payload)
            except RuntimeError as e:
                await interaction.followup.send(f"❌ Failed to update embed: {e}", ephemeral=True)
                return
            await interaction.channel.send(
                f"❌ {interaction.user.mention} denied the closure request."
            )
            await interaction.followup.send("Done.", ephemeral=True)

    # ── Slash command ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="ticketpanel",
        description="Post the support ticket panel in this channel.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_panel(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.raw_send(interaction.channel_id, support_panel_payload())
            await interaction.followup.send("✅ Ticket panel posted!", ephemeral=True)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ Failed to post panel:\n```{e}```", ephemeral=True)

    @ticket_panel.error
    async def ticket_panel_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Manage Server** to use this command.", ephemeral=True
            )


# ─── SETUP ─────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))