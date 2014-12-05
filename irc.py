import socket, time
import re, string

"""
Represents an IRC message
"""
class Message(object):
    def __init__(self, msg):
        # :rapptz!rapptz@user/rapptz/x-00071589 PRIVMSG #SmashBrosTourney :okay sign in seems to be working
        regex = r'\:(?P<source>(?P<nick>[^!]+)![~]{0,1}(?P<user>[^@]+)@)?(?P<host>[^\s]+)\s(?P<command>[^\s]+)\s?(?P<parameters>[^:]+){0,1}\:?(?P<text>[^\r^\n]+)?'
        match = re.match(regex, msg)
        self.valid_command = False
        if match:
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
        self.channel = kwargs['channel']
        self.nickname = kwargs['nickname']
        self.password = kwargs['password']
        self.owners = kwargs.get('owners', [])
        self.port = kwargs.get('port', 6667)
        self.response = ''
        self.commands = {}
        self.running = True

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

    def join(self, channel):
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
        self._send('PRIVMSG NickServ :identify {}\r\n'.format(self.password))
        print(self.response)

    def run(self):
        server_match = re.search(r'\:Your host is (.*),', self.response)
        self.chat_server = server_match.group(1) if server_match else self.server
        print('The chat server found is ' + self.chat_server)
        self.join(self.channel)
        while self.running:
            self.response = self.irc.recv(2048).strip()
            self.pong()

            # we're being bugged to log on so go ahead and do so >_>
            if ':You have 30 seconds to identify to your nickname' in self.response:
                self.sign_in()

            if self.chat_server in self.response:
                continue

            self.message = Message(self.response)

            if self.message.valid_command:
                print(self.response)
                if self.message.text.startswith('!commands'):
                    self.send_message(self.message.user, 'available commands:')
                    if len(self.commands) == 0:
                        self.send_message(self.message.user, 'none found!')
                    else:
                        for k, _ in self.commands.items():
                            self.send_message(self.message.user, k)
                elif self.message.text.startswith('!quit') and self.message.user in self.owners:
                    self.disconnect(self.channel, 'pew pew pew')
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
                                self.send_message(self.channel if not result.pm_user else self.message.user, item)
                    except Exception as e:
                        print('error found: ' + str(e))
