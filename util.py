from telegram.error import Unauthorized
from threading import Thread
from paimon import bot_blocked, notify_promo_codes
from bs4 import BeautifulSoup
import sqlite3
import requests

RESIN_MAX = 160
RESIN_REGEN_MIN = 8
TRACK_MAX = (7, 5, 9)
WARN_MAX = (1, 5, 9)
STRIKE_BAN = 50
STRIKE_WARN = 25
CODE_CHECK_HOUR = 6


def set_up_db():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY,
            resin INTEGER DEFAULT 0,
            warn INTEGER DEFAULT 1,
            warn_threshold INTEGER DEFAULT 150,
            codes_notify INTEGER DEFAULT 0,
            timezone INTEGER DEFAULT 0,
            timezone_local INTEGER DEFAULT 0,
            strikes INTEGER DEFAULT 0
        )''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            uid INTEGER PRIMARY KEY
        )''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            rewards TEXT,
            expired INTEGER DEFAULT 0,
            eu_code TEXT PRIMARY KEY,
            na_code TEXT,
            sea_code TEXT,
            notified INTEGER DEFAULT 0
        )''')


def strikes(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT strikes '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    try:
        cstrikes = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: strikes({uid})")
        cstrikes = -1
    return cstrikes


def strikes_inc(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET strikes = strikes + 1 '
         'WHERE uid = ?'),
        [uid]
    )
    db.commit()


def strikes_dec(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET strikes = strikes - 1 '
         'WHERE strikes > 0'
         'AND uid = ?'),
        [uid]
    )
    db.commit()


def user_ban(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('INSERT INTO banned_users '
         'VALUES (?)'),
        [uid]
    )
    db.commit()
    bot_blocked(uid)


def user_banned(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT EXISTS ('
         'SELECT 1 '
         'FROM banned_users '
         'WHERE uid = ?)'),
        [uid]
    )
    try:
        banned = cur.fetchone()[0]  # (1,) if exists, (0,) otherwise
    except TypeError:
        print(f"Error: user_banned({uid})")
        banned = -1
    return banned


def user_exists(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT EXISTS ('
         'SELECT 1 '
         'FROM users '
         'WHERE uid = ?)'),
        [uid]
    )
    try:
        exist = cur.fetchone()[0]  # (1,) if exists, (0,) otherwise
    except TypeError:
        print(f"Error: user_exists({uid})")
        exist = -1
    return exist


def user_add(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('INSERT INTO users (uid) '
         'VALUES (?)'),
        [uid]
    )
    db.commit()


def user_remove(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('DELETE '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    db.commit()


def users():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT uid '
         'FROM users')
    )
    user_list = cur.fetchall()
    return user_list


def resin(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT resin '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    try:
        cresin = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: get_resin({uid})")
        cresin = -1
    return cresin


def resin_set(uid, sresin):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET resin = ? '
         'WHERE uid = ?'),
        [sresin, uid]
    )
    db.commit()


def resin_inc(uid, iresin):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET resin = resin + ? '
         'WHERE uid = ?'),
        [iresin, uid]
    )
    db.commit()


def resin_dec(uid, dresin):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET resin = resin - ? '
         'WHERE uid = ?'),
        [dresin, uid]
    )
    db.commit()


def resin_max(uid):
    cresin = resin(uid)
    cwarn = warn_threshold(uid)
    hcap = (RESIN_MAX - cresin) * RESIN_REGEN_MIN
    scap = (cwarn - cresin) * RESIN_REGEN_MIN
    scap = 0 if scap < 0 else scap
    return (hcap // 60, hcap % 60), (scap // 60, scap % 60)


def warn_allowed(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT warn '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    try:
        allowed = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: warn_allowed({uid})")
        allowed = -1
    return allowed


def warn_toggle(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET warn = NOT warn '
         'WHERE uid = ?'),
        [uid]
    )
    db.commit()


def warn_threshold(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT warn_threshold '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    try:
        cthreshold = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: warn({uid})")
        cthreshold = -1
    return cthreshold


def warn_threshold_set(uid, th):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET warn_threshold = ? '
         'WHERE uid = ?'),
        [th, uid]
    )
    db.commit()


def timezone(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT timezone '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    try:
        ctimezone = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: timezone({uid})")
        ctimezone = -1
    return ctimezone


def timezone_toggle(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET timezone = NOT timezone '
         'WHERE uid = ?'),
        [uid]
    )
    db.commit()


def timezone_local(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT timezone_local '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    try:
        tz = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: timezone_local({uid})")
        tz = -1
    return tz


def timezone_local_set(uid, tz):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE timezone_local '
         'SET timezone_local = ? '
         'WHERE uid = ?'),
        [tz, uid]
    )
    db.commit()


def code_exists(code):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT EXISTS ('
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
    return exist


def _is_expired(expired):
    return int(expired.lower() == 'yes')


def code_add(rewards, expired, eu_code, na_code, sea_code):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    if code_exists(eu_code):
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


def code_notify(code):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE promo_codes '
         'SET notified = 1 '
         'WHERE eu_code = ?'),
        [code]
    )
    db.commit()


def codes_unnotified_exists():
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
        print("Error: code_unnotified_exists()")
        exist = -1
    return exist


def codes_unnotified():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT eu_code, na_code, sea_code, rewards '
         'FROM promo_codes '
         'WHERE notified = 0 AND expired = 0')
    )
    try:
        exist = cur.fetchall()
    except TypeError:
        print("Error: codes_unnotified()")
        exist = -1
    return exist


def codes_unexpired():
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
        print("Error: codes_unexpired()")
        exist = -1
    return exist


def codes_notify_allowed(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT codes_notify '
         'FROM users '
         'WHERE uid = ?'),
        [uid]
    )
    try:
        allowed = cur.fetchone()[0]  # (x,)
    except TypeError:
        print(f"Error: codes_notify({uid})")
        allowed = -1
    return allowed


def codes_notify_toggle(uid):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('UPDATE users '
         'SET codes_notify = NOT codes_notify '
         'WHERE uid = ?'),
        [uid]
    )
    db.commit()


class ResinThread(Thread):
    def __init__(self, event, uid, current_timer, context):
        Thread.__init__(self)
        self.stopped = event
        self.uid = uid
        self.current_timer = current_timer
        self.notified = False
        self.maxreached = False
        self.context = context
        self.daemon = True

    def notify(self, msg, cap=False):
        try:
            self.context.bot.send_message(
                chat_id=self.uid, text=msg)
        except Unauthorized:
            bot_blocked(self.uid)
            self.stopped.set()
        finally:
            if cap:
                self.maxreached = True
            else:
                self.notified = True

    def run(self):
        while not self.stopped.wait(self.current_timer):
            cresin = resin(self.uid)

            if cresin >= RESIN_MAX:
                self.stopped.set()
            else:
                self.current_timer = RESIN_REGEN_MIN * 60
                # debug
                # self.current_timer = 5

                resin_inc(self.uid, 1)

                cresin = resin(self.uid)
                cwarn = warn_threshold(self.uid)

                if cwarn <= cresin < RESIN_MAX and not self.notified:
                    self.notify(
                        (f"‼ Hey! You have {cresin} resin waiting!\n"
                         f"Don't let it lose ‼"))
                elif cresin >= RESIN_MAX and not self.maxreached:
                    self.notify(
                        (f"‼ Hey! You have {cresin} resin waiting!\n"
                         "You won't earn more resin! ‼"),
                        cap=True)
                    self.stopped.set()
                elif cresin < cwarn:
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
                    code_add(reward, expired, eu_code, na_code, sea_code)

                notify_promo_codes(self.updater)
