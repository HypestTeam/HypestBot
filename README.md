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
    "ranking_directory": "directory with the corresponding Hypest Database files"
}

```

Make sure to fill it in with the configuration values you want.

### Current Commands

The bot knows two kinds of commands. Ones applicable to owners (see above) and everyone. If
someone who isn't an owner uses an owner only command then the user is PM'd an error message.

#### Owner Only Commands

- `!change`: Changes the output from `!bracket` and `!rules`. Type `!change help` for more info.
- `!owners`: Manages the owners of the bot. Type `!owners help` for more info.
- `!leave`: Leaves the current channel.
- `!exit`: Quits the bot.
- `!seed`: Seeds the challonge bracket provided with the TPS score.

#### General Commands

- `!bracket`: Posts a URL to the brackets.
- `!phonebook`: Posts a URL to the Hypest Phonebook.
- `!rules`: Posts a URL to the current ruleset.
- `!streams`: Posts the current streams as managed by the pastebin provided by BestTeaMaker. This will be made more generalised soon.
- `!rank`: Posts a player's rankings and stats for a specific game.
- `!form`: Posts a URL to the sign-up form.
- `!faq`: Posts a URL to the FAQ.
- `!conduct`: Posts a URL to the Code of Conduct.
- `!tutorial`: Posts a URL to the tutorials provided.
- `!ranking`: Posts a URL to the /r/smashbros ranking.
- `!calendar`: Posts a URL to the /r/smashbros Event Calendar.


### Custom Commands

Coming soon.

### License

MIT License.
