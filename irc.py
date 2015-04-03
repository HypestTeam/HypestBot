import socket, time
import re, string
import traceback

"""
Represents an IRC message
"""
class Message(object):
    def __init__(self, msg):
        # :rapptz!rapptz@user/rapptz/x-00071589 PRIVMSG #SmashBrosTourney :okay sign in seems to be working
        regex = r':(?P<source>(?P<nick>[^!]+)!~?(?P<user>[^@]+)@)?(?P<host>[^\s]+)\s(?P<command>[^\s]+)\s?(?P<parameters>[^:]+)?:?(?P<text>[^\r^\n]+)?'
        match = re.match(regex, msg)
        self.valid_command = False
        self.is_message = False
        if match:
            self.is_message = True
            self.raw_message = match.group(0)
            self.source = match.group('source')
            self.nick = match.group('nick')
            self.user = match.group('user')
            self.host = match.group('host')
            self.command = match.group('command')
            self.parameters = match.group('parameters')
            self.text = match.group('text')
            self.valid_command = self.text != None and self.text[0] == '!'
            self.words = [word.rstrip(string.punctuation) for word in self.text.split()] if self.text != None else []

    def __len__(self):
        if self.is_message:
            return len(self.text)
        else:
            return 0

    def channel_used(self):
        if self.is_message and self.command == 'PRIVMSG':
            return self.parameters.strip()
        else:
            return ''

"""
Represents a response from a command function
"""
class Response(object):
    def __init__(self, msg, pm_user=False):
        self.message = msg
        self.pm_user = pm_user

class Bot(object):
    def __init__(self, **kwargs):
        self.server = kwargs['server']
        self.channels = kwargs['channels']
        self.nickname = kwargs['nickname']
        self.password = kwargs['password']
        self.owners = kwargs.get('owners', [])
        self.port = kwargs.get('port', 6667)
        self.login_command = kwargs.get('login', None)
        self.response = ''
        self.commands = {}
        self.running = True
        self.current_channel = ''

        if self.login_command and not self.login_command.endswith('\r\n'):
            self.login_command = self.login_command + '\r\n'

        # actually connect
        self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc.connect((self.server, self.port))
        print('Setting User...')
        self._send('USER {0} {0} {0} :{0}\r\n'.format(self.nickname))
        print('Setting Nick...')
        self._send('NICK {}\r\n'.format(self.nickname))

        # this sleeping is required so we don't get some asynchronous sending
        time.sleep(1)
        self.sign_in()
        time.sleep(1)

    def _send(self, message):
        self.irc.send(message)
        self.response = self.irc.recv(2048).strip()
        self.pong()

    def pong(self):
        result = re.search(r'PING :(.*)', self.response)
        if result:
            self.irc.send('PONG :{}\r\n'.format(result.group(1)))

    def send_message(self, channel, message):
        self.irc.send('PRIVMSG {} :{}\r\n'.format(channel, message))

    def disconnect(self, channel, message):
        self.irc.send('PART {} :{}\r\n'.format(channel, message))
        if channel in self.channels:
            self.channels.remove(channel)

        if len(self.channels) == 0:
            self.running = False

    def join(self):
        for channel in self.channels:
            print('joining ' + channel)
            self.irc.send('JOIN {}\r\n'.format(channel))

    def add_owner(self, owner):
        self.owners.append(owner)

    # a command is basically a python function associated with a command string.
    # the command string will then be prepended with ! and when the user executes
    # !command in IRC, then the function will be executed with an irc.Message object
    # as its parameter.
    # The function is expected to return either a string or None. None denotes that no
    # message will be sent to the IRC server, while a string will be sent. The string is
    # split at '\n' to denote multiple messages to send, use this to your advantage if
    # needed.
    def add_command(self, command, function):
        self.commands['!' + command.lower()] = function

    def sign_in(self):
        print('signing in...')
        if self.login_command:
            self._send(self.login_command.format(pw=self.password, user=self.nickname))
        else:
            self._send('PRIVMSG NickServ :identify {}\r\n'.format(self.password))
        print(self.response)

    def run(self):
        server_match = re.search(r'\:Your host is (.*),', self.response)
        self.chat_server = server_match.group(1) if server_match else self.server
        print('The chat server found is ' + self.chat_server)
        self.join()
        while self.running:
            self.response = self.irc.recv(2048).strip()
            self.pong()

            # force sign-in, again >_>
            if '{} is a registered nick'.format(self.nickname) in self.response:
                self.sign_in()
                self.join()

            if self.chat_server in self.response:
                continue

            self.message = Message(self.response)
            self.current_channel = self.message.channel_used()

            if self.message.valid_command:
                print(self.response)
                if self.message.text.startswith('!botcommands'):
                    self.send_message(self.message.nick, 'available commands:')
                    if len(self.commands) == 0:
                        self.send_message(self.message.nick, 'none found!')
                    else:
                        self.send_message(self.message.nick, ', '.join(self.commands.keys()))
                elif self.message.text.startswith('!leave') and self.message.nick in self.owners:
                    self.disconnect(self.current_channel, 'pew pew pew')
                elif self.message.text.startswith('!quit') and self.message.nick in self.owners:
                    for channel in self.channels:
                        self.disconnect(channel, 'quitting bot')
                    self.running = False
                else:
                    function = self.commands.get(self.message.words[0].lower(), None)
                    if function == None:
                        print('unknown command found : ' + self.message.text)
                    try:
                        result = function(self.message)
                        if result:
                            messages = result.message.split('\n')
                            for item in messages:
                                self.send_message(self.current_channel if not result.pm_user else self.message.nick, item)
                    except Exception as e:
                        print('error found:')
                        print(traceback.format_exc())
