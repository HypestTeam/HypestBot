#!/usr/bin/env python

import irc
import json
import urllib
import csv
import re, os, sys
import time
import codecs
import datetime as dt
import shlex
import requests
from collections import namedtuple
from functools import wraps
from ranking import *

# global configuration
conf = {}

def owners_only(command):
    """A decorator to make a command owner-only"""
    @wraps(command)
    def wrapped_up(bot):
        if bot.message.nick not in conf.get('owners', []):
            return irc.Response('Sorry, you are not an owner thus not authorised to use this command', pm_user=True)
        return command(bot)
    wrapped_up.owner_only = True
    return wrapped_up

def botcommands(bot):
    bot.send_message(bot.message.nick, 'available commands:\n')
    is_owner = bot.message.nick in conf.get('owners', [])

    for key in bot.commands:
        value = bot.commands[key]
        is_owner_only = hasattr(value['command'], 'owner_only')
        text = value.get('help', None)
        format_string = '{command} -- {help}' if text else '{command}'
        if not is_owner and is_owner_only:
            continue
        bot.send_message(bot.message.nick, format_string.format(command=key, help=text))
    if len(bot.commands) == 0:
        bot.send_message(bot.message.nick, 'none found!')

@owners_only
def leave(bot):
    bot.disconnect(bot.current_channel, 'pew pew pew')

@owners_only
def quit(bot):
    bot.quit()

def bracket(bot):
    channel = bot.current_channel
    brackets = conf.get('bracket', None)
    if not channel.startswith('#'):
        return irc.Response('This command must be used outside of private messages', pm_user=True)

    if brackets == None:
        return irc.Response('Unknown bracket found, please see !change help')

    return irc.Response(brackets.get(channel, 'Unknown bracket found, please see !change help'))

def rules(bot):
    channel = bot.current_channel
    rules = conf.get('rules', None)
    if not channel.startswith('#'):
        return irc.Response('This command must be used outside of private messages', pm_user=True)

    if rules == None:
        return irc.Response('Unknown rules found, please see !change help')

    return irc.Response(rules.get(channel, 'Unknown rules found, please see !change help'))

def phonebook(bot):
    return irc.Response('https://docs.google.com/spreadsheets/d/1dsoA_emnkmuroDZV9plDVPY-pQBtaUcnxLcaXQ7g06Y/')

@owners_only
def change(bot):
    if bot.message.text == '!change help':
        return irc.Response('!change bracket <url> -- updates the brackets\n!change rules <url> -- updates the rules\n', pm_user=True)

    words = len(bot.message.words)
    if words != 3:
        return irc.Response('Invalid amount of parameters (expected 3, received {}) check !change help'.format(words), pm_user=True)

    command = bot.message.words[1].lower()
    channel = bot.current_channel
    if command not in ['bracket', 'rules']:
        return irc.Response('Invalid command given (!change {}) check !change help'.format(command), pm_user=True)

    if not channel.startswith('#'):
        return irc.Response('This command must be used outside of private messages', pm_user=True)

    info = conf.get(command, None)
    if info == None:
        info = { channel: bot.message.words[2] }
    elif isinstance(info, dict):
        info[channel] = bot.message.words[2]
    else:
        return irc.Response('Unable to update {} due to invalid configuration type'.format(command))
    conf[command] = info
    update_config(conf)
    return irc.Response('Successfully updated', pm_user=True)

@owners_only
def owners(bot):
    if bot.message.text == '!owners help':
        return irc.Response('!owners add <nick> -- adds an owner\n!owners remove <nick> -- removes an owner'\
                            '!owners -- lists all current owners', pm_user=True)

    args = len(bot.message.words)
    if args == 1:
        return irc.Response('list of owners:\n' + '\n'.join(list_of_owners), pm_user=True)
    elif args != 3:
        return irc.Response('Invalid amount of parameters (expected 3, received {}) check !owners help'.format(args), pm_user=True)

    command = bot.message.words[1].lower()
    if command not in ['add', 'remove']:
        return irc.Response('Invalid command given ({}) check !owners help'.format(command), pm_user=True)

    owner = bot.message.words[2]
    if command == 'add':
        list_of_owners.append(owner)
    elif command == 'remove':
        if owner not in list_of_owners:
            return irc.Response('Owner "{}" not found (note this is case sensitive)'.format(owner), pm_user=True)
        list_of_owners.remove(owner)

    conf['owners'] = list_of_owners
    update_config(conf)
    return irc.Response('Successfully updated', pm_user=True)

