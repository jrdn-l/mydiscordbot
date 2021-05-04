import discord
import random
from discord.ext import commands


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='8ball',
                 description='Ask the 8ball a question and receive an answer')
    async def eight_ball(self, ctx, *message: str):
        '''
        Ask a question
        '''
        x = ['It is certain', 'It is decidedly so', 'Without a doubt',
             'Yes - definitely', 'You may rely on it', 'As I see it yes',
             'Most likely', 'Outlook good', 'Yes', 'Signs point to yes',
             'Ask again later', 'Cannot predict now', 'Concentrate and ask '
                                                      'again',
             'Better not tell you now', 'Reply Hazy, try again',
             'My sources say no',
             'Don\'t count on it', 'My reply is no', 'Doubtful',
             'Outlook not so good']
        if message == ():
            await ctx.send('Where the question at?')
        else:
            await ctx.send(random.choice(x))

    @commands.command()
    async def roll(self, ctx, dice: str):
        """Rolls a dice in NdN format."""
        try:
            rolls, limit = map(int, dice.split('d'))
        except Exception:
            await ctx.send('Format has to be in NdN!')
            return

        result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
        await ctx.send(result)

    @commands.command(
        description='For when you wanna settle the score some other way')
    async def choose(self, ctx, *choices: str):
        """Chooses between multiple choices."""
        await ctx.send(random.choice(choices))

    @commands.command()
    async def repeat(self, ctx, times, *, content='repeating...'):
        """Repeats a message multiple times."""
        try:
            times = int(times)
        except ValueError:
            await ctx.send("Not a valid input!"
                           "Repeating format is: !repeat <num_times> "
                           "<contents>")
            return None

        for i in range(int(times)):
            await ctx.send(content)

    @commands.command()
    async def joined(self, ctx, member: discord.Member):
        """Says when a member joined."""
        await ctx.send('{0.name} joined in {0.joined_at}'.format(member))


def setup(bot):
    bot.add_cog(Misc(bot))
