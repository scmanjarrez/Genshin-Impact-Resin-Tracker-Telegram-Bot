#!/usr/bin/env python3
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.error import Unauthorized
from telegram import ParseMode
from datetime import datetime
from threading import Event
import util
import logging


user_state = {}
threads = {}


def bot_blocked(user_id):
    try:
        threads[user_id][0].set()
        del user_state[user_id]
        del threads[user_id]
    except KeyError:
        pass
    finally:
        util.delete_user_from_db(user_id)


def start(update, context):
    user_id = update.message.chat.id
    if not util.is_user_in_db(user_id):
        util.set_resin(user_id, util.MAX_RESIN)
        try:
            update.message.reply_text(
                ("Hi, {}\nTo start tracking your resin, "
                 "set your current resin with /refill.")
                .format(update.message.chat.first_name),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        user_state[user_id] = 'start'
        try:
            update.message.reply_text(
                ("You are familiar... If you want to change your resin value, "
                 "set it with /refill."),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)


def refill(update, context):
    user_id = update.message.chat.id
    if not util.is_user_in_db(user_id):
        try:
            update.message.reply_text(
                ("Traveler! You need to start the bot with /start "
                 "to set up your information."),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        if context.args:
            if len(context.args) < 2:
                try:
                    update.message.reply_text(
                        "Incorrect number of arguments. Use /refill x mm:ss.",
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)
            else:
                try:
                    resin = int(context.args[0])
                except ValueError:
                    try:
                        update.message.reply_text(
                            ("{} te nandayo! "
                             "You must give an integer value and lower than {}!")
                            .format(context.args[0], util.MAX_RESIN),
                            quote=True)
                    except Unauthorized:
                        bot_blocked(user_id)
                else:
                    if resin >= util.MAX_RESIN:
                        try:
                            context.bot.send_message(
                                chat_id=user_id,
                                text=("You can't have more than {} resin! "
                                      .format(util.MAX_RESIN)))
                        except Unauthorized:
                            bot_blocked(user_id)
                    else:
                        next_resin = context.args[1]
                        fmt = "%M:%S"
                        try:
                            datetime_obj = datetime.strptime(next_resin, fmt)
                        except ValueError:
                            try:
                                update.message.reply_text(
                                    "{} te nandayo! Use format mm:ss!"
                                    .format(next_resin),
                                    quote=True)
                            except Unauthorized:
                                bot_blocked(user_id)
                        else:
                            seconds = (int(datetime_obj.strftime('%M')) * 60
                                       + int(datetime_obj.strftime('%S')))

                            try:
                                threads[user_id][0].set()
                            except KeyError:
                                pass
                            finally:
                                util.set_resin(user_id, resin)

                                resin_flag = Event()
                                resin_thread = util.ResinThread(resin_flag, user_id,
                                                                seconds,
                                                                util.get_warn(user_id),
                                                                context)
                                threads[user_id] = (resin_flag, resin_thread)
                                resin_thread.start()
                                try:
                                    update.message.reply_text(
                                        "Perfect. I'm tracking your resin.",
                                        quote=True)
                                except Unauthorized:
                                    bot_blocked(user_id)

        else:
            user_state[user_id] = 'refill'
            try:
                update.message.reply_text(
                    "Tell me how many resin you have right now.",
                    quote=True)
            except Unauthorized:
                bot_blocked(user_id)


def spend(update, context):
    user_id = update.message.chat.id
    if not util.is_user_in_db(user_id):
        try:
            update.message.reply_text(
                ("Traveler! You need to start the bot with /start "
                 "to set up your information."),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        if context.args:
            cur_resin = util.get_resin(user_id)
            try:
                resin = int(context.args[0])
            except ValueError:
                try:
                    update.message.reply_text(
                        ("{} te nandayo! "
                         "You must give an integer value and lower than {}!")
                        .format(context.args[0], util.MAX_RESIN),
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)
            else:
                if resin > cur_resin:
                    try:
                        context.bot.send_message(
                            chat_id=user_id,
                            text=("You can't spend more than {} resin! "
                                  .format(cur_resin)))
                    except Unauthorized:
                        bot_blocked(user_id)
                else:
                    util.dec_resin(user_id, resin)

                    if user_id in threads and threads[user_id][1].is_alive():
                        pass
                    else:
                        seconds = 8 * 60
                        resin_flag = Event()
                        resin_thread = util.ResinThread(resin_flag, user_id,
                                                        seconds,
                                                        util.get_warn(user_id),
                                                        context)
                        threads[user_id] = (resin_flag, resin_thread)
                        resin_thread.start()
                    try:
                        newresin = util.get_resin(user_id)
                        update.message.reply_text(
                            "Perfect. I've updated your resin to {}."
                            .format(newresin),
                            quote=True)
                    except Unauthorized:
                        bot_blocked(user_id)
        else:
            user_state[user_id] = 'spend'
            try:
                update.message.reply_text(
                    "Tell me how many resin you want to spend.",
                    quote=True)
            except Unauthorized:
                bot_blocked(user_id)


def warn(update, context):
    user_id = update.message.chat.id
    if not util.is_user_in_db(user_id):
        try:
            update.message.reply_text(
                ("Traveler! You need to start the bot with /start "
                 "to set up your information."),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        if context.args:
            try:
                warn = int(context.args[0])
            except ValueError:
                try:
                    update.message.reply_text(
                        "{} te nandayo!!. You must give an integer value!"
                        .format(context.args[0]),
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)
            else:
                if warn > util.MAX_RESIN:
                    try:
                        context.bot.send_message(
                            chat_id=user_id,
                            text=("I can't notify you above {} resin! "
                                  .format(util.MAX_RESIN)))
                    except Unauthorized:
                        bot_blocked(user_id)
                else:
                    util.set_warn(user_id, warn)

                    try:
                        update.message.reply_text(
                            ("Ok. I have updated your resin warning to value: {}. "
                             "You must /refill again to update the warning.")
                            .format(warn),
                            quote=True)
                    except Unauthorized:
                        bot_blocked(user_id)
        else:
            user_state[user_id] = 'warn'
            try:
                update.message.reply_text(
                    ("I'm warning you at {} resin. "
                     "Tell me at what resin value should I notify you."
                     .format(util.get_warn(user_id))),
                    quote=True)
            except Unauthorized:
                bot_blocked(user_id)


def myresin(update, context):
    user_id = update.message.chat.id
    if not util.is_user_in_db(user_id):
        try:
            update.message.reply_text(
                ("Traveler! You need to start the bot with /start "
                 "to set up your information."),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        user_state[user_id] = 'myresin'
        resin = util.get_resin(user_id)
        try:
            update.message.reply_text(
                "You have {} resin right now.".format(resin),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)


def notrack(update, context):
    user_id = update.message.chat.id
    if not util.is_user_in_db(user_id):
        try:
            update.message.reply_text(
                ("Traveler! You need to start the bot with /start "
                 "to set up your information."),
            quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        user_state[user_id] = 'notrack'
        try:
            threads[user_id][0].set()
        except KeyError:
            pass
        finally:
            try:
                update.message.reply_text(
                    "Ok. I have stopped the resin tracking.",
                    quote=True)
            except Unauthorized:
                bot_blocked(user_id)


def bothelp(update, context):
    try:
        update.message.reply_text(
            ("/start Start bot, set up your information. "
             "Mandatory if you want to interact with the bot.\n\n"
             "/refill Change your current resin value. "
             "Can be called alone or passing resin and time as parameters, "
             "e.g. /refill or /refill 50 00:04.\n\n"
             "/spend Decrease your current resin value by a given quantity.\n\n"
             "/warn Change resin notification value. "
             "Set the value to be notified at. Can be called alone or "
             "passing limit as parameter, "
             "e.g. /warn or /warn 110.\n\n"
             "/myresin Show current resin value.\n\n"
             "/notrack Cancel current resin tracking.\n\n"
             "/help Show this message.\n\n"
             "/cancel Cancel current command.\n\n"
             "/stop Delete bot information about you.\n\n"),
        quote=True)
    except Unauthorized:
        bot_blocked(user_id)


def cancel(update, context):
    user_id = update.message.chat.id
    if util.is_user_in_db(user_id):
        user_state[user_id] = 'start'
        try:
            update.message.reply_text(
                "Current command cancelled.",
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        try:
            update.message.reply_text(
                "I don't have information about you.",
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)


def stop(update, context):
    user_id = update.message.chat.id
    if util.is_user_in_db(user_id):
        util.delete_user_from_db(user_id)
        try:
            update.message.reply_text(
                "I have deleted any information about you.",
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)
    else:
        try:
            update.message.reply_text(
                "I don't have information about you.",
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)


def announce(update, context):
    user_id = update.message.chat.id
    with open('.adminid', 'r') as f:
        admin_id = f.read().strip()
    if int(user_id) == int(admin_id):
        msg = "*Announcement:* " + " ".join(context.args)
        users = util.get_users()
        for user, in users:
            try:
                context.bot.send_message(chat_id=user,
                                         text=msg,
                                         parse_mode=ParseMode.MARKDOWN)
            except Unauthorized:
                bot_blocked(user)


def text(update, context):
    user_id = update.message.chat.id
    text = update.message.text
    try:
        if user_state[user_id] == 'refill':
            try:
                resin = int(text)
            except ValueError:
                try:
                    update.message.reply_text(
                        ("{} te nandayo! "
                         "You must give an integer value and lower than {}.")
                        .format(text, util.MAX_RESIN),
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)
            else:
                if resin >= util.MAX_RESIN:
                    try:
                        context.bot.send_message(
                            chat_id=user_id,
                            text=("You can't have more than {} resin! "
                                  .format(util.MAX_RESIN)))
                    except Unauthorized:
                        bot_blocked(user_id)
                else:
                    try:
                        threads[user_id][0].set()
                    except KeyError:
                        pass
                    finally:
                        util.set_resin(user_id, resin)
                        user_state[user_id] = 'timer'
                        try:
                            update.message.reply_text(
                                ("Ok. I have updated your resin to value: {}. "
                                 "Now tell me when you will get the next resin. Use format mm:ss.")
                                .format(resin),
                                quote=True)
                        except Unauthorized:
                            bot_blocked(user_id)
        elif user_state[user_id] == 'timer':
            try:
                fmt = "%M:%S"
                datetime_obj = datetime.strptime(text, fmt)
            except ValueError:
                try:
                    update.message.reply_text(
                        "{} te nandayo! Use the format mm:ss!".format(text),
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)
            else:
                seconds = (int(datetime_obj.strftime('%M')) * 60
                           + int(datetime_obj.strftime('%S')))

                resin_flag = Event()
                resin_thread = util.ResinThread(resin_flag, user_id,
                                                seconds,
                                                util.get_warn(user_id),
                                                context)
                threads[user_id] = (resin_flag, resin_thread)
                resin_thread.start()

                try:
                    update.message.reply_text(
                        "Perfect. I'm tracking your resin.",
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)

        elif user_state[user_id] == 'warn':
            try:
                warn = int(text)
            except ValueError:
                try:
                    update.message.reply_text(
                        "{} te nandayo!!. You must give an integer value!"
                        .format(text),
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)
            else:
                if warn > util.MAX_RESIN:
                    try:
                        context.bot.send_message(
                            chat_id=user_id,
                            text=("I can't notify you above {} resin! "
                                  .format(util.MAX_RESIN)))
                    except Unauthorized:
                        bot_blocked(user_id)

                util.set_warn(user_id, warn)

                try:
                    update.message.reply_text(
                        ("Ok. I have updated your resin warning to value: {}. "
                         "You must /refill again to update the warning.")
                        .format(warn),
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)

        elif user_state[user_id] == 'spend':
            cur_resin = util.get_resin(user_id)
            try:
                resin = int(text)
            except ValueError:
                try:
                    update.message.reply_text(
                        ("{} te nandayo! "
                         "You must give an integer value and lower than {}!")
                        .format(text, cur_resin),
                        quote=True)
                except Unauthorized:
                    bot_blocked(user_id)
            else:
                if resin > cur_resin:
                    try:
                        context.bot.send_message(
                            chat_id=user_id,
                            text=("You can't spend more than {} resin! "
                                  .format(cur_resin)))
                    except Unauthorized:
                        bot_blocked(user_id)
                else:
                    util.dec_resin(user_id, resin)

                    if user_id in threads and threads[user_id][1].is_alive():
                        pass
                    else:
                        seconds = 8 * 60
                        resin_flag = Event()
                        resin_thread = util.ResinThread(resin_flag, user_id,
                                                        seconds,
                                                        util.get_warn(user_id),
                                                        context)
                        threads[user_id] = (resin_flag, resin_thread)
                        resin_thread.start()

                    cur_resin = util.get_resin(user_id)
                    try:
                        update.message.reply_text(
                            "Perfect. I've updated your resin to {}."
                            .format(cur_resin),
                            quote=True)
                    except Unauthorized:
                        bot_blocked(user_id)
        else:
            try:
                update.message.reply_text(
                    ("To start tracking your resin, "
                     "set your current resin with /refill."),
                quote='True')
            except Unauthorized:
                bot_blocked(user_id)
    except KeyError:
        try:
            update.message.reply_text(
                ("Use /myresin if you want to know your current resin.\n"
                 "Use /refill to change your resin value."),
                quote=True)
        except Unauthorized:
            bot_blocked(user_id)


def warn_users(updater):
    msg = ("*Announcement:* Bot is restarting, all tracking are lost. "
           "Refill your resin!")
    users = util.get_users()
    for user, in users:
        updater.bot.send_message(chat_id=user,
                                 text=msg,
                                 parse_mode=ParseMode.MARKDOWN)


if __name__ == '__main__':
    logging.basicConfig(format=('%(asctime)s - %(name)s - '
                                '%(levelname)s - %(message)s'),
                        level=logging.INFO)
    API_KEY = ''
    with open(".apikey", 'r') as f:
        API_KEY = f.read().strip()

    util.set_up_db()

    updater = Updater(token=API_KEY, use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    refill_handler = CommandHandler('refill', refill)
    dispatcher.add_handler(refill_handler)

    spend_handler = CommandHandler('spend', spend)
    dispatcher.add_handler(spend_handler)

    warn_handler = CommandHandler('warn', warn)
    dispatcher.add_handler(warn_handler)

    myresin_handler = CommandHandler('myresin', myresin)
    dispatcher.add_handler(myresin_handler)

    notrack_handler = CommandHandler('notrack', notrack)
    dispatcher.add_handler(notrack_handler)

    help_handler = CommandHandler('help', bothelp)
    dispatcher.add_handler(help_handler)

    cancel_handler = CommandHandler('cancel', cancel)
    dispatcher.add_handler(cancel_handler)

    stop_handler = CommandHandler('stop', stop)
    dispatcher.add_handler(stop_handler)

    announce_handler = CommandHandler('announce', announce)
    dispatcher.add_handler(announce_handler)

    text_handler = MessageHandler(Filters.text, text)
    dispatcher.add_handler(text_handler)

    updater.start_polling()
    updater.idle()

    warn_users(updater)
