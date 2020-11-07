from telegram.error import Unauthorized
from threading import Thread
from paimon import bot_blocked
import sqlite3


MAX_RESIN = 120
RESIN_REGEN_MIN = 8
BAN_STRIKE = 100
WARN_STRIKE = 75


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
            warn_strikes INTEGER
        )''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY
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

                inc_resin(self.user_id)

                resin = get_resin(self.user_id)
                warn = get_warn(self.user_id)

                if warn <= resin < MAX_RESIN and not self.notified:
                    self.notify(
                        (f"Hey! You have {resin} resin waiting! "
                         f"Don't let it lose."))
                elif resin >= MAX_RESIN and not self.maxreached:
                    self.notify(
                        (f"Hey! You have {resin} resin waiting! "
                         "You won't earn more resin!"),
                        cap=True)
                    self.stopped.set()
                elif resin < warn:
                    self.notified = False
                    self.maxreached = False
