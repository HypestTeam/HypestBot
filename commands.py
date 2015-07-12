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
import ranking as seasonal
import threading

# global configuration
conf = {}

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def update_config(conf):
    with open('config.json', 'wb') as out:
        json.dump(conf, out, sort_keys=True, indent=4, separators=(',', ': '))

def owners_only(command):
    """A decorator to make a command owner-only"""
    @wraps(command)
    def wrapped_up(bot):
        if bot.message.nick not in conf.get('owners', []):
            return irc.Response('Sorry, you are not an owner thus not authorised to use this command', pm_user=True)
        return command(bot)
    wrapped_up.owner_only = True
    return wrapped_up

def help_text(main=None, **text):
    """A decorator that provides help for a command and its subcommands.

       To provide help for the main command, the keyword argument used
       must be 'main' or none at all. The rest follow the subcommand=text pattern.
       For example, @help_text(main='does stuff', other='one', three='stuff')
       Would give you help text for !command, !command other, and !command three
       where ! is the irc.command_prefix

       If an argument is needed to be displayed in the command help output, then pass a tuple
       or list with two items with the extra information right before the text. For example:
       @help_text('hello', one=('<stuff>', 'does things') would result in the following string:
       !command one <stuff> -- does things

       The same principle applies with the main keyword argument."""

    main_is_verbose = isinstance(main, tuple) or isinstance(main, list)
    def actual_decorator(command):
        @wraps(command)
        def wrapper(bot):
            if len(bot.message.words) >= 2 and bot.message.words[1] == 'help':
                command_text = irc.command_prefix + command.__name__.lower()
                format_string = command_text + ' {subcommand} -- {help}'
                verbose_format = command_text + ' {subcommand} {help[0]} -- {help[1]}'
                if main:
                    if main_is_verbose:
                        bot.send_message(bot.message.nick, '{0} {1[0]} -- {1[1]}'.format(command_text, main))
                    else:
                        bot.send_message(bot.message.nick, ('{} -- {}'.format(command_text, main)))
                bot.send_message(bot.message.nick, format_string.format(subcommand='help', help='shows this message'))
                for subcommand in text:
                    value = text[subcommand]
                    temp = format_string
                    if isinstance(value, tuple) or isinstance(value, list):
                        temp = verbose_format
                    bot.send_message(bot.message.nick, temp.format(subcommand=subcommand, help=value))
            else:
                return command(bot)

        if main_is_verbose:
            wrapper.help = main[1]
        else:
            wrapper.help = main
        wrapper.subcommand_help = text
        return wrapper
    return actual_decorator

def requirements(length=2, subcommands=None):
    """A decorator to help with requirements in formatting for subcommands

       Currently supported are length and subcommands. length checks that there
       are at least length words passed while subcommands checks if the second word
       is in the list of valid options"""
    def actual_decorator(command):
        @wraps(command)
        def wrapper(bot):
            # check for length requirement
            command_name = irc.command_prefix + command.__name__.lower()
            number_of_words = len(bot.message.words)
            if number_of_words < length:
                temp = 'Incorrect number of arguments passed (received {}, expected {}). Try {} help'
                return irc.Response(temp.format(number_of_words, length, command_name), pm_user=True)

            # check for subcommand requirement
            if number_of_words >= 2 and subcommands and bot.message.words[1] not in subcommands:
                return irc.Response('Incorrect subcommand passed. Try {} help'.format(command_name), pm_user=True)

            return command(bot)
        return wrapper
    return actual_decorator

@help_text('shows a list of commands')
def botcommands(bot):
    bot.send_message(bot.message.nick, 'available commands:\n')
    is_owner = bot.message.nick in conf.get('owners', [])
    offset = len(max(bot.commands, key=lambda k: len(k))) + 2
    for key in bot.commands:
        command = bot.commands[key]
        is_owner_only = hasattr(command, 'owner_only')
        text = command.func_dict.get('help', None)
        format_string = '{command:<{offset}} -- {help}' if text else '{command:<{offset}}'
        if not is_owner and is_owner_only:
            continue
        bot.send_message(bot.message.nick, format_string.format(command=key, help=text, offset=offset))
    if len(bot.commands) == 0:
        bot.send_message(bot.message.nick, 'none found!')

@owners_only
@help_text('leaves the current channel')
def leave(bot):
    bot.disconnect(bot.current_channel, 'pew pew pew')

@owners_only
@help_text('quits the bot')
def quit(bot):
    bot.quit()

@help_text('provides the bracket for the current channel')
def bracket(bot):
    channel = bot.current_channel
    brackets = conf.get('bracket', None)
    if not channel.startswith('#'):
        return irc.Response('This command must be used outside of private messages', pm_user=True)

    if brackets == None:
        return irc.Response('Unknown bracket found, please see !change help')

    return irc.Response(brackets.get(channel, 'Unknown bracket found, please see !change help'))

