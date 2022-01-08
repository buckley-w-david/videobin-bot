import re
import os
import hikari
import sqlite3
from collections import defaultdict

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
  channel INTEGER
);
''')

# Save (commit) the changes
con.commit()

def set_videobin(guild_id, channel_id):
    with con:
        con.execute(
            """
            INSERT INTO metadata(guild, channel) VALUES(?, ?)
              ON CONFLICT(guild) DO UPDATE SET channel=(?);
            """, 
            (guild_id, channel_id, channel_id)
        )

def get_channel(guild_id):
    with con:
        res = con.execute(
            "SELECT channel FROM metadata where guild = ?", (guild_id, )
        ).fetchone()
        if res:
            return res[0]

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

    target = target_cache.setdefault(event.guild_id, get_channel(event.guild_id))

    if event.content == ("!videobin"):
        set_videobin(event.guild_id, event.channel_id)
        target_cache[event.guild_id] = event.channel_id
        history[event.channel_id] = videos(event.channel_id)
        async for message in event.get_channel().fetch_history():
            try:
                if event.content and (m := youtube_video_pattern.search(message.content)):
                    url = m.group()
                    if url not in history[event.channel_id]:
                        history[event.channel_id].add(url)
                        add_video(event.channel_id, url)
            except TypeError:
                pass
    elif target is None or target != event.channel_id:
        print('Abort!')
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
            history[event.channel_id].add(url)
