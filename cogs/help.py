"""This custom help command is a perfect replacement for the default one on any Discord Bot written in Discord.py Rewrite!
However, you must put "bot.remove_command('help')" in your bot, and the command must be in a cog for it to work.
Written by Jared Newsom (AKA Jared M.F.)!"""

from discord.ext import commands
import discord


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.has_permissions(add_reactions=True, embed_links=True)
    async def help(self, ctx, *cog):
        """Gets all cogs and commands of this bot."""
        try:
            if not cog:
                halp = discord.Embed(title='Useless\' Commands',
                                     description='Use `!help *category*` to find out more about the commands in them!')
                cogs_desc = ''
                for x in self.bot.cogs:
                    cogs_desc = f'{x}'
                    cmds = ''
                    for cmd in self.bot.get_cog(x).get_commands():
                        if not cmd.hidden:
                            cmds += f'`{cmd.name}`, '
                    if cmds != '':
                        halp.add_field(name= cogs_desc,
                                       value=f'{cmds[0:-2]}',
                                       inline=False)
                cmds_desc = ''
                for y in self.bot.walk_commands():
                    if not y.cog_name and not y.hidden:
                        cmds_desc += ('`{}` - {}'.format(y.name, y.help) + '\n')
                if cmds_desc != '':
                    halp.add_field(name='Uncatergorized Commands',
                                   value=cmds_desc[0:len(cmds_desc) - 1],
                                   inline=False)
                await ctx.send(embed=halp)
            else:
                if len(cog) > 1:
                    halp = discord.Embed(title='Error!',
                                         description='I can only help with 1 category!',
                                         color=discord.Color.red())
                    await ctx.send(embed=halp)
                else:
                    found = False
                    for x in self.bot.cogs:
                        for y in cog:
                            if x == y:
                                halp = discord.Embed(
                                    title=cog[0] + ' Command Listing',
                                    description=self.bot.cogs[cog[0]].__doc__)
                                for c in self.bot.get_cog(y).get_commands():
                                    if not c.hidden:
                                        halp.add_field(name=c.name,
                                                       value=c.help,
                                                       inline=False)
                                found = True
                    if not found:
                        halp = discord.Embed(title='Error!',
                                             description='How do you even use "' +
                                                         cog[0] + '"?',
                                             color=discord.Color.red())
                    await ctx.send('', embed=halp)

        except:
            print('Pass')
            pass


def setup(bot):
    bot.add_cog(Help(bot))