@help_text('provides the rules for the current channel tournament')
def rules(bot):
    channel = bot.current_channel
    rules = conf.get('rules', None)
    if not channel.startswith('#'):
        return irc.Response('This command must be used outside of private messages', pm_user=True)

    if rules == None:
        return irc.Response('Unknown rules found, please see !change help')

    return irc.Response(rules.get(channel, 'Unknown rules found, please see !change help'))

@help_text('provides the Hypest official phonebook')
def phonebook(bot):
    return irc.Response('https://docs.google.com/spreadsheets/d/1dsoA_emnkmuroDZV9plDVPY-pQBtaUcnxLcaXQ7g06Y/')

@owners_only
@help_text('changes the bracket and rules URLs', bracket=('<url>', 'updates the brackets'), rules=('<url>', 'updates the rules'))
@requirements(length=3, subcommands=['bracket', 'rules'])
def change(bot):
    command = bot.message.words[1].lower()
    channel = bot.current_channel
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
@help_text('manages the list of owners', add=('<nick>', 'adds an owner'), remove=('<nick>', 'removes an owner'), list='lists the current owners')
@requirements(subcommands=['add', 'remove', 'list'], length=0)
def owners(bot):
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

@help_text('accesses ranking information for different games',**{
           '3ds': ('<challonge username>', 'Returns your ranking for Smash 3DS'),
           'wiiu': ('<challonge username>', 'Returns your ranking for Smash Wii U'),
           'melee': ('<challonge username>', 'Returns your ranking for Melee'),
           'brawl': ('<challonge username>', 'Returns your ranking for Brawl'),
           'ssf2': ('<challonge username>', 'Returns your ranking for Super Smash Flash 2'),
           '64': ('<challonge username>', 'Returns your ranking for Smash 64'),
           'projectm': ('<challonge username>', 'Returns your ranking for Project M'),
           })
@requirements(length=3, subcommands=['3ds', 'melee', 'wiiu', 'brawl', 'ssf2', '64', 'projectm'])
def rank(bot):
    directory = conf.get('ranking_directory', None)
    if directory == None or not os.path.exists(directory):
        return irc.Response('Internal error occurred: no directory for databases', pm_user=True)

    words = bot.message.text.split(' ')

    filename = seasonal.game_to_filename.get(words[1].lower(), None)
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

@help_text('lists current streams using the pastebin URL')
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
@help_text('prepares the bracket by seeding and removing banned users')
@requirements(length=2)
def prepare(bot):
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

    full_filename = os.path.join(directory, seasonal.game_to_filename.get(tournament['game_id'], None))
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
@help_text(main=('<username> <days> [reason]', 'bans players from participating in our tournaments'))
@requirements(length=3)
def banish(bot):
    if bot.message.text.strip() == '!banish':
        with open('bans.txt') as f:
            result = []
            for line in f:
                parts = shlex.split(line)
                result.append('{0[0]} is banned until {0[1]} for "{0[2]}"'.format(parts))
            return irc.Response('\n'.join(result), pm_user=True)

    words = bot.message.text.split(' ')
    with open('bans.txt', 'a') as f:
        end_date = dt.date.today() + dt.timedelta(days=int(words[2]))
        reason = ' '.join(words[3:])
        f.write('{} "{}" "{}"\n'.format(words[1], end_date.strftime('%B %d, %Y'), reason))

    return irc.Response('User {} successfully banished for {} days'.format(words[1], words[2]), pm_user=True)

@owners_only
@help_text(main=('<username>', 'unbans players'))
@requirements(length=2)
def unbanish(bot):
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
@help_text('helps debug the bot')
@requirements(subcommands=['print', 'execute'])
def debug(bot):
    words = bot.message.text.split(' ')
    if words[1] == 'print':
        if words < 4:
            return irc.Response('the print command required at least 2 more arguments', pm_user=True)
        subcommand = words[2]
        lookup = {
            'bot': bot,
            'message': bot.message
        }
        if subcommand not in lookup:
            return irc.Response('unknown debug subcommand ' + subcommand, pm_user=True)
        obj = lookup[subcommand]
        result = []
        for variable in words[3:]:
            if hasattr(obj, variable):
                attr = getattr(obj, variable)
                if callable(attr):
                    # call it with no arguments
                    result.append(str(attr()))
                else:
                    result.append(str(attr))
            else:
                result.append('no attribute found on {} for {}'.format(subcommand, variable))
        return irc.Response('\n'.join(result), pm_user=True)

    if words[1] == 'execute':
        if bot.message.nick != 'Rapptz':
            return irc.Response('The execute command is not allowed to be used.', pm_user=True)
        code = ' '.join(words[2:])
        result = eval(code)
        return irc.Response(str(result), pm_user=True)

