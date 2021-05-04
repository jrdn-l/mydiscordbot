"""
Music bot based off of https://gist.github.com/EvieePy/ab667b74e9758433b3eb806c53a19f34

New commands have been added and somethings have been improved
"""
import discord
from discord.ext import commands
import random
import asyncio
import itertools
import sys
import traceback
from async_timeout import timeout
from functools import partial
from youtube_dl import YoutubeDL
import math

ytdlopts = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    #'verbose': True,
    'no_warnings': True,
    'cachedir': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn',
}

ytdl = YoutubeDL(ytdlopts)


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester
        self.title = data.get('title')
        self.web_url = data.get('webpage_url')
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.thumbnail = data.get('thumbnail')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        return cls(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS),
                   data=data, requester=ctx.author)

    @classmethod
    def check_playlist(cls, search: str):
        with ytdl:
            result = ytdl.extract_info(search, download=False, process=False)

            if result.get('_type') == 'playlist':
                return result['entries']
            elif result.get('extractor_key') != 'Youtube' and result.get('extractor_key') != 'Generic':
                return result
            else:
                with ytdl:
                    result = ytdl.extract_info(search, download=False)
                try:
                    return result['entries'][0]
                except:
                    return result

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} days'.format(days))
        if hours > 0:
            duration.append('{} hours'.format(hours))
        if minutes > 0:
            duration.append('{} minutes'.format(minutes))
        if seconds > 0:
            duration.append('{} seconds'.format(seconds))

        return ', '.join(duration)


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


class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = (
        'ctx', 'bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current',
        'np', 'volume', 'loop', 'loop_queue', 'song_info', 'skip', 'task', '_v_channel')

    def __init__(self, ctx):
        self.ctx = ctx
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._v_channel = ctx.author.voice.channel
        self._cog = ctx.cog

        self.queue = SongQueue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None
        self.loop = False
        self.loop_queue = SongQueue()
        self.song_info = None
        self.skip = False
        ctx.bot.loop.create_task(self.player_loop())



    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()
            if not self.loop or self.skip:
                try:
                    # Wait for the next song. If we timeout cancel the player and disconnect...
                    async with timeout(60):  # 1 minute...
                        s = await self.queue.get()
                except asyncio.TimeoutError:
                    if self in self._cog.players.values():
                        return self.destroy(self._guild)
                    return
                self.song_info = s

            while(True):
                try:
                    source = await self.get_source(s[0])
                    #print(s)
                    break
                except:

                    await self.ctx.send(f'Couldn\'t play ``{s[0].get("title")}``')
                    s = await self.queue.get()


            self.ctx = s[1]

            embed = self.embeded(source)

            source.volume = self.volume
            self.current = source
            self._guild.voice_client.play(source, after=self.play_next_song)
            if not self.loop or self.skip:
                self.np = await self._channel.send(embed=embed)
                self.skip = False

            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

            if not self.loop or self.skip:
                try:
                    # We are no longer playing this song...
                    await self.np.delete()
                except discord.HTTPException:
                    pass

            if not self.check_members():
                if self in self._cog.players.values():
                    return self.destroy(self._guild)
                return

    async def get_source(self, s):
        if s.get('extractor_key') is not None and s.get('extractor_key') != 'Youtube':
            return await YTDLSource.create_source(self.ctx, s['webpage_url'],
                                                  loop=self.bot.loop)
        else:
            try:
                return await YTDLSource.create_source(self.ctx,
                                                      s.get('id',
                                                            s['webpage_url']),
                                                      loop=self.bot.loop)
            except KeyError:
                return await YTDLSource.create_source(self.ctx,
                                                      s.get('id', s['url']),
                                                      loop=self.bot.loop)

    def embeded(self, source):
        embed = (discord.Embed(title='Now playing',
                               description=f'```css\n{source.title}\n```',
                               color=discord.Color.blurple())
                 .add_field(name='Duration', value=source.duration)
                 .add_field(name='Requested by', value=self.ctx.author.mention)
                 .add_field(name='Uploader',
                            value=f'[{source.uploader}]({source.uploader_url})')
                 .add_field(name='URL', value=f'[Click]({source.web_url})')
                 .set_thumbnail(url=source.thumbnail))
        return embed

    def play_next_song(self, error=None):
        if error:
            raise Exception(str(error))
        # self.bot.loop.call_soon_threadsafe(self.next.set)
        self.next.set()

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))

    def check_members(self):
        members = self._v_channel or []
        #print(self._v_channel.members)
        if members != []:
            members = members.members
            #print(members)
            for member in members:
                if not member.bot:
                    return True
        return False




