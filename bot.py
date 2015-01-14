#!/usr/bin/env python

import irc
import json
import urllib
import csv
import re, os
import codecs
import requests
from collections import namedtuple

# global configuration
conf = {}

def bracket(message):
    # just posts the url
    return irc.Response(conf.get('bracket', 'Unknown please see !change help'))

def rules(message):
    # posts the rules
    return irc.Response(conf.get('rules', 'Unknown please see !change help'))

def phonebook(message):
    # posts the phonebook
    return irc.Response('https://docs.google.com/spreadsheets/d/1dsoA_emnkmuroDZV9plDVPY-pQBtaUcnxLcaXQ7g06Y/')

def tps(message):
    p = conf.get('tps', None)
    if p == None or not os.path.exists(p):
        return irc.Response('No TPS database has been found. Sorry.', pm_user=True)

    if message.text == '!tps help':
        return irc.Response('!tps <challonge username> -- returns your TPS (Tournament Participation Score)\n'\
                            '!tps <challonge username> place -- returns your placing in the TPS leaderboards', pm_user=True)

    words = message.text.split(' ')
    if len(words) == 1:
        return irc.Response('Invalid format given. Check !tps help', pm_user=True)

    username = words[1].lower()
    check_place = len(words) == 3 and words[2] == 'place'

    db = {}
    with codecs.open(p, 'r', 'utf-8') as f:
        db = json.load(f)

    score = db.get(username, 1000)
    if check_place:
        scores = sorted(db.values(), reverse=True)
        try:
            place = scores.index(score)
            return irc.Response('User {} is {}/{} place with a TPS of {}'.format(username, place, len(scores), score), pm_user=True)
        except Exception as e:
            return irc.Response('Placing not found for user {}.'.format(username), pm_user=True)

    return irc.Response('User {} has a TPS of {}'.format(username, score), pm_user=True)


def change(message):
    # allows 'owners' to modify the database
    # if you're not an owner, so just ignore the message
    if message.nick not in conf.get('owners', []):
        return irc.Response('Sorry, you are not an owner thus not authorised to use this command', pm_user=True)

    if message.text == '!change help':
        return irc.Response('!change bracket <url> -- updates the brackets\n!change rules <url> -- updates the rules\n', pm_user=True)

    words = len(message.words)
    if words != 3:
        return irc.Response('Invalid amount of parameters (expected 3, received {}) check !change help'.format(words), pm_user=True)

    command = message.words[1].lower()
    if command not in ['bracket', 'rules']:
        return irc.Response('Invalid command given (!change {}) check !change help'.format(command), pm_user=True)

    conf[command] = message.words[2]
    update_config(conf)
    return irc.Response('Successfully updated', pm_user=True)

def owners(message):
    list_of_owners = conf.get('owners', [])
    # allows an owner to modify the owner list
    if message.nick not in list_of_owners:
        return irc.Response('Sorry, you are not an owner thus not authorised to use this command', pm_user=True)

    if message.text == '!owners help':
        return irc.Response('!owners add <nick> -- adds an owner\n!owners remove <nick> -- removes an owner'\
                            '!owners -- lists all current owners', pm_user=True)

    args = len(message.words)
    if args == 1:
        return irc.Response('list of owners:\n' + '\n'.join(list_of_owners), pm_user=True)
    elif args != 3:
        return irc.Response('Invalid amount of parameters (expected 3, received {}) check !owners help'.format(args), pm_user=True)

    command = message.words[1].lower()
    if command not in ['add', 'remove']:
        return irc.Response('Invalid command given ({}) check !owners help'.format(command), pm_user=True)

    owner = message.words[2]
    if command == 'add':
        list_of_owners.append(owner)
    elif command == 'remove':
        if owner not in list_of_owners:
            return irc.Response('Owner "{}" not found (note this is case sensitive)'.format(owner), pm_user=True)
        list_of_owners.remove(owner)

    conf['owners'] = list_of_owners
    update_config(conf)
    return irc.Response('Successfully updated', pm_user=True)


