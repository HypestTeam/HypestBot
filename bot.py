#!/usr/bin/env python

import irc
import json
import urllib
import csv
import re, os
import codecs

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

    username = words[1]
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
        except Exception, e:
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

def score(message):
    # !score <me>: <score> <you>: <score>
    fmt = re.compile(r'!score\s*(?P<you>[a-zA-Z_\-\[\]\\^{}|`][\w\-\[\]\\^{}|`]*)\s*\:\s*(?P<score>\d+)\s*'\
                     r'(?P<opponent>[a-zA-Z_\-\[\]\\^{}|`][\w\-\[\]\\^{}|`]*)\s*\:\s*(?P<opscore>\d+)', re.UNICODE)
    result = fmt.match(message.text)
    if not result:
        return irc.Response('Incorrect format given.\n'\
                            'Must be !score <your name>: <your score> <opponent name>: <opponent score>', pm_user=True)

    score = int(result.group('score'))
    opscore = int(result.group('opscore'))
    if (score, opscore) not in [(2, 1), (1, 2), (2, 0), (0, 2)]:
        return irc.Response('Incorrect score total. Possible variations are 2-1, 1-2, 2-0, or 0-2', pm_user=True)

    with open('round.txt', 'a') as f:
        f.write('{0}:{1} {2}:{3} was reported by {4}\n'.format(result.group('you'), score,
                                                               result.group('opponent'), opscore, message.nick))

    return irc.Response('Score successfully recorded! Make sure to wait until next round.\n', pm_user=True)


def endround(message):
    if message.nick not in conf.get('owners', []):
        return irc.Response('You are not authorised to use this command', pm_user=True)

    data = None
    with open('round.txt') as f:
        data = f.read()

    api_key = conf.get('pastebin', None)
    if api_key == None:
        return irc.Response('Unfortunately something broke. Please tell rapptz that there is\
                             a missing or invalid pastebin API key.', pm_user=True)

    link = r"http://pastebin.com/api/api_post.php"
    params_dict = {
        'api_dev_key': api_key,
        'api_option': 'paste',
        'api_paste_code': data,
        'api_paste_name': 'End of Round Results',
        'api_paste_expire_date': '1H'
    }
    params = urllib.urlencode(params_dict)
    resp = urllib.urlopen(link, params)
    contents = resp.read()
    if 'Bad API' in contents:
        return irc.Response('Unfortunately something broke. Paste could not be posted. Contact rapptz', pm_user=True)

    os.remove('round.txt')
    return irc.Response(contents)

def viewround(message):
    if message.nick not in conf.get('owners', []):
        return irc.Response('You are not authorised to use this command', pm_user=True)

    data = None
    with open('round.txt') as f:
        data = f.read()

    api_key = conf.get('pastebin', None)
    if api_key == None:
        return irc.Response('Unfortunately something broke. Please tell rapptz that there is\
                             a missing or invalid pastebin API key.', pm_user=True)

    link = r"http://pastebin.com/api/api_post.php"
    params_dict = {
        'api_dev_key': api_key,
        'api_option': 'paste',
        'api_paste_code': data,
        'api_paste_name': 'A View of Round Results',
        'api_paste_expire_date': '10M'
    }
    params = urllib.urlencode(params_dict)
    resp = urllib.urlopen(link, params)
    contents = resp.read()
    if 'Bad API' in contents:
        return irc.Response('Unfortunately something broke. Paste could not be posted. Contact rapptz', pm_user=True)

    return irc.Response(contents)

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def update_config(conf):
    with open('config.json', 'wb') as out:
        json.dump(conf, out, sort_keys=True, indent=4, separators=(',', ': '))

if __name__ == '__main__':
    conf = load_config()
    bot = irc.Bot(owners=conf.get('owners', []), server=conf['server'], channel=conf['channel'],
                  nickname=conf['nickname'], password=conf['password'])
    bot.add_command('bracket', bracket)
    bot.add_command('rules', rules)
    bot.add_command('phonebook', phonebook)
    bot.add_command('tps', tps)
    bot.add_command('change', change)
    bot.add_command('owners', owners)
    bot.add_command('streams', streams)
    bot.add_command('endround', endround)
    bot.add_command('viewround', viewround)
    bot.add_command('score', score)
    bot.run()