class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        player = self.players.get(guild.id)
        if player is not None:
            player.queue.clear()
            player.loop = False
            player.skip = False

        try:
            del self.players[guild.id]
        except KeyError:
            pass



    async def __local_check(self, ctx: commands.Context):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx: commands.Context, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send(
                    'This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Error connecting to Voice Channel. '
                           'Please make sure you are in a valid channel or provide me with one')

        print('Ignoring exception in command {}:'.format(ctx.command),
              file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__,
                                  file=sys.stderr)

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx: commands.Context, *,
                       channel: discord.VoiceChannel = None):
        """Connect to voice channel specified, if none is specified it tries to join the voice channel you are currently connected to.
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise InvalidVoiceChannel(
                    'No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(
                    f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(
                    f'Connecting to channel: <{channel}> timed out.')

    @commands.command(name='splay', aliases=['shuffleplay'])
    async def _splay(self, ctx: commands.Context, *, search: str):
        """ Adds the song to the queue and then shuffles the queue.
        Works the same as the play command.
        Playlists will automatically be shuffled
        """
        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        player = self.get_player(ctx)
        queues = YTDLSource.check_playlist(search)
        counter = 0
        if not isinstance(queues, dict):
            for vid in queues:
                # print(vid)
                await player.queue.put((vid, ctx))
                player.queue.shuffle()
                counter += 1
        if counter == 0:
            await ctx.send(
                f'```ini\n[Added {queues["title"]} to the Queue.]\n```')
            await player.queue.put((queues, ctx))
            player.queue.shuffle()
        else:
            await ctx.send(
                f'```ini\n[Added {counter} songs to the Queue.]\n```')

    @commands.command(name='play', aliases=['sing'])
    async def play_(self, ctx: commands.Context, *, search: str):
        """Request a song and add it to the queue.
        This command attempts to join a valid voice channel if the bot is not already in one.
        The search can be a url, search or playlist on youtube.
        """
        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        player = self.get_player(ctx)
        queues = YTDLSource.check_playlist(search)
        counter = 0
        if not isinstance(queues, dict):
            for vid in queues:
                await player.queue.put((vid, ctx))
                counter += 1
        if counter == 0:
            await ctx.send(
                f'```ini\n[Added {queues["title"]} to the Queue.]\n```')
            await player.queue.put((queues, ctx))
        else:
            await ctx.send(
                f'```ini\n[Added {counter} songs to the Queue.]\n```')

    @commands.command(name='pause')
    async def pause_(self, ctx: commands.Context):
        """Pause the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('I am not currently playing anything!')
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.message.add_reaction('⏸')

    @commands.command(name='resume')
    async def resume_(self, ctx: commands.Context):
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.message.add_reaction('▶')

    @commands.command(name='skip')
    async def skip_(self, ctx: commands.Context):
        """Skip the song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')

        player = self.get_player(ctx)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        player.skip = True
        await ctx.message.add_reaction('⏭')

    @commands.command(name='queue', aliases=['q', 'playlist'])
    async def queue_info(self, ctx: commands.Context, *, page: int = 1):
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send(
                'I am not currently connected to voice!')  # , delete_after=20)

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send('There are currently no more queued songs.')

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(player.queue[start:end], start=start):
            queue += '`{0}.` [**{1}**]\n'.format(i + 1, song[0].get('title'))

        embed = (discord.Embed(
            description=f'**{len(player.queue)} tracks:**\n\n{queue}')
                 .set_footer(text=f'Viewing page {page}/{pages}'))
        await ctx.send(embed=embed)

    @commands.command()
    async def loop(self, ctx: commands.Context):
        """Loops the current song"""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')
        player = self.get_player(ctx)
        player.loop = not player.loop
        if player.loop:
            await ctx.message.add_reaction('✅')
        else:
            await ctx.message.add_reaction('❌')

    @commands.command()
    async def shuffle(self, ctx: commands.Context, *, t=''):
        """Shuffles the songs in the queue"""
        player = self.get_player(ctx)
        player.queue.shuffle()
        await ctx.message.add_reaction('✅')
        if t != '':
            await self.queue_info(ctx)

    @commands.command(name='removeall')
    async def clear_queue(self, ctx: commands.Context):
        """Clears all the songs in the queue"""
        player = self.get_player(ctx)
        player.queue.clear()

    @commands.command()
    async def remove(self, ctx: commands.Context, index: int):
        """Removes the song at the position number entered
        """
        player = self.get_player(ctx)
        if not isinstance(index, int):
            return await ctx.send(
                "That is not a valid song number in the queue")
        elif index > len(player.queue):
            return await ctx.send(f'There is no song at queue position{index}')
        player.queue.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='now_playing',
                      aliases=['np', 'current', 'currentsong', 'playing'])
    async def now_playing_(self, ctx: commands.Context):
        """Display information about the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send(
                'I am not currently connected to voice!')  # , delete_after=20)

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('I am not currently playing anything!')
        try:
            # Remove our previous now_playing message.
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send(embed=player.embeded(player.current))

    @commands.command(name='volume', aliases=['vol'])
    async def change_volume(self, ctx: commands.Context, *, vol: float):
        """Change the player volume. Volume must be between 0 and 100.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send(
                'I am not currently connected to voice!')  # , delete_after=20)

        if not 0 <= vol <= 100:
            return await ctx.send('Please enter a value between 0 and 100.')

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        await ctx.send(f'**`{ctx.author}`**: Set the volume to **{vol}%**')

    @commands.command(name='stop', aliases=['leave'])
    async def stop_(self, ctx: commands.Context):
        """Stop the currently playing song and leaves the voice Channel.
        Can also use leave.
        """
        await ctx.message.add_reaction("⏹")
        await self.cleanup(ctx.guild)

def setup(bot):
    bot.add_cog(Music(bot))
