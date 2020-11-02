#!/usr/bin/env python3
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from threading import Event, Thread
from datetime import datetime
import sqlite3
import logging


def set_up_db():
    db = sqlite3.connect('paimon.db')
    cur = db.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
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
            ('INSERT INTO users '
             'VALUES (?, ?)'),
            [user_id, resin]
        )

    db.commit()
    db.close()


user_state = {}
threads = {}
wait_for_thread = []


def start(update, context):
    user_id = update.message.chat.id
    if not is_user_in_db(user_id):
        set_resin(user_id, 120)
        update.message.reply_text(
            ("Hi, {}\nTo start tracking your resin, "
             "set your current resin with /refill.")
            .format(update.message.chat.first_name),
            quote=True)
    else:
        user_state[user_id] = 'start'
        update.message.reply_text(
            ("You are familiar... If you want to change your resin value, "
             "set it with /refill."),
            quote=True)


def stop(update, context):
    user_id = update.message.chat.id
    if is_user_in_db(user_id):
        delete_from_db(user_id)
        update.message.reply_text(
            "I have deleted any information about you.",
            quote=True)
    else:
        update.message.reply_text(
            "I don't have information about you.",
            quote=True)


def warn(update, context):
    user_id = update.message.chat.id
    if not is_user_in_db(user_id):
        update.message.reply_text(
            ("Traveler! You need to start the bot with /start "
             "to set up your information."),
            quote=True)
    else:
        user_state[user_id] = 'warn'
        update.message.reply_text(
            "Tell me at what resin value should I notify you.",
            quote=True)


def refill(update, context):
    user_id = update.message.chat.id
    if not is_user_in_db(user_id):
        update.message.reply_text(
            ("Traveler! You need to start the bot with /start "
             "to set up your information."),
            quote=True)
    else:
        user_state[user_id] = 'refill'
        update.message.reply_text(
            "Tell me how much resin you have right now.",
            quote=True)


def myresin(update, context):
    user_id = update.message.chat.id
    if not is_user_in_db(user_id):
        update.message.reply_text(
            ("Traveler! You need to start the bot with /start "
             "to set up your information."),
            quote=True)
    else:
        user_state[user_id] = 'myresin'
        resin = get_resin(user_id)
        update.message.reply_text(
            "You have {} resin right now.".format(resin),
            quote=True)


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
            elif resin == 120 and not self.maxreached:
                self.stopped.set()
                self.context.bot.send_message(
                    chat_id=self.user_id,
                    text="Hey! You have {} resin waiting! Don't let it lose."
                    .format(resin)
                )
                self.maxreached = True
            elif resin < self.warn:
                self.notified = False
                self.maxreached = False

            self.current_timer = 480


def text(update, context):
    user_id = update.message.chat.id
    text = update.message.text
    try:
        if user_state[user_id] == 'refill':
            if text.isdigit():
                resin = int(text)
                set_resin(user_id, resin)
                update.message.reply_text(
                    "Ok. I have updated your resin to value: {}".format(resin),
                    quote=True)
                user_state[user_id] = 'timer'
                context.bot.send_message(
                    chat_id=user_id,
                    text=("Now tell me when you will get the next resin. "
                          "Use format mm:ss"))
            else:
                update.message.reply_text(
                    "{} te nandayo!!. You must give an integer value!"
                    .format(text),
                    quote=True)
        elif user_state[user_id] == 'timer':
            try:
                fmt = "%M:%S"
                datetime_obj = datetime.strptime(text, fmt)
                seconds = (int(datetime_obj.strftime('%M')) * 60
                           + int(datetime_obj.strftime('%S')))
                try:
                    threads[user_id][0].set()
                except KeyError:
                    pass
                resin_flag = Event()
                resin_thread = ResinThread(resin_flag, user_id,
                                           seconds, get_warn(user_id), context)
                threads[user_id] = (resin_flag, resin_thread)
                resin_thread.start()

                update.message.reply_text(
                    "Perfect. I'm tracking your resin.",
                    quote=True)

            except ValueError:
                update.message.reply_text(
                    "{} bad format! Use the format: mm:ss".format(text),
                    quote=True)
            pass
        elif user_state[user_id] == 'warn':
            if text.isdigit():
                warn = int(text)
                set_warn(user_id, warn)
                update.message.reply_text(
                    ("Ok. I have updated your resin warning to value: {}. "
                     "You must /refill again to update the warning.")
                    .format(warn),
                    quote=True)
            else:
                update.message.reply_text(
                    "{} te nandayo!!. You must give an integer value!"
                    .format(text),
                    quote=True)
        else:
            update.message.reply_text(
                ("To start tracking your resin, "
                 "set your current resin with /refill."),
                quote='True')
    except KeyError:
        update.message.reply_text(
            ("Use /myresin if you want to know your current resin.\n"
             "Use /refill to change your resin value."),
            quote=True)


if __name__ == '__main__':
    logging.basicConfig(format=('%(asctime)s - %(name)s - '
                                '%(levelname)s - %(message)s'),
                        level=logging.INFO)
    API_KEY = ''
    with open(".apikey", 'r') as f:
        API_KEY = f.read().strip()

    set_up_db()

    updater = Updater(token=API_KEY, use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    stop_handler = CommandHandler('stop', stop)
    dispatcher.add_handler(stop_handler)

    refill_handler = CommandHandler('refill', refill)
    dispatcher.add_handler(refill_handler)

    myresin_handler = CommandHandler('myresin', myresin)
    dispatcher.add_handler(myresin_handler)

    text_handler = MessageHandler(Filters.text, text)
    dispatcher.add_handler(text_handler)

    updater.start_polling()
    updater.idle()
