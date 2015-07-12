import commands
import irc
import sys

@commands.owners_only
@commands.help_text('Reloads the bot\'s internal functions and config file')
def refresh(bot):
    reload(commands)
    reload(irc)
    commands.conf = commands.load_config()
    commands.register(bot)
    return irc.Response('Bot successfully refreshed internal functions', pm_user=True)

if __name__ == '__main__':
    commands.conf = commands.load_config()
    reload(sys)
    sys.setdefaultencoding('utf-8')
    bot = irc.Bot(**commands.conf)
    bot.add_command(refresh)
    commands.register(bot)
    bot.run()
