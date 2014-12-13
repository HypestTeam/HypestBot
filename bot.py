#!/usr/bin/env python

import irc
import json
import urllib
import csv

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

def toc(message):
    if message.user in conf['owners']:
        return irc.Response('https://docs.google.com/spreadsheets/d/1uYu-dk8-HjQt98fEoJ5G2VndUF-AqKW5bEHtAo7oKeM/', pm_user=True)
    return None

def change(message):
    # allows 'owners' to modify the database
    # if you're not an owner, so just ignore the message
    if message.user not in conf['owners']:
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
    if message.user not in list_of_owners:
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
    bot.add_command('toc', toc)
    bot.add_command('rules', rules)
    bot.add_command('phonebook', phonebook)
    bot.add_command('change', change)
    bot.add_command('owners', owners)
    bot.add_command('streams', streams)
    bot.run()