def rank(bot):
    directory = conf.get('ranking_directory', None)
    if directory == None or not os.path.exists(directory):
        return irc.Response('Internal error occurred: no directory for databases', pm_user=True)

    if bot.message.text == '!rank help':
        resp = [ '!rank 3ds <challonge username> -- Returns your ranking for Smash 3DS',
                 '!rank wiiu <challonge username> -- Returns your ranking for Smash Wii U',
                 '!rank melee <challonge username> -- Returns your ranking for Melee',
                 '!rank brawl <challonge username> -- Returns your ranking for Brawl',
                 '!rank ssf2 <challonge username> -- Returns your ranking for Super Smash Flash 2',
                 '!rank 64 <challonge username> -- Returns your ranking for Smash 64',
                 '!rank projectm <challonge username> -- Returns your ranking for Project M'
               ]
        return irc.Response('\n'.join(resp), pm_user=True)

    words = bot.message.text.split(' ')
    if len(words) != 3:
        return irc.Response('Invalid format given. Check !rank help for more info', pm_user=True)

    filename = game_to_filename.get(words[1].lower(), None)
    if filename == None:
        return irc.Response('Invalid game given. Check !rank help for more info', pm_user=True)

    full_filename = os.path.join(directory, filename)

    if not os.path.exists(full_filename):
        return irc.Response('Internal error occurred: no database file found', pm_user=True)

    db = {}
    with open(full_filename, 'r') as f:
        db = json.loads(f.read().decode('utf-8-sig'))

    db = dict((k.lower(), v) for k, v in db.iteritems())

    entry = db.get(words[2].lower(), None)
    if entry == None:
        return irc.Response('No entry found for ' + words[2], pm_user=True)

    valid_keys = ['losses', 'wins', 'rating', 'ties', 'challonge_username']
    for key in valid_keys:
        if key not in entry:
            return irc.Response('Internal error: incomplete entry found for ' + words[2], pm_user=True)

    # create the rankings list
    ranking = sorted(db.values(), key=lambda e: e['rating'], reverse=True)
    ranking = [x['challonge_username'] for x in ranking]
    # check the player placing
    stats = 'Rating: {0} (Wins: {1}, Losses: {2}, Ties: {3}) [W/L Ratio: {4:.2}]'
    ratio = float(entry['wins']) if entry['losses'] == 0 else float(entry['wins'])/entry['losses']
    stats = stats.format(entry['rating'], entry['wins'], entry['losses'], entry['ties'], ratio)

    try:
        place = ranking.index(entry['challonge_username'])
        placing = 'User {2} is ranked {0} out of {1} players.\n'.format(place + 1, len(ranking), entry['challonge_username'])
        return irc.Response(placing + stats, pm_user=True)
    except Exception as e:
        return irc.Response(stats, pm_user=True)

def streams(bot):
    result = []
    pastebin = "http://pastebin.com/raw.php?i=x5qCS5Gz"
    data = urllib.urlopen(pastebin)
    reader = csv.reader(data)
    round_filter = None
    if len(bot.message.words) > 1:
        round_filter = bot.message.words[1]
    for row in reader:
        if round_filter != None and row[0] != round_filter:
            continue
        result.append('{a[0]:<10} {a[1]:<10} {a[2]:<10}'.format(a=row))

    return irc.Response('\n'.join(result))

