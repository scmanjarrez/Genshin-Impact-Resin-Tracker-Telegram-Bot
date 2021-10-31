# Description
Telegram bot to track your resin using python timers. A new version using
unofficial API is in development [Genshin-Impact-Stats-Telegram-Bot](https://github.com/scmanjarrez/Genshin-Impact-Stats-Telegram-Bot).

# Requirements
- python

# BotFather set up
Create a bot with [@BotFather](https://t.me/BotFather) and set the following commands:
```
start - Setup user data. Mandatory.
help - List of commands.
menu - Interact with me using UI. [beta]
resin - Resin status.
set - Set resin value.
spend - Spend resin.
refill - Increase resin.
track - Synchronize bot timer.
warnings - Set resin warning threshold.
timezone - Set your timezone.
cancel - Cancel current action.
stop - Remove your information from bot.
```

# Run
- Install python dependencies.

    `pip install -r requirements.txt`

- Create a self-signed certificate in order to communicate with telegram server
  using SSL.

    `openssl req -newkey rsa:2048 -sha256 -nodes -keyout paimon.key
    -x509 -days 3650 -out paimon.pem`

- Modify **config.template** placeholders. Port must be **80**, **88**,
  **443** or **8443**.

- Change config.template name.

    `mv config.template .config`

- Execute the bot.

    `./paimon.py`
    > **Note:** If you run the bot in port 80, it may be needed to run the bot as
    > superuser (**sudo**).

# License
    Copyright (c) 2021 scmanjarrez. All rights reserved.
    This work is licensed under the terms of the MIT license.

For a copy, see
[LICENSE](https://github.com/scmanjarrez/ordonnanz/blob/master/LICENSE).
