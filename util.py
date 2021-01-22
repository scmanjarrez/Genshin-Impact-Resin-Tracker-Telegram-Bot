from telegram.error import Unauthorized
from threading import Thread
from paimon import bot_blocked, notify_promo_codes
from bs4 import BeautifulSoup
import sqlite3
import requests


MAX_RESIN = 160
RESIN_REGEN_MIN = 8
BAN_STRIKE = 100
WARN_STRIKE = 75
CODE_CHECK_HOUR = 6


def set_up_db():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            resin INTEGER DEFAULT 0,
            warn INTEGER DEFAULT 110,
            custom_timezone INTEGER DEFAULT 0,
            timezone INTEGER DEFAULT 0,
            warn_strikes INTEGER,
            notify_codes INTEGER DEFAULT 0
        )''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY
        )''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            eu_code TEXT PRIMARY KEY,
            na_code TEXT,
            sea_code TEXT,
            expired INTEGER DEFAULT 0,
            rewards TEXT,
            notified INTEGER DEFAULT 0
        )''')

    db.close()


def is_user_banned(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT EXISTS('
         'SELECT 1 '
         'FROM banned_users '
         'WHERE user_id = ?)'),
        [user_id]
    )
    try:
        exist = cur.fetchone()[0]  # (1,) if exists, (0,) otherwise
    except TypeError:
        print(f"Error: is_user_banned({user_id})")
        exist = -1
    db.close()
    return exist


def ban_user(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('INSERT INTO banned_users '
         'VALUES (?)'),
        [user_id]
    )
    db.commit()
    db.close()
    bot_blocked(user_id)


def get_strikes(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT warn_strikes '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    try:
        strikes = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: get_strikes({user_id})")
        strikes = -1
    db.close()
    return strikes


def inc_strike(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET warn_strikes = warn_strikes + 1 '
         'WHERE user_id = ?'),
        [user_id]
    )
    db.commit()
    db.close()


def dec_strike(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur_strikes = get_strikes(user_id)
    if cur_strikes > 0:
        cur.execute(
            ('UPDATE users '
             'SET warn_strikes = warn_strikes - 1 '
             'WHERE user_id = ?'),
            [user_id]
        )
    db.commit()
    db.close()


def is_user_in_db(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT EXISTS('
         'SELECT 1 '
         'FROM users '
         'WHERE user_id = ?)'),
        [user_id]
    )
    try:
        exist = cur.fetchone()[0]  # (1,) if exists, (0,) otherwise
    except TypeError:
        print(f"Error: is_user_in_db({user_id})")
        exist = -1
    db.close()
    return exist


def delete_user_from_db(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('DELETE '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    db.commit()
    db.close()


def get_users():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT user_id '
         'FROM users')
    )
    user_list = cur.fetchall()
    db.close()
    return user_list


def get_resin(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT resin '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    try:
        resin = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: get_resin({user_id})")
        resin = -1
    db.close()
    return resin


def set_resin(user_id, resin):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    if is_user_in_db(user_id):
        cur.execute(
            ('UPDATE users '
             'SET resin = ? '
             'WHERE user_id = ?'),
            [resin, user_id]
        )
    else:
        cur.execute(
            ('INSERT INTO users (user_id, resin) '
             'VALUES (?, ?)'),
            [user_id, resin]
        )

    db.commit()
    db.close()


def inc_resin(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET resin = resin + 1 '
         'WHERE user_id = ?'),
        [user_id]
    )
    db.commit()
    db.close()


def dec_resin(user_id, resin):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET resin = resin - ? '
         'WHERE user_id = ?'),
        [resin, user_id]
    )
    db.commit()
    db.close()


def max_resin(user_id):
    cur_resin = get_resin(user_id)
    captime = (MAX_RESIN - cur_resin) * RESIN_REGEN_MIN
    return captime // 60, captime % 60


def get_warn(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT warn '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    try:
        warn = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: get_warn({user_id})")
        warn = -1
    db.close()
    return warn


def set_warn(user_id, warn):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    if is_user_in_db(user_id):
        cur.execute(
            ('UPDATE users '
             'SET warn = ? '
             'WHERE user_id = ?'),
            [warn, user_id]
        )
    else:
        cur.execute(
            ('INSERT INTO users (user_id, warn) '
             'VALUES (?, ?)'),
            [user_id, warn]
        )

    db.commit()
    db.close()


def custom_timezone(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT custom_timezone '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    try:
        custom_timezone = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: custom_timezone({user_id})")
        custom_timezone = -1
    db.close()
    return custom_timezone


def get_timezone(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT timezone '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    try:
        timezone = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: get_timezone({user_id})")
        timezone = -1
    db.close()
    return timezone


def set_timezone(user_id, timezone):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    if is_user_in_db(user_id):
        cur.execute(
            ('UPDATE users '
             'SET custom_timezone = 1, timezone = ? '
             'WHERE user_id = ?'),
            [timezone, user_id]
        )
    else:
        cur.execute(
            ('INSERT INTO users (user_id, custom_timezone, timezone) '
             'VALUES (?, 1, ?)'),
            [user_id, timezone]
        )

    db.commit()
    db.close()


def is_code_in_db(code):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT EXISTS('
         'SELECT 1 '
         'FROM promo_codes '
         'WHERE eu_code = ?)'),
        [code]
    )
    try:
        exist = cur.fetchone()[0]  # (1,) if exists, (0,) otherwise
    except TypeError:
        print(f"Error: code_in_db({code})")
        exist = -1
    db.close()
    return exist


def _is_expired(expired):
    return int(expired.lower() == 'yes')


def add_code(rewards, expired, eu_code, na_code, sea_code):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    if is_code_in_db(eu_code):
        cur.execute(
            ('UPDATE promo_codes '
             'SET expired = ? '
             'WHERE eu_code = ?'),
            [_is_expired(expired), eu_code]
        )
    else:
        cur.execute(
            ('INSERT INTO promo_codes (rewards, expired, '
             'eu_code, na_code, sea_code, notified)'
             'VALUES (?, ?, ?, ?, ?, ?)'),
            [rewards, _is_expired(expired),
             eu_code, na_code, sea_code,
             _is_expired(expired)]
        )

    db.commit()
    db.close()


def code_notified(code):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE promo_codes '
         'SET notified = 1 '
         'WHERE eu_code = ?'),
        [code]
    )
    db.commit()
    db.close()


def is_code_unnotified():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT EXISTS('
         'SELECT 1 '
         'FROM promo_codes '
         'WHERE notified = 0 AND expired = 0)')
    )
    try:
        exist = cur.fetchone()[0]  # (1,) if exists, (0,) otherwise
    except TypeError:
        print("Error: is_code_unnotified()")
        exist = -1
    db.close()
    return exist


def get_unnotified_codes():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT eu_code, na_code, sea_code, rewards '
         'FROM promo_codes '
         'WHERE notified = 0')
    )
    try:
        exist = cur.fetchall()
    except TypeError:
        print("Error: get_unnotified_codes()")
        exist = -1
    db.close()
    return exist


def get_unexpired_codes():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT eu_code, na_code, sea_code, rewards '
         'FROM promo_codes '
         'WHERE expired = 0')
    )
    try:
        exist = cur.fetchall()
    except TypeError:
        print("Error: get_unexpired_codes()")
        exist = -1
    db.close()
    return exist


def notify_codes_allowed(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT notify_codes '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    try:
        allowed = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: notify_codes_allowed({user_id})")
        allowed = -1
    db.close()
    return allowed


def notify_codes_allow(user_id, allow):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET notify_codes = ? '
         'WHERE user_id = ?'),
        [allow, user_id]
    )
    db.commit()
    db.close()


class ResinThread(Thread):
    def __init__(self, event, user_id, current_timer, context):
        Thread.__init__(self)
        self.stopped = event
        self.user_id = user_id
        self.current_timer = current_timer
        self.notified = False
        self.maxreached = False
        self.context = context
        self.daemon = True

    def notify(self, msg, cap=False):
        try:
            self.context.bot.send_message(
                chat_id=self.user_id, text=msg)
        except Unauthorized:
            bot_blocked(self.user_id)
            self.stopped.set()
        finally:
            if cap:
                self.maxreached = True
            else:
                self.notified = True

    def run(self):
        while not self.stopped.wait(self.current_timer):
            resin = get_resin(self.user_id)

            if resin >= MAX_RESIN:
                self.stopped.set()
            else:
                self.current_timer = RESIN_REGEN_MIN * 60
                # debug
                # self.current_timer = 5

                inc_resin(self.user_id)

                resin = get_resin(self.user_id)
                warn = get_warn(self.user_id)

                if warn <= resin < MAX_RESIN and not self.notified:
                    self.notify(
                        (f"‼ Hey! You have {resin} resin waiting!\n"
                         f"Don't let it lose ‼"))
                elif resin >= MAX_RESIN and not self.maxreached:
                    self.notify(
                        (f"‼ Hey! You have {resin} resin waiting!\n"
                         "You won't earn more resin! ‼"),
                        cap=True)
                    self.stopped.set()
                elif resin < warn:
                    self.notified = False
                    self.maxreached = False


class PromoCodeThread(Thread):
    def __init__(self, event, updater):
        Thread.__init__(self)
        self.stopped = event
        self.url = "https://www.gensh.in/events/promotion-codes"
        self.row_elem = 6
        self.updater = updater
        self.daemon = True
        self.next_scrap = 5

    def run(self):
        while not self.stopped.wait(self.next_scrap):
            self.next_scrap = CODE_CHECK_HOUR * 60 * 60
            try:
                req = requests.get(self.url)
            except requests.exceptions.ConnectionError:
                print("Error: Couldn't connect to gensh.in")
            else:
                soup = BeautifulSoup(req.text, features='html.parser')
                codes_table = soup.find('table',
                                        attrs={
                                            'class': 'ce-table-bordered'
                                        }).find('tbody').find_all('td')

                stripped_codes = [c.text.strip() for c in codes_table]
                codes = [stripped_codes[i:i+self.row_elem]
                         for i in range(0, len(stripped_codes), self.row_elem)]
                for c in codes:
                    _, reward, expired, eu_code, na_code, sea_code = c
                    add_code(reward, expired, eu_code, na_code, sea_code)

                notify_promo_codes(self.updater)
