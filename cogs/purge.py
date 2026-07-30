# cogs/purge.py

import discord
from discord.ext import commands


class Purge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        if amount < 1:
            await ctx.reply("Please specify at least 1 message to delete.")
            return

        # Delete the command message itself first
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        # Fetch messages and filter out pinned ones, then delete up to `amount`
        deleted = 0
        async for message in ctx.channel.history(limit=amount + 50):  # fetch extra to account for pinned skips
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
                continue  # already deleted, skip

        confirm = await ctx.channel.send(f"Deleted {deleted} message(s).")
        await confirm.delete(delay=3)

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