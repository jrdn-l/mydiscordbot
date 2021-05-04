import discord
from discord.ext import commands
from discord import Game
import os


description = '''Jordan's discord bot that has been copied from the example 
template. This bot does have a few new commands though. '''
bot = commands.Bot(command_prefix='-', description=description)
bot.remove_command('help')
file = open('token.txt', 'r')
token = file.readline()

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=Game(name="-help"))
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


@bot.command()
async def add(ctx, left: int, right: int):
    """Adds two numbers together."""
    await ctx.send(left + right)


@bot.group()
async def cool(ctx):
    """Says if a user is cool.
    In reality this just checks if a subcommand is being invoked.
    """
    if ctx.invoked_subcommand is None:
        await ctx.send('No, {0.subcommand_passed} is not cool'.format(ctx))


@bot.command(name='bot')
async def _bot(ctx):
    """Is the bot cool?"""
    await ctx.send('Yes, the bot is cool.')



@bot.command(name='greeting')
async def greet(ctx):
    '''
    General reply greeting
    '''
    await ctx.send('Greetings {0.author.mention}'.format(ctx))


@bot.command()
async def idiot(ctx, member: discord.Member):
    """
    Says hello to the idiot mentioned
    """
    await ctx.send('Hello fellow idiot {0.mention}'.format(member))


@commands.has_permissions(manage_messages=True)
@bot.command(description='Clear <number> of messages in the channel called and '
                         'pinned messages if <pin> is False. '
                         'By default it clears 1000 lines and pin is True.')
async def clear(ctx, number=1000, pin=True):
    """
    Clears messages from chat
    """
    def is_pin(m):
        return not m.pinned

    number = int(number)  # Convert num of messages to delete into an int
    if pin:
        await ctx.channel.purge(limit=number, check=is_pin)
    else:
        await ctx.channel.purge(limit=number)

@bot.command(hidden=True)
async def load(ctx, extension):
    bot.load_extension(f'cogs.{extension}')
    await ctx.send("Loaded!")


@bot.command(hidden=True)
async def unload(ctx, extension):
    bot.unload_extension(f'cogs.{extension}')
    await ctx.send("Unloaded!")


for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')


bot.run(token)