# prepares the bracket by seeding and removing banned players
@owners_only
def prepare(bot):
    if len(bot.message.words) != 2:
        return irc.Response('Incorrect format. Must be !prepare <url>', pm_user=True)

    directory = conf.get('ranking_directory', None)
    if directory == None or not os.path.exists(directory):
        return irc.Response('No ranking database has been found. Sorry.', pm_user=True)

    api_key =conf.get('challonge', None)
    if api_key == None:
        return irc.Response('No Challonge API key has been set in config', pm_user=True)

    m = re.match(r'(?:https?\:\/\/)?(?:(?P<subdomain>\w*)\.)?challonge\.com\/(?P<url>\w*)', bot.message.words[1])
    url = m.group('url')
    if m.group('subdomain'):
        url = '{}-{}'.format(m.group('subdomain'), m.group('url'))


    params = {
        'api_key': api_key,
        'include_participants': '1'
    }

    participants = requests.get('https://api.challonge.com/v1/tournaments/{}.json'.format(url), params=params)
    if participants.status_code != 200:
        return irc.Response('Unable to access challonge API [error: {}]'.format(participants.text), pm_user=True)
    js = participants.json()

    tournament = js['tournament']

    if tournament['state'] == 'complete':
        return irc.Response('Tournament is already complete', pm_user=True)
    elif tournament['state'] != 'checked_in':
        return irc.Response('Check ins have not been processed yet', pm_user=True)

    full_filename = os.path.join(directory, game_to_filename.get(tournament['game_id'], None))
    if full_filename == None or not os.path.exists(full_filename):
        return irc.Response('Hypest Database file not found', pm_user=True)

    db = {}
    with open(full_filename) as f:
        db = json.loads(f.read().decode('utf-8-sig'))

    # get a mapping of (challonge_username, participant_id, rating)
    User = namedtuple('User', ['name', 'id', 'rating'])
    users = []
    for obj in tournament['participants']:
        participant = obj['participant']
        if participant.get('checked_in', False):
            name = participant["challonge_username"]
            pid = participant["id"]
            rating = db.get(name, None)
            if rating == None:
                users.append(User(name=name, id=pid, rating=0))
            else:
                users.append(User(name=name, id=pid, rating=rating['rating']))


    # sort the users by their rating score
    users.sort(key=lambda x: x.rating, reverse=True)

    # just stores the banned usernames for quick lookup
    banned_usernames = []

    if os.path.exists('bans.txt'):
        # obtain the list of banned users
        Ban = namedtuple('Ban', ['challonge', 'end', 'reason'])
        bans = []
        old_ban_lines = 0
        with open('bans.txt') as ban_file:
            today = dt.date.today()
            for line in ban_file:
                old_ban_lines += 1
                parts = shlex.split(line)
                ban = Ban(challonge=parts[0], end=dt.datetime.strptime(parts[1], '%B %d, %Y').date(), reason=parts[2])
                if ban.end > today:
                    bans.append(ban)


        # update the bans.txt file with the list of currently banned users
        # effectively removing the now unbanned users
        if old_ban_lines != len(bans):
            with open('bans.txt', 'w') as f:
                for ban in bans:
                    f.write('{} "{}" "{}"\n'.format(ban.challonge, ban.end.strftime('%B %d, %Y'), ban.reason))
                    banned_usernames.append(ban.challonge)

    # update the seed based on position on the list
    # the seeds.txt file is used as a way to debug if something goes wrong in the future
    f = open('seeds.txt', 'w')
    seed = 1
    removed_users = []
    for user in users:
        params = {
            'api_key': api_key
        }

        # check if a user is banned, and if so remove them from the seeding calculation
        if user.name in banned_usernames:
            removed_users.append(user.name)
            r = requests.delete('https://api.challonge.com/v1/tournaments/{}/participants/{}.json'.format(url, user.id), params=params)
            if r.status_code != 200:
                return irc.Response('Unable to access challonge API [error: {}]'.format(r.text), pm_user=True)
            continue

        f.write('{} has a seed of {}\n'.format(str(user), seed))
        params['participant[seed]'] = seed
        r = requests.put('https://api.challonge.com/v1/tournaments/{}/participants/{}.json'.format(url, user.id), params=params)
        if r.status_code != 200:
            return irc.Response('Unable to access challonge API [error: {}]'.format(r.text), pm_user=True)
        seed += 1

    # prepare statistics
    result = [ 'Tournament has successfully been prepared' ]
    newcomers = sum(1 for user in users if user.rating == 0)
    result.append('Total number of participants: {}'.format(len(users)))
    result.append('Newcomers joined: {}'.format(newcomers))
    result.append('Frequent users: {}'.format(len(users) - newcomers))
    result.append('Users removed due to ban: {}'.format(len(removed_users)))
    if len(removed_users) > 0:
        result.append('These users were: {}'.format(', '.join(removed_users)))

    return irc.Response('\n'.join(result), pm_user=True)

