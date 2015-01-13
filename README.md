### IRC Bot

This is the IRC bot for Hypest's IRC chat. It has a couple commands
that are useful.

### Bot Configuration

To run an instance of HypestBot a file called `config.json` is used. All there is to it
is to create a file called `config.json` where the `bot.py` file is located and it has
the following contents:

```js
{
    "bracket": "url where bracket is located",
    "channels": [ "#TheIRCCHannel" ],
    "nickname": "TheBotName",
    "owners": [
        "a list of nicknames who own the bot"
    ],
    "password": "the bot password for NickServ",
    "rules": "url where the rules are located",
    "server": "the server the bot should go to (e.g. irc.snoonet.org)",
    "tps": "TPS database file location (must be .json)"
}

```

Make sure to fill it in with the configuration values you want.

### Current Commands

The bot knows two kinds of commands. Ones applicable to owners (see above) and everyone. If
someone who isn't an owner uses an owner only command then the user is PM'd an error message.

#### Owner Only Commands

1. `!change`: Changes the output from `!bracket` and `!rules`. Type `!change help` for more info.
2. `!owners`: Manages the owners of the bot. Type `!owners help` for more info.
3. `!leave`: Leaves the current channel.
4. `!exit`: Quits the bot.
5. `!seed`: Seeds the challonge bracket provided with the TPS score.

#### General Commands

1. `!bracket`: Posts a URL to the brackets.
2. `!phonebook`: Posts a URL to the Hypest Phonebook.
3. `!rules`: Posts a URL to the current ruleset.
4. `!streams`: Posts the current streams as managed by the pastebin provided by BestTeaMaker. This will be made more generalised soon.
5. `!tps`: Displays the user's Tournament Participation Score.


### Custom Commands

Coming soon.

### License

MIT License.
