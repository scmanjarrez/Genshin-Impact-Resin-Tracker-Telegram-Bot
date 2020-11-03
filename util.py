from threading import Thread
import sqlite3


MAX_RESIN = 120


def set_up_db():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            resin INTEGER DEFAULT 0,
            warn INTEGER DEFAULT 110
        )''')
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
    exist = cur.fetchone()[0]  # (1,) if exists, (0,) otherwise
    db.close()
    return exist


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


def delete_from_db(user_id):
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


def get_resin(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT resin '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    resin = cur.fetchone()[0]  # (x,)
    db.close()
    return resin


def get_warn(user_id):
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()
    cur.execute(
        ('SELECT warn '
         'FROM users '
         'WHERE user_id = ?'),
        [user_id]
    )
    warn = cur.fetchone()[0]  # (x,)
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
            ('INSERT INTO users (user_id, warn)'
             'VALUES (?, ?)'),
            [user_id, warn]
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
            ('INSERT INTO users (user_id, resin)'
             'VALUES (?, ?)'),
            [user_id, resin]
        )

    db.commit()
    db.close()


class ResinThread(Thread):
    def __init__(self, event, user_id, current_timer, warn, context):
        Thread.__init__(self)
        self.stopped = event
        self.user_id = user_id
        self.current_timer = current_timer
        self.warn = warn
        self.notified = False
        self.maxreached = False
        self.context = context
        self.daemon = True

    def run(self):
        while not self.stopped.wait(self.current_timer):
            inc_resin(self.user_id)
            resin = get_resin(self.user_id)
            if resin >= self.warn and not self.notified:
                self.context.bot.send_message(
                    chat_id=self.user_id,
                    text="Hey! You have {} resin waiting! Don't let it lose."
                    .format(resin)
                )
                self.notified = True
            elif resin == MAX_RESIN and not self.maxreached:
                self.stopped.set()
                self.context.bot.send_message(
                    chat_id=self.user_id,
                    text=("Hey! You have {} resin waiting! "
                          "You won't gain more resin!.")
                    .format(resin)
                )
                self.maxreached = True
            elif resin < self.warn:
                self.notified = False
                self.maxreached = False

            self.current_timer = 480
