import re
import os
import hikari
import sqlite3
from collections import defaultdict

from videobin_bot.playlist import Playlist

bot = hikari.GatewayBot(token=os.environ["DISCORD_TOKEN"])
con = sqlite3.connect('bot.db')
cur = con.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY,
  channel INTEGER,
  url text
);
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS metadata (
  guild INTEGER PRIMARY KEY,
  channel INTEGER,
  playlist text
);
''')

# Save (commit) the changes
con.commit()

def set_videobin(guild_id, channel_id, playlist_id):
    with con:
        con.execute(
            """
            INSERT INTO metadata(guild, channel, playlist) VALUES(?, ?, ?)
              ON CONFLICT(guild) DO UPDATE SET channel=(?);
            """, 
            (guild_id, channel_id, playlist_id, channel_id)
        )

def get_metadata(guild_id):
    with con:
        return con.execute(
            "SELECT channel, playlist FROM metadata where guild = ?", (guild_id, )
        ).fetchone()

def videos(channel_id):
    return set(r[0] for r in con.execute("SELECT url from videos WHERE channel=?", (channel_id, )).fetchall())

def add_video(channel_id, url):
    with con:
        con.execute("INSERT INTO videos(channel, url) VALUES (?, ?)", (channel_id, url))

# https://stackoverflow.com/a/37704433
youtube_video_pattern = re.compile(r"((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)")

history = defaultdict(set)
target_cache = {}

@bot.listen()
async def ping(event: hikari.GuildMessageCreateEvent) -> None:
    if event.is_bot or not event.content:
        print('Abort!')
        return

    if event.guild_id in target_cache:
        target, playlist = target_cache[event.guild_id]
        playlist_id = playlist.playlist_id
    else:
        metadata = get_metadata(event.guild_id)
        if metadata:
            target, playlist_id = metadata
            playlist = Playlist(playlist_id)

            target_cache[event.guild_id] = (target, Playlist(playlist_id))
        else:
            target, playlist, playlist_id = None, None, None

    if event.content == ("!videobin"):
        new = not playlist
        channel = event.get_channel()
        if new:
            playlist = Playlist.create()
        await channel.edit(topic=f"https://www.youtube.com/playlist?list={playlist.playlist_id}")

        set_videobin(event.guild_id, event.channel_id, playlist.playlist_id)
        target_cache[event.guild_id] = (event.channel_id, playlist)
        history[event.channel_id] = videos(event.channel_id)
        async for message in channel.fetch_history():
            try:
                if event.content and (m := youtube_video_pattern.search(message.content)):
                    url = m.group()
                    if url not in history[event.channel_id]:
                        history[event.channel_id].add(url)
                        if new:
                            playlist.add(url)
                        add_video(event.channel_id, url)
            except TypeError:
                pass
    elif target is None or playlist is None or target != event.channel_id:
        return
    elif m := youtube_video_pattern.search(event.content):
        url = m.group()
        if url in history.setdefault(event.channel_id, videos(event.channel_id)):
            await event.message.delete()
            dm = await event.author.fetch_dm_channel()
            try:
                await dm.send(f"Hey! I just deleted your message in <#{event.channel_id}>, {url} is a duplicate")
            except hikari.errors.ForbiddenError:
                pass # User has DMs off
        else:
            add_video(event.channel_id, url)
            playlist.add(url)
            history[event.channel_id].add(url)