def streams(message):
    result = []
    pastebin = "http://pastebin.com/raw.php?i=x5qCS5Gz"
    data = urllib.urlopen(pastebin)
    reader = csv.reader(data)
    round_filter = None
    if len(message.words) > 1:
        round_filter = message.words[1]
    for row in reader:
        if round_filter != None and row[0] != round_filter:
            continue
        result.append('{a[0]:<10} {a[1]:<10} {a[2]:<10}'.format(a=row))

    return irc.Response('\n'.join(result))

def seed(message):
    if message.nick not in conf.get('owners', []):
        return irc.Response('You are not authorised to use this command', pm_user=True)

    p = conf.get('tps', None)
    if p == None or not os.path.exists(p):
        return irc.Response('No TPS database has been found. Sorry.', pm_user=True)

    api_key =conf.get('challonge', None)
    if api_key == None:
        return irc.Response('No Challonge API key has been set in config', pm_user=True)

    db = {}
    with codecs.open(p, 'r', 'utf-8') as f:
        db = json.load(f)

    m = re.match(r'(?:https?\:\/\/)?(?:(?P<subdomain>\w*)\.)?challonge\.com\/(?P<url>\w*)', message.words[1])
    url = m.group('url')
    if m.group('subdomain'):
        url = '{}-{}'.format(m.group('subdomain'), m.group('url'))


    params = {
        'api_key': api_key
    }
    participants = requests.get('https://api.challonge.com/v1/tournaments/{}/participants.json'.format(url), params=params)
    if participants.status_code != 200:
        return irc.Response('Unable to access challonge API [error: {}]'.format(participants.text), pm_user=True)
    pjson = participants.json()

    # get a mapping of (challonge_username, participant_id, tps)
    User = namedtuple('User', ['name', 'id', 'tps'])
    users = []
    for obj in pjson:
        if obj.get('checked_in', True):
            participant = obj['participant']
            name = participant["challonge_username"]
            pid = participant["id"]
            tps = db.get(name, 1000)
            users.append(User(name=name, id=pid, tps=tps))

    # sort the users by their TPS score
    users.sort(key=lambda x: x.tps, reverse=True)

    # update the seed based on position on the list
    for seed, user in enumerate(users):
        params = {
            'api_key': api_key,
            'participant[seed]': seed + 1
        }
        r = requests.put('https://api.challonge.com/v1/tournaments/{}/participants/{}.json'.format(url, user.id), params=params)
        if r.status_code != 200:
            return irc.Response('Unable to access challonge API [error: {}]'.format(r.text), pm_user=True)

    return irc.Response('Tournament has successfully been seeded.', pm_user=True)


def form(message):
    return irc.Response("http://goo.gl/CfFKeO")

def faq(message):
    return irc.Response("http://goo.gl/EUbs9X")

def conduct(message):
    return irc.Response("http://goo.gl/FvbxHm")

def tutorial(message):
    return irc.Response("http://goo.gl/wRFPoU")

def ranking(message):
    return irc.Response("http://www.reddit.com/r/smashbros/wiki/rankings")

def calendar(message):
    return irc.Response("http://www.reddit.com/r/smashbros/wiki/eventcalendar")

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def update_config(conf):
    with open('config.json', 'wb') as out:
        json.dump(conf, out, sort_keys=True, indent=4, separators=(',', ': '))

if __name__ == '__main__':
    conf = load_config()
    bot = irc.Bot(owners=conf.get('owners', []), server=conf['server'], channels=conf['channels'],
                  nickname=conf['nickname'], password=conf['password'])
    bot.add_command('bracket', bracket)
    bot.add_command('rules', rules)
    bot.add_command('phonebook', phonebook)
    bot.add_command('tps', tps)
    bot.add_command('change', change)
    bot.add_command('owners', owners)
    bot.add_command('streams', streams)
    bot.add_command('seed', seed)
    bot.add_command('form', form)
    bot.add_command('faq', faq)
    bot.add_command('conduct', conduct)
    bot.add_command('tutorial', tutorial)
    bot.add_command('ranking', ranking)
    bot.add_command('calendar', calendar)
    bot.run()
