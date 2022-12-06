import datetime
import os
import sched
import time
import json
import urllib.request
import schedule
from time import gmtime, strftime
from datetime import datetime, timedelta
import asyncio

from discord.ext import commands, tasks
import discord

# Load the variables
dotenv = Dotenv('.env')
TOKEN = dotenv['DISCORD_TOKEN']
URL = dotenv['AOC_URL']
COOKIE = dotenv['AOC_COOKIE']

# Advent Of Code request that you don't poll their API more often than once every 15 minutes
POLL_MINS = 15

# Discord messages are limited to 2000 characters. This also includes space for 6 '`' characters for a code block
MAX_MESSAGE_LEN = 2000 - 6

PLAYER_STR_FORMAT = '{rank:2}) {name:{name_pad}} ({points:{points_pad}}) {stars:{stars_pad}}* ({star_time})\n'

# A cache to make sure we do not need to poll the Advent of Code API within 15 min
players_cache = ()

# CH channel name for AOC
CHANNEL_ID = 912708047141486592
NUM_PLAYERS = 20


def get_players():
    global players_cache
    now = time.time()
    debug_msg = 'Got Leader board From Cache'

    # If the cache is more than POLL_MINS old, refresh the cache, else use the cache
    if not players_cache or (now - players_cache[0]) > (60 * POLL_MINS):
        debug_msg = 'Got Leader board Fresh'

        req = urllib.request.Request(URL)
        req.add_header('Cookie', 'session=' + COOKIE)
        page = urllib.request.urlopen(req).read()

        data = json.loads(page)

        # Extract the data from the JSON
        players = [(member['name'],
                    member['local_score'],
                    member['stars'],
                    int(member['last_star_ts']),
                    member['completion_day_level'],
                    member['id']) for member in data['members'].values()]

        # Players that are anonymous have no name in the JSON, so give them a default name "Anon"
        for i, player in enumerate(players):
            if not player[0]:
                anon_name = "anon #" + str(player[5])
                players[i] = (anon_name, player[1], player[2], player[3], player[4], player[5])

        # Sort the table primarily by score, secondly by stars and finally by timestamp
        players.sort(key=lambda tup: tup[3])
        players.sort(key=lambda tup: tup[2], reverse=True)
        players.sort(key=lambda tup: tup[1], reverse=True)
        players_cache = (now, players)

    print(debug_msg)
    return players_cache[1]


async def output_leader_board(leader_board_lst):
    item_len = len(leader_board_lst[0])
    block_size = MAX_MESSAGE_LEN // item_len

    tmp_leader_board = leader_board_lst
    message_channel = bot.get_channel(CHANNEL_ID)

    while (len(tmp_leader_board) * item_len) > MAX_MESSAGE_LEN:
        output_str = '```'
        output_str += ''.join(tmp_leader_board[:block_size])
        output_str += '```'
        await message_channel.send(output_str)
        tmp_leader_board = tmp_leader_board[block_size:]
    output_str = '```'
    output_str += ''.join(tmp_leader_board)
    output_str += '```'
    await message_channel.send(output_str)


async def leader_board(num_players: int = 20):
    print('Leader board requested')
    players = get_players()[:num_players]

    # Get string lengths for the format string
    max_name_len = len(max(players, key=lambda t: len(t[0]))[0])
    max_points_len = len(str(max(players, key=lambda t: t[1])[1]))
    max_stars_len = len(str(max(players, key=lambda t: t[2])[2]))

    leader_board = []
    for i, player in enumerate(players):
        leader_board.append(PLAYER_STR_FORMAT.format(rank=i + 1,
                                                     name=player[0], name_pad=max_name_len,
                                                     points=player[1], points_pad=max_points_len,
                                                     stars=player[2], stars_pad=max_stars_len,
                                                     star_time=time.strftime('%H:%M %d/%m', time.localtime(player[3]))))

    await output_leader_board(leader_board)


async def keen():
    print('Keenest bean requested')

    all_players = get_players()
    # Calculate the highest number of stars gained by anyone in the leader board
    max_stars = max(all_players, key=lambda t: t[2])[2]
    # Get list of players with max stars
    players = [(i, player) for i, player in enumerate(all_players) if player[2] == max_stars]

    # Find the first person who got the max stars
    i, player = min(players, key=lambda t: t[1][3])

    result = 'Today\'s keenest bean is:\n```'
    result += PLAYER_STR_FORMAT.format(rank=i + 1,
                                       name=player[0], name_pad=len(player[0]),
                                       points=player[1], points_pad=len(str(player[1])),
                                       stars=player[2], stars_pad=len(str(player[2])),
                                       star_time=time.strftime('%H:%M %d/%m', time.localtime(player[3])))
    result += '```'
    message_channel = bot.get_channel(CHANNEL_ID)
    await message_channel.send(result)


# Create the bot and specify to only look for messages starting with '!'
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord and is in the following channels:')
    for guild in bot.guilds:
        print('  ', guild.name)


def seconds_until_9():
    now = datetime.now()
    target = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    diff = (target - now).total_seconds()
    print(f"{target} - {now} = {diff}")
    return diff


@tasks.loop(seconds=60)
async def daily_leaderboard():
    await asyncio.sleep(seconds_until_9())
    message_channel = bot.get_channel(CHANNEL_ID)
    print(f"Got channel {message_channel}")
    await leader_board(NUM_PLAYERS)
    await keen()


@daily_leaderboard.before_loop
async def before():
    await bot.wait_until_ready()
    print("Finished waiting")


bot.run(TOKEN)
