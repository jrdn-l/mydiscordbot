import asyncio
import discord
from discord.ext import commands
import random

class Games(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(description='The bot randomly selects a number between '
                                  '<start> and <end>. The player will have 5 guesses '
                                  'and 10s to start')
    async def guess(self, ctx, start=0, end=10):
        """
        Game where you guess a number
        """
        try:
            ans = random.randint(start, end)
        except ValueError:
            return await ctx.send("Not a valid number range!")
        await ctx.send('Guess a number between {0} and {1}'
                       '\nYou will have 10s and 5 attempts'.format(start, end))

        def is_correct(m):
            return m.author == ctx.author and m.content.isdigit()

        counter = 5
        while True:
            try:
                guess = await self.bot.wait_for('message', check=is_correct,
                                                timeout=10.0)
            except asyncio.TimeoutError:
                return await ctx.send(
                    'Sorry, you took too long it was {}.'.format(ans))

            if int(guess.content) == ans:
                return await ctx.send(
                    'You are right! The answer was {0}'.format(ans))
            elif counter == 1:
                return await ctx.send('Sorry, you\'ve run out of guesses,'
                                      ' it was {}.'.format(ans))
            else:
                counter -= 1
                await ctx.send(
                    'You have {0} attempts remaining'.format(counter))

    @commands.command(name='Ultimate_Rock_Paper_Scissors', description='Ultimate Rock Paper Scissors',
                      aliases=['urps'])
    async def ursp(self, ctx, member: discord.Member):
        """
        The ultimate rock paper scissors. Can also call with urps
        """
        # Declaring some local variables
        options = ['rock', 'fire', 'scissors', 'snake', 'human', 'tree',
                   'wolf', 'sponge', 'paper', 'air', 'water', 'dragon', 'devil',
                   'lightning', 'gun', 'rock', 'fire', 'scissors', 'snake',
                   'human', 'tree', 'wolf']

        s_options = ['ro', 'fi', 'sc', 'sn', 'hu', 'tr', 'wo', 'sp', 'pa', 'ai',
                     'wa', 'dr', 'de', 'li', 'gu']

        await ctx.send('{0.author.mention} has challenged {1.mention} to {2}.\n'
                       'Send \'a\' to accept.'.format(ctx, member, 'Sidasho'))

        # Send duel request
        def is_accept(m):
            return m.author == member and m.content.lower() == 'a'

        if member == self.bot.user:
            await ctx.send('a')
        else:
            while True:
                try:
                    await self.bot.wait_for('message', check=is_accept,
                                            timeout=10.0)
                    print("We made it")
                    break
                except asyncio.TimeoutError:
                    return await ctx.send(
                        'Sorry, you took too long, game cancelled')

        # Start game
        e = discord.Embed(title=f'{ctx.author} VS {member}',
                          description=f'Here are the possible moves:'
                                      f'\n{options[:-7]}'
                                      f'\nBoth players send your move in this chat',
                          colour=discord.Colour.purple())
        e.set_image(url='https://i.redd.it/zfqhu451s6931.jpg')

        await ctx.send("Starting Game...")
        await ctx.send(embed=e)
        await asyncio.sleep(1)

        def is_my_move(m):
            return (m.author == ctx.author and (m.content.lower() in options
                                                or m.content.lower() in s_options))

        def is_their_move(m):
            return m.author == member and (m.content.lower() in options
                                           or m.content.lower() in s_options)

        # Times is the timeout duration in seconds
        # Collect moves from players
        times = 5.0
        my_move = None
        their_move = None
        while True:
            try:
                if member == self.bot.user:
                    my_move = await self.bot.wait_for('message',
                                                      check=is_my_move,
                                                      timeout=times)
                    their_move = (await ctx.send(random.choice(options)))
                else:
                    r = await asyncio.gather(
                        self.bot.wait_for('message', check=is_my_move,
                                          timeout=times),
                        self.bot.wait_for('message', check=is_their_move,
                                          timeout=times))
                    for message in r:
                        if message.author == ctx.author:
                            my_move = message
                        elif message.author == member:
                            their_move = message
                break
            except asyncio.TimeoutError:
                return await ctx.send(
                    'One of the players didn\'t respond in time.'
                    ' Game was cancelled')

        if my_move.content.lower() == 'bogdan':
            my_move.content = options[12]
        if their_move.content.lower() == 'bogdan':
            their_move.content = options[12]

        # Convert moves to full names if applicable
        if my_move.content.lower() in s_options:
            if my_move.content.lower() == 'bo':
                my_move.content = options[12]
            else:
                my_move.content = options[s_options.index(my_move.content.lower())]
        if their_move.content.lower() in s_options:
            if their_move.content.lower() == 'bo':
                their_move.content = options[12]
            else:
                their_move.content = options[
                    s_options.index(their_move.content.lower())]

        # Display who wins
        def wins(move1: str, move2: str, index: int, winner):
            for j in range(1, 8):
                if options[index + j] == move2:
                    return ("{3}{1} beats {2}! {0} has won!".format(
                        winner.mention, move1[1:], move2,
                        move1[0].upper()))

        msg = None
        for i in range(len(options) - 7):
            if my_move.content.lower() == their_move.content.lower():
                return await ctx.send("It's a draw!")
            elif options[i] == my_move.content.lower():
                msg = wins(my_move.content.lower(), their_move.content.lower(),
                           i, ctx.author)
            elif options[i] == their_move.content.lower():
                msg = wins(their_move.content.lower(), my_move.content.lower(),
                           i, member)
            if msg is not None:
                return await ctx.send(msg)
        await ctx.send("We excited")


def setup(bot):
    bot.add_cog(Games(bot))



