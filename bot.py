import commands
import irc
import sys

@commands.owners_only
@commands.help_text('Reloads the bot\'s internal functions and config file')
def refresh(bot):
    reload(commands)
    reload(irc)
    commands.conf = commands.load_config()
    return irc.Response('Bot successfully refreshed internal functions', pm_user=True)

if __name__ == '__main__':
    commands.conf = commands.load_config()
    reload(sys)
    sys.setdefaultencoding('utf-8')
    bot = irc.Bot(**commands.conf)
    bot.add_command(commands.botcommands)
    bot.add_command(commands.quit)
    bot.add_command(commands.leave)
    bot.add_command(commands.bracket)
    bot.add_command(commands.rules)
    bot.add_command(commands.phonebook)
    bot.add_command(commands.change)
    bot.add_command(commands.owners)
    bot.add_command(commands.streams)
    bot.add_command(commands.rank)
    bot.add_command(commands.prepare)
    bot.add_command(commands.delta)
    bot.add_command(commands.form)
    bot.add_command(commands.banish)
    bot.add_command(commands.unbanish)
    bot.add_command(commands.faq)
    bot.add_command(commands.conduct)
    bot.add_command(commands.tutorial)
    bot.add_command(commands.ranking)
    bot.add_command(commands.calendar)
    bot.add_command(commands.debug)
    bot.add_command(commands.season)
    bot.add_command(refresh)
    bot.run()