@help_text('provides a URL to the phonebook form')
def form(bot):
    return irc.Response("http://goo.gl/CfFKeO")

@help_text('provides a URL to the FAQ')
def faq(bot):
    return irc.Response("http://goo.gl/EUbs9X")

@help_text('provides a URL our code of conduct')
def conduct(bot):
    return irc.Response("https://goo.gl/ga83zj")

@help_text('provides a URL to our IRC tutorial')
def tutorial(bot):
    return irc.Response("http://goo.gl/wRFPoU")

@help_text('provides a URL to the reddit rankings')
def ranking(bot):
    return irc.Response("http://www.reddit.com/r/smashbros/wiki/rankings")

@help_text('provides a URL to the event calendar')
def calendar(bot):
    return irc.Response("http://www.reddit.com/r/smashbros/wiki/eventcalendar")

@owners_only
def season_rank(bot):
    """Given a URL, updates the ranking"""
    if len(bot.message.words) < 3:
        return irc.Response('URL parameter is missing. The proper command is !season rank <url>', pm_user=True)
    try:
        seasonal.update_rankings(bot.message.words[2], conf['challonge'])
        return irc.Response('Successfully updated the seasonal rankings', pm_user=True)
    except Exception as e:
        return irc.Response('An error occurred: ' + str(e), pm_user=True)

@owners_only
def season_reset(bot):
    """Removes the filename"""
    with open('ssbwiiu.json', 'w') as f:
        f.write('{}')
    return irc.Response('Seasonal rankings successfully purged', pm_user=True)

def season_check(bot):
    """Checks the challonge username's ranking"""
    if len(bot.message.words) < 3:
        return irc.Response('Challonge username is missing. The proper command is !season check <challonge_username>', pm_user=True)

    ranking = seasonal.get_rankings("ssbwiiu.json")
    sorted_rankings = sorted(ranking.values(), reverse=True)
    username = bot.message.words[2]
    try:
        points = ranking[username]
        place = sorted_rankings.index(points)
        return irc.Response('{} is ranked {} out of {} players with {} points'.format(username, place + 1, len(ranking), points))
    except Exception as e:
        return irc.Response('Username {} not found. Note that usernames are case sensitive.'.format(username), pm_user=True)

def season_top(bot):
    """Returns a list of top players"""
    if len(bot.message.words) < 3:
        return irc.Response('Number to cut off is missing. The proper command is !season top <number> [condensed?]', pm_user=True)

    try:
        top_cut = int(bot.message.words[2])
        condensed = len(bot.message.words) >= 4 and bot.message.words[3].lower() in ('yes', 'true', '1')
        ranking = sorted(seasonal.get_rankings("ssbwiiu.json").items(), key=lambda x: x[1], reverse=True)
        separator = ', ' if condensed else '\n'
        ranking = ['{0[0]} ({0[1]} points)'.format(player) for player in ranking]
        return irc.Response(separator.join(ranking[:top_cut]), pm_user=True)
    except ValueError as e:
        return irc.Response('Number to cut off must be a number.', pm_user=True)


@help_text('manages the seasonal playoffs', rank=('<url>', 'updates the seasonal rankings with the given URL'),
           reset='resets the seasonal rankings', top=('<number> [condensed?]', 'returns the top number of players this season'),
           check=('<challonge_username>', 'checks your seasonal ranking placing'))
@requirements(length=2, subcommands=['rank', 'check', 'reset', 'top'])
def season(bot):
    # delegate work over to the sub functions
    return globals()['season_' + bot.message.words[1]](bot)

@owners_only
@help_text(main=('<minutes>', 'implements a timer to notify the user'))
@requirements(length=2)
def timer(bot):
    def notify(channel, user):
        lock = threading.Lock()
        with lock:
            bot.send_message(channel, 'Hello {}! Your timer is up!'.format(user))
    try:
        minutes = float(bot.message.words[1])
        t = threading.Timer(60.0 * minutes, notify, args=[bot.current_channel, bot.message.nick])
        t.start()
    except ValueError as e:
        return irc.Response('You must pass in a number of minutes', pm_user=True)

def register(bot):
    bot.add_command(botcommands)
    bot.add_command(quit)
    bot.add_command(leave)
    bot.add_command(bracket)
    bot.add_command(rules)
    bot.add_command(phonebook)
    bot.add_command(change)
    bot.add_command(owners)
    bot.add_command(streams)
    bot.add_command(rank)
    bot.add_command(prepare)
    bot.add_command(form)
    bot.add_command(banish)
    bot.add_command(unbanish)
    bot.add_command(faq)
    bot.add_command(conduct)
    bot.add_command(tutorial)
    bot.add_command(ranking)
    bot.add_command(calendar)
    bot.add_command(debug)
    bot.add_command(season)
    bot.add_command(timer)