@owners_only
def banish(bot):
    if bot.message.text == '!banish help':
        return irc.Response('!banish <username> <days> [reason]-- bans a challonge username for days length', pm_user=True)

    if bot.message.text.strip() == '!banish':
        with open('bans.txt') as f:
            result = []
            for line in f:
                parts = shlex.split(line)
                result.append('{0[0]} is banned until {0[1]} for "{0[2]}"'.format(parts))
            return irc.Response('\n'.join(result), pm_user=True)

    words = bot.message.text.split(' ')
    if len(words) < 3:
        return irc.Response('Incorrect format. Check !banish help for more info', pm_user=True)

    with open('bans.txt', 'a') as f:
        end_date = dt.date.today() + dt.timedelta(days=int(words[2]))
        reason = ' '.join(words[3:])
        f.write('{} "{}" "{}"\n'.format(words[1], end_date.strftime('%B %d, %Y'), reason))

    return irc.Response('User {} successfully banished for {} days'.format(words[1], words[2]), pm_user=True)

@owners_only
def unbanish(bot):
    if bot.message.text == '!unbanish help':
        return irc.Response('!unbanish <username> -- prematurely unbans a challonge username', pm_user=True)

    words = bot.message.text.split(' ')
    if len(words) != 2:
        return irc.Response('Incorrect format. Check !unbanish help for more info', pm_user=True)

    bans = ''
    with open('bans.txt') as f:
        bans = filter(lambda x: words[1] not in x, f.readlines())

    with open('bans.txt', 'w') as f:
        f.write(''.join(bans))

    return irc.Response('User {} successfully unbanished'.format(words[1]), pm_user=True)

@owners_only
def delta(bot):
    current_time = dt.datetime.now()
    round_end = current_time + dt.timedelta(minutes=40)
    game_one_end = current_time + dt.timedelta(minutes=10)
    round_loss = current_time + dt.timedelta(minutes=15)
    time_format = '%I:%M:%S %p'
    result = []
    result.append('Current Time: {}'.format(current_time.strftime(time_format)))
    result.append('Game 1 loss is given at {}'.format(game_one_end.strftime(time_format)))
    result.append('Entire round loss is given at {}'.format(round_loss.strftime(time_format)))
    result.append('Round ends at {}'.format(round_end.strftime(time_format)))
    return irc.Response('\n'.join(result), pm_user=True)


# The 'season' command will be split up into multiple subcommands
# These could be invoked via season_<type>(bot) in a semi-dynamic fashion.
# But for now just get something basic going
# @owners_only
# def season_rank(bot):
#
#
# def season(bot):


def form(bot):
    return irc.Response("http://goo.gl/CfFKeO")

def faq(bot):
    return irc.Response("http://goo.gl/EUbs9X")

def conduct(bot):
    return irc.Response("https://goo.gl/ga83zj")

def tutorial(bot):
    return irc.Response("http://goo.gl/wRFPoU")

def ranking(bot):
    return irc.Response("http://www.reddit.com/r/smashbros/wiki/rankings")

def calendar(bot):
    return irc.Response("http://www.reddit.com/r/smashbros/wiki/eventcalendar")

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def update_config(conf):
    with open('config.json', 'wb') as out:
        json.dump(conf, out, sort_keys=True, indent=4, separators=(',', ': '))

if __name__ == '__main__':
    conf = load_config()
    reload(sys)
    sys.setdefaultencoding('utf-8')
    bot = irc.Bot(**conf)
    bot.add_command(botcommands, 'shows a list of commands')
    bot.add_command(quit, 'quits the bot')
    bot.add_command(leave, 'leaves the current channel')
    bot.add_command(bracket, 'provides the bracket for the channel')
    bot.add_command(rules, 'provides the rules for the channel tournament')
    bot.add_command(phonebook, 'provides the Hypest official phonebook')
    bot.add_command(change, 'changes the bracket and rules URLs')
    bot.add_command(owners, 'manages the list of owners')
    bot.add_command(streams, 'lists current streams using the pastebin URL')
    bot.add_command(rank, 'accesses ranking information for different games')
    bot.add_command(prepare, 'prepares the bracket by seeding and removing banned users')
    bot.add_command(delta, 'provides a delta time to help with tournament organising')
    bot.add_command(form, 'provides the phonebook form')
    bot.add_command(banish, 'bans players from participating in our tournaments')
    bot.add_command(unbanish, 'unbans players')
    bot.add_command(faq, 'provides the FAQ')
    bot.add_command(conduct, 'provides our code of conduct')
    bot.add_command(tutorial, 'provides our IRC tutorial')
    bot.add_command(ranking, 'provides the reddit rankings')
    bot.add_command(calendar, 'provides the event calendar')
    bot.run()
