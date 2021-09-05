# Description
Source code of Telegram bot @ehe_te_nandayo_bot

# Requirements
- python

# Run
- Install python dependencies.

    `pip install -r requirements.txt`

- Create a self-signed certificate in order to communicate with telegram server using SSL.

    `openssl req -newkey rsa:2048 -sha256 -nodes -keyout paimon.key -x509 -days 3650 -out paimon.pem`

- Modify **config.template** placeholders. Port must be **80**, **88**, **443** or **8443**.

- Change config.template name.

    `mv config.template .config`

- Execute the bot.

    `./paimon.py`
