import os
import discord
from discord.ext import commands


class Purge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="purge")
    async def purge(self, ctx: commands.Context, amount: int):
        if not isinstance(ctx.author, discord.Member):
            await ctx.reply("This command can only be used in a server.")
            return

        allowed_role_ids = []
        for role_id in [os.getenv("MGMT_ROLE_ID"), os.getenv("STAFF_ROLE_ID")]:
            if role_id:
                try:
                    allowed_role_ids.append(int(role_id))
                except ValueError:
                    continue

        if not allowed_role_ids:
            await ctx.reply("Role configuration is missing.")
            return

        if not any(role.id in allowed_role_ids for role in ctx.author.roles):
            await ctx.reply("You do not have permission to use this command.")
            return

        if amount < 1:
            await ctx.reply("Please specify at least 1 message to delete.")
            return

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        deleted = 0
        async for message in ctx.channel.history(limit=amount + 50):
            if deleted >= amount:
                break
            if message.pinned:
                continue
            try:
                await message.delete()
                deleted += 1
            except discord.Forbidden:
                break
            except discord.NotFound:
                continue

    @purge.error
    async def purge_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Usage: `purge <number>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.reply("Please provide a valid number.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply("You need **Manage Messages** permission to use this.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Purge(bot)) 