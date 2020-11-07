#!/usr/bin/env python3
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.error import Unauthorized
from telegram import ParseMode
from datetime import datetime
from threading import Event
import util
import logging


user_state = {}
tmp_resin = {}
threads = {}


def clean_state(user_id):
    user_state[user_id] = ''


def set_state(user_id, state):
    user_state[user_id] = state


def bot_blocked(user_id):
    if user_id in threads:
        threads[user_id][0].set()
        del threads[user_id]

    if user_id in user_state:
        del user_state[user_id]

    util.delete_user_from_db(user_id)


def warn_user(user_id, reason):
    msg = ["➡ Check /help to know what I can do\n\n",
           "⛔ Don't flood the bot or ",
           "you will be banned from the bot ⛔"]

    if reason == 'cmd':
        msg.insert(0, "🚫 Unknown command 🚫\n\n")

    elif reason == 'restarted':
        msg.insert(0, "‼ Bot restarted and lost all trackings ‼\n\n")

    strikes = util.get_strikes(user_id)

    if strikes >= util.BAN_STRIKE - 1:
        msg = ("⛔ You have been banned from the bot "
               "for spam/flooding ⛔")
        util.ban_user(user_id)

    util.inc_strike(user_id)
    return "".join(msg)


def warn_not_started(update):
    send_message(update,
                 ("Traveller! You need to start the bot with /start "
                  "before you can use it!"))


def send_message(update, msg):
    try:
        update.message.reply_text(msg, quote=True)
    except Unauthorized:
        bot_blocked(update.effective_message.chat.id)


def start(update, context):
    user_id = update.effective_message.chat.id
    clean_state(user_id)

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            util.set_resin(user_id, util.MAX_RESIN)
            first_name = update.message.chat.first_name
            send_message(update,
                         (f"Hi, {first_name}\n\n"
                          f"➡ Check /help to know what I can do\n\n"))
        else:
            send_message(update,
                         ("You are familiar...\n\n"
                          "➡ Check /help to know what I can do"))


def refill(update, context):
    user_id = update.effective_message.chat.id

    msg = "Tell me your current resin value."

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            if context.args:
                if len(context.args) < 2:
                    msg = ("Incorrect number of parameters. "
                           "Use /refill <value> <mm:ss>")
                    util.inc_strike(user_id)
                else:
                    resin_arg = context.args[0]
                    time_arg = context.args[1]

                    try:
                        resin = int(resin_arg)
                    except ValueError:
                        msg = (f"{resin_arg} te nandayo! "
                               f"You must give a number "
                               f"lower than {util.MAX_RESIN}!")
                        util.inc_strike(user_id)
                    else:
                        if resin < 0:
                            msg = "You can't have negative values of resin!"
                            util.inc_strike(user_id)
                        elif resin >= util.MAX_RESIN:
                            msg = (f"You can't have more "
                                   f"than {util.MAX_RESIN} resin!")
                            util.inc_strike(user_id)
                        else:
                            fmt = "%M:%S"
                            try:
                                datetime_obj = datetime.strptime(time_arg, fmt)
                            except ValueError:
                                msg = (f"{time_arg} te nandayo! "
                                       f"You must use the format mm:ss!")
                                util.inc_strike(user_id)
                            else:
                                seconds = (
                                    int(datetime_obj.strftime('%M')) * 60
                                    + int(datetime_obj.strftime('%S')))

                                if user_id in threads:
                                    threads[user_id][0].set()

                                util.set_resin(user_id, resin)

                                resin_flag = Event()
                                resin_thread = util.ResinThread(resin_flag,
                                                                user_id,
                                                                seconds,
                                                                context)
                                threads[user_id] = (resin_flag, resin_thread)
                                resin_thread.start()

                                clean_state(user_id)
                                msg = "Perfect. I'm tracking your resin."
                                util.dec_strike(user_id)

            else:
                set_state(user_id, 'refill')

            send_message(update, msg)


def spend(update, context):
    user_id = update.effective_message.chat.id

    msg = "How many resin do you want to spend?"

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            if context.args:
                resin_arg = context.args[0]

                cur_resin = util.get_resin(user_id)
                try:
                    resin = int(resin_arg)
                except ValueError:
                    msg = (f"{resin_arg} te nandayo! "
                           f"You must give a number "
                           f"lower than {util.MAX_RESIN}!")
                    util.inc_strike(user_id)
                else:
                    if resin < 0:
                        msg = "You can't spend negative values of resin!"
                        util.inc_strike(user_id)
                    elif resin > cur_resin:
                        msg = (f"You can't spend more "
                               f"than {cur_resin} resin!")
                        util.inc_strike(user_id)
                    else:
                        util.dec_resin(user_id, resin)

                        if user_id not in threads or (
                                user_id in threads and
                                not threads[user_id][1].is_alive()):
                            seconds = util.RESIN_REGEN_MIN * 60
                            resin_flag = Event()
                            resin_thread = util.ResinThread(resin_flag,
                                                            user_id,
                                                            seconds,
                                                            context)
                            threads[user_id] = (resin_flag, resin_thread)
                            resin_thread.start()

                        clean_state(user_id)
                        cur_resin = util.get_resin(user_id)
                        msg = f"I have updated your resin to {cur_resin}."
                        util.dec_strike(user_id)
            else:
                set_state(user_id, 'spend')

            send_message(update, msg)


def warn(update, context):
    user_id = update.effective_message.chat.id

    msg = (f"Notification threshold can't be "
           f"higher than {util.MAX_RESIN} resin!")

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            if context.args:
                warn_arg = context.args[0]

                try:
                    warn = int(warn_arg)
                except ValueError:
                    msg = (f"{warn_arg} te nandayo! "
                           f"You must give a number "
                           f"lower than {util.MAX_RESIN}!")
                    util.inc_strike(user_id)
                else:
                    if warn < 0:
                        msg = "Notification threshold can't be negative!"
                        util.inc_strike(user_id)
                    elif warn <= util.MAX_RESIN:
                        util.set_warn(user_id, warn)

                        clean_state(user_id)
                        msg = (f"I have updated your "
                               f"notifications threshold to {warn} resin.")
                        util.dec_strike(user_id)
            else:
                set_state(user_id, 'warn')
                msg = "Tell me your new notification threshold."

            send_message(update, msg)


def myresin(update, context):
    user_id = update.effective_message.chat.id

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            clean_state(user_id)
            resin = util.get_resin(user_id)

            send_message(update,
                         f"You currently have {resin} resin.")


def maxresin(update, context):
    user_id = update.effective_message.chat.id

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            clean_state(user_id)
            cap_hour, cap_min = util.max_resin(user_id)

            if cap_hour == 0 and cap_min == 0:
                msg = ("You have hit the resin cap. Hurry up!")

            else:
                if util.custom_timezone(user_id):
                    timezone = util.get_timezone(user_id)

                    user_hour = (int(datetime.strftime(datetime.now(), '%H'))
                                 + timezone) % 24
                    local_min = int(datetime.strftime(datetime.now(), '%M'))

                    full_min = (local_min + cap_min) % 60
                    carry_hour = (local_min + cap_min) // 60
                    full_hour = (user_hour + cap_hour + carry_hour) % 24

                    msg = (f"Your resin will be capped in "
                           f"{cap_hour} hour(s) and {cap_min} minute(s) "
                           f"approx. at {full_hour:02}:{full_min:02}h.")
                else:
                    msg = (f"Your resin will be capped in "
                           f"{cap_hour:02} hours and {cap_min:02} minutes.")

            send_message(update, msg)


def timezone(update, context):
    user_id = update.effective_message.chat.id

    msg = "Tell me your current hour. Use 24h format: hh:mm."

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            if context.args:
                hour_arg = context.args[0]

                fmt = "%H:%M"

                try:
                    user_time = datetime.strptime(hour_arg, fmt)
                except ValueError:
                    msg = (f"{hour_arg} te nandayo! "
                           f"You must use the format hh:mm!")
                    util.inc_strike(user_id)
                else:
                    local_hour = datetime.strftime(datetime.now(), '%H')
                    user_hour = user_time.strftime('%H')
                    timezone = int(user_hour) - int(local_hour)

                    clean_state(user_id)
                    util.set_timezone(user_id, timezone)
                    msg = ("I have updated your timezone. "
                           "Command /maxresin "
                           "will show an estimated hour "
                           "when you'll hit the resin cap.")
                    util.dec_strike(user_id)
            else:
                set_state(user_id, 'timezone')

            send_message(update, msg)


def mytimezone(update, context):
    user_id = update.effective_message.chat.id

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            clean_state(user_id)

            if util.custom_timezone(user_id):
                timezone = util.get_timezone(user_id)

                user_hour = (int(datetime.strftime(datetime.now(), '%H'))
                             + timezone) % 24
                local_min = int(datetime.strftime(datetime.now(), '%M'))

                msg = (f"Your current time is {user_hour:02}:{local_min:02} "
                       f"({'+' if timezone > 0 else ''}{timezone}).")
            else:
                msg = ("You haven't set your timezone. "
                       "Command /maxresin will show only "
                       "the remaining time before you hit the resin cap.")

            send_message(update, msg)


def mywarn(update, context):
    user_id = update.effective_message.chat.id

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            clean_state(user_id)
            warn = util.get_warn(user_id)

            send_message(update,
                         (f"Your current notification threshold "
                          f"is {warn} resin."))


def notrack(update, context):
    user_id = update.effective_message.chat.id

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            clean_state(user_id)
            msg = "Resin tracker isn't active."

            if user_id in threads:
                threads[user_id][0].set()
                msg = "I have stopped your resin tracker."

            send_message(update, msg)


def bothelp(update, context):
    user_id = update.effective_message.chat.id

    if not util.is_user_banned(user_id):
        send_message(update,
                     ("➡ /start Set up your information. "
                      "Mandatory to interact with the bot.\n"

                      "➡ /refill Change your current resin value. "
                      "Use it alone or passing value and time as parameters, "
                      "e.g. /refill or /refill 50 02:10.\n"

                      "➡ /spend Spend your resin. "
                      "Use it alone or passing value as parameter, "
                      "e.g. /spend or /spend 80.\n"

                      "➡ /myresin Show your current resin value.\n"

                      "➡ /maxresin Show an estimation when you'll hit "
                      "the resin cap. To show an estimated hour, "
                      "set your timezone with /timezone command.\n"

                      "➡ /warn Change your notification threshold. "
                      "Use it alone or passing value as parameter. "
                      "e.g. /warn or /warn 100.\n"

                      "➡ /mywarn Show your current notification threshold.\n"

                      "➡ /timezone Set your timezone to show an "
                      "estimated hour with /maxresin command. "
                      "Use it alone or passing hour as parameter, e.g. "
                      "/timezone or /timezone 17:45.\n"

                      "➡ /mytimezone Show your personalized timezone.\n"

                      "➡ /notrack Stop resin tracking.\n"

                      "➡ /help Show bot usage.\n"

                      "➡ /cancel Cancel any pending operation.\n"

                      "➡ /stop Delete your information from bot database.\n"))


def cancel(update, context):
    user_id = update.effective_message.chat.id
    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            clean_state(user_id)
            send_message(update, "Current command cancelled.")


def stop(update, context):
    user_id = update.effective_message.chat.id
    msg = "I don't have information about you."

    if not util.is_user_banned(user_id):
        if util.is_user_in_db(user_id):
            bot_blocked(user_id)
            msg = "I have deleted your information from my database."

        send_message(update, msg)


def announce(update, context):
    user_id = update.effective_message.chat.id

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
    user_id = update.effective_message.chat.id
    text = update.message.text

    msg = ("Bot restarted and lost all trackings. "
           "Please, refill your resin.")

    if not util.is_user_banned(user_id):
        if not util.is_user_in_db(user_id):
            warn_not_started(update)
        else:
            if text.startswith('/'):
                msg = warn_user(user_id, 'cmd')
            else:
                if user_id in user_state:
                    if user_state[user_id] == 'refill':
                        try:
                            resin = int(text)
                        except ValueError:
                            msg = (f"{text} te nandayo! "
                                   f"You must give a number "
                                   f"lower than {util.MAX_RESIN}!")
                            util.inc_strike(user_id)
                        else:
                            if resin < 0:
                                msg = ("You can't have negative "
                                       "values of resin!")
                                util.inc_strike(user_id)
                            elif resin >= util.MAX_RESIN:
                                msg = (f"You can't have more "
                                       f"than {util.MAX_RESIN} resin!")
                                util.inc_strike(user_id)
                            else:
                                tmp_resin[user_id] = resin

                                user_state[user_id] = 'timer'
                                msg = ("Now tell me the time "
                                       "until you get your next resin. "
                                       "Use the format mm:ss.")
                    elif user_state[user_id] == 'timer':
                        fmt = "%M:%S"
                        try:
                            datetime_obj = datetime.strptime(text, fmt)
                        except ValueError:
                            msg = (f"{text} te nandayo! "
                                   f"You must use the format mm:ss!")
                            util.inc_strike(user_id)
                        else:
                            seconds = (int(datetime_obj.strftime('%M')) * 60
                                       + int(datetime_obj.strftime('%S')))

                            if user_id in threads:
                                threads[user_id][0].set()

                            if user_id in tmp_resin:
                                util.set_resin(user_id, tmp_resin[user_id])
                                del tmp_resin[user_id]

                                resin_flag = Event()
                                resin_thread = util.ResinThread(resin_flag,
                                                                user_id,
                                                                seconds,
                                                                context)
                                threads[user_id] = (resin_flag, resin_thread)
                                resin_thread.start()

                                msg = "Perfect. I'm tracking your resin."
                                util.dec_strike(user_id)
                            else:
                                msg = ("Error happened processing "
                                       "your request. "
                                       "Start refill process again.")
                    elif user_state[user_id] == 'warn':
                        try:
                            warn = int(text)
                        except ValueError:
                            msg = (f"{text} te nandayo! "
                                   f"You must give a number "
                                   f"lower than {util.MAX_RESIN}!")
                            util.inc_strike(user_id)
                        else:
                            if warn < 0:
                                msg = ("Notification threshold "
                                       "can't be negative!")
                                util.inc_strike(user_id)
                            elif warn > util.MAX_RESIN:
                                msg = (f"Notification threshold can't be "
                                       f"higher than {util.MAX_RESIN} resin!")
                                util.inc_strike(user_id)

                            else:
                                util.set_warn(user_id, warn)
                                msg = (f"I have updated your "
                                       f"notifications to {warn} resin.")
                                util.dec_strike(user_id)
                    elif user_state[user_id] == 'spend':
                        try:
                            resin = int(text)
                        except ValueError:
                            msg = (f"{text} te nandayo! "
                                   f"You must give a number "
                                   f"lower than {util.MAX_RESIN}!")
                            util.inc_strike(user_id)
                        else:
                            cur_resin = util.get_resin(user_id)
                            if resin < 0:
                                msg = ("You can't spend "
                                       "negative values of resin!")
                                util.inc_strike(user_id)
                            elif resin > cur_resin:
                                msg = (f"You can't spend more "
                                       f"than {cur_resin} resin!")
                                util.inc_strike(user_id)
                            else:
                                util.dec_resin(user_id, resin)

                                if user_id not in threads or (
                                        user_id in threads and
                                        not threads[user_id][1].is_alive()):
                                    seconds = 8 * 60
                                    resin_flag = Event()
                                    resin_thread = util.ResinThread(resin_flag,
                                                                    user_id,
                                                                    seconds,
                                                                    context)
                                    threads[user_id] = (resin_flag,
                                                        resin_thread)
                                    resin_thread.start()

                                cur_resin = util.get_resin(user_id)

                                msg = (f"I have updated your "
                                       f"resin to {cur_resin}.")
                                util.dec_strike(user_id)
                    elif user_state[user_id] == 'timezone':
                        fmt = "%H:%M"
                        try:
                            user_time = datetime.strptime(text, fmt)
                        except ValueError:
                            msg = (f"{text} te nandayo! "
                                   f"You must use the format hh:mm!")
                            util.inc_strike(user_id)
                        else:
                            local_hour = datetime.strftime(
                                datetime.now(),
                                '%H')
                            user_hour = user_time.strftime('%H')
                            timezone = int(user_hour) - int(local_hour)

                            clean_state(user_id)
                            util.set_timezone(user_id, timezone)
                            msg = ("I have updated your timezone. "
                                   "Command /maxresin "
                                   "will show an estimated hour "
                                   "when you'll' hit the resin cap.")
                            util.dec_strike(user_id)
                    else:
                        msg = warn_user(user_id, 'help')
                else:
                    msg = warn_user(user_id, 'restart')
            send_message(update, msg)


def notify_restart(updater):
    msg = ("*Announcement:* Bot is restarting, all tracking are lost. "
           "Please, refill your resin.")
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

    maxresin_handler = CommandHandler('maxresin', maxresin)
    dispatcher.add_handler(maxresin_handler)

    timezone_handler = CommandHandler('timezone', timezone)
    dispatcher.add_handler(timezone_handler)

    mytimezone_handler = CommandHandler('mytimezone', mytimezone)
    dispatcher.add_handler(mytimezone_handler)

    mywarn_handler = CommandHandler('mywarn', mywarn)
    dispatcher.add_handler(mywarn_handler)

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

    notify_restart(updater)
