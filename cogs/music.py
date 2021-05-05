import discord
import youtube_dl
import itertools
import random
from async_timeout import timeout
import math
from functools import partial
from discord.ext import commands
import asyncio

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'cachedir': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
    # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        to_run = partial(ytdl.extract_info, url, download=False)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url']
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options),
                   data=data)

    @staticmethod
    async def url_no_process(url):
        with ytdl:
            result = ytdl.extract_info(url, download=False, process=False)
            if result.get('_type') == 'playlist':
                ls = []
                for item in result['entries']:
                    ls.append({'title': item['title'], 'url': item['url']})
                return {'title': result['title'], 'url': result['webpage_url'],
                        'playlist': ls}
            elif result.get('extractor_key') != 'Generic':
                return {'title': result['title'], 'url': result['webpage_url']}
            else:
                result = ytdl.extract_info(url, download=False)
                info = result['entries'][0]
                return {'title': info['title'], 'url': info['webpage_url']}


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(
                itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playerInfo = {}

    def get_player(self, ctx):
        if self.playerInfo.get(ctx.guild.id) is None:
            self.playerInfo[ctx.guild.id] = {"loop": False,
                                             "queue": SongQueue(),
                                             "skip": False,
                                             'current': ''}
        return self.playerInfo[ctx.guild.id]

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    def set_next(self, ctx, url, player):
        if ctx.voice_client is None:
            return
        if player['loop'] and not player['skip']:
            self.bot.loop.create_task(self.play(ctx=ctx, url=url))
        elif not player['queue'].empty():
            self.bot.loop.create_task(self.play(ctx=ctx, url=None))
        player["skip"] = False

    @commands.command()
    async def play(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""
        player = self.get_player(ctx=ctx)

        if url is not None:
            check = await YTDLSource.url_no_process(url)
            if 'playlist' in check:
                for entry in check['playlist']:
                    await player["queue"].put(entry)
            if ctx.voice_client.is_playing():
                await player["queue"].put(check)
                await ctx.send("Added to queue")
                return
            async with ctx.typing():
                source = await YTDLSource.from_url(url, loop=self.bot.loop)
                ctx.voice_client.play(source,
                                      after=lambda e: self.set_next(ctx, url,
                                                                    player))
                await ctx.send(f'Now playing: {source.title}')
        else:
            url = await player['queue'].get()
            url = url['url']
            async with ctx.typing():
                source = await YTDLSource.from_url(url, loop=self.bot.loop)
                ctx.voice_client.play(source,
                                      after=lambda e: self.set_next(ctx, url,
                                                                    player))
                await ctx.send(f'Now playing: {source.title}')

    @commands.command()
    async def loop(self, ctx):
        player = self.get_player(ctx=ctx)
        if not player['loop']:
            await ctx.message.add_reaction('✅')
        else:
            await ctx.message.add_reaction('❌')
        player["loop"] = not player["loop"]

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f'changed volume to {volume}%')

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        player = self.get_player(ctx=ctx)
        await ctx.message.add_reaction("⏹")
        await ctx.voice_client.disconnect()
        player["queue"].clear()
        player["loop"] = False
        player["skip"] = False

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client.is_playing():
            await ctx.voice_client.resume()
            await ctx.message.add_reaction('▶')
        else:
            await ctx.send("I am not paused")

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client.is_playing():
            await ctx.voice_client.pause()
            await ctx.message.add_reaction('⏸')
        else:
            await ctx.send("I am not playing anything")

    @commands.command()
    async def skip(self, ctx):
        player = self.get_player(ctx)
        await ctx.message.add_reaction('⏭')
        ctx.voice_client.source = discord.AudioSource()
        player["skip"] = True

    @commands.command(aliases=['q', 'playlist'])
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send(
                'I am not currently connected to voice!')  # , delete_after=20)

        player = self.get_player(ctx)
        if player["queue"].empty():
            return await ctx.send('There are currently no more queued songs.')

        items_per_page = 10
        pages = math.ceil(len(player['queue']) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        q = ''
        for i, song in enumerate(player["queue"][start:end], start=start):
            q += f'`{i + 1}.` [**{song.get("title")}**]\n'

        embed = (discord.Embed(
            description=f'**{len(player["queue"])} tracks:**\n\n{q}')
                 .set_footer(text=f'Viewing page {page}/{pages}'))
        await ctx.send(embed=embed)

    @commands.command()
    async def shuffle(self, ctx, view: bool = False):
        player = self.get_player(ctx)
        player["queue"].shuffle()
        await ctx.message.add_reaction('✅')
        if view:
            await self.queue(ctx)

    @commands.command(name='removeall')
    async def clear_queue(self, ctx: commands.Context):
        """Clears all the songs in the queue"""
        player = self.get_player(ctx)
        player['queue'].clear()

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError(
                    "Author not connected to a voice channel.")


def setup(bot):
    bot.add_cog(Music(bot))
