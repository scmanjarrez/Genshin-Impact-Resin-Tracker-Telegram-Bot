#!/usr/bin/env python3
from telegram.ext import (Updater, CommandHandler,
                          MessageHandler, Filters, CallbackQueryHandler)
from telegram.error import Unauthorized, BadRequest
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from threading import Event
# from pprint import pprint
import util
import logging


user_state = {}
user_menu_state = {}
tmp_resin = {}
threads = {}


def state(uid, state=''):
    user_state[uid] = state


def bot_blocked(uid):
    if uid in threads:
        threads[uid][0].set()
        del threads[uid]

    if uid in user_state:
        del user_state[uid]

    util.user_remove(uid)


def warn_user(uid, reason):
    msg = ["➡ Check /help to know what I can do\n\n",
           "⛔ Don't flood the bot or ",
           "you will be banned from the bot ⛔"]
    if reason == 'cmd':
        msg.insert(0, "🚫 Unknown command 🚫\n\n")
    elif reason == 'restarted':
        msg.insert(0, "‼ Bot restarted and lost all trackings ‼\n\n")
    strikes = util.strikes(uid)
    if strikes >= util.STRIKE_BAN - 1:
        msg = ("⛔ You have been banned from the bot "
               "for spam/flooding ⛔")
        util.user_ban(uid)
    util.strikes_inc(uid)
    return "".join(msg)


def warn_not_started(update):
    send_message(update,
                 ("Traveller! You need to start the bot with /start "
                  "before you can use it!"))


def send_message(update, msg, quote=True, reply_markup=None, markdown=False):
    if update is not None:
        try:
            reply = getattr(update.message, 'reply_text')
            if markdown:
                reply = getattr(update.message, 'reply_markdown')
            try:
                reply(msg, quote=quote,
                      reply_markup=reply_markup)
            except Unauthorized:
                bot_blocked(update.effective_message.chat.id)
        except AttributeError:
            try:
                reply = getattr(update.callback_query.message, 'reply_text')
                if markdown:
                    reply = getattr(update.callback_query.message,
                                    'reply_markdown')
                try:
                    reply(msg, quote=quote,
                          reply_markup=reply_markup)
                except Unauthorized:
                    bot_blocked(update.effective_message.chat.id)
            except AttributeError:
                print(f"Error: send_message({update})")


def send_message_bot(bot, uid, msg, reply_markup=None):
    if bot is not None:
        try:
            bot.send_message(chat_id=uid,
                             text=msg,
                             parse_mode=ParseMode.MARKDOWN,
                             reply_markup=reply_markup)
        except Unauthorized:
            bot_blocked(uid)


def edit_message(update, msg, reply_markup):
    try:
        update.callback_query.edit_message_text(
            msg, reply_markup=reply_markup)
    except BadRequest:
        pass


def start(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            state(uid)
            if not util.user_exists(uid):
                util.user_add(uid)
            send_message(update,
                         ("Hi, traveler.\n\n"
                          "ℹ️ Check /help for a list of commands."))


def refill(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        msg = "Tell me your current resin value."

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                if context.args:
                    if len(context.args) < 2:
                        msg = ("Incorrect number of parameters. "
                               "Use /refill <value> <mm:ss>")
                        util.strikes_inc(uid)
                    else:
                        rarg = context.args[0]
                        targ = context.args[1]

                        try:
                            resin = int(rarg)
                        except ValueError:
                            msg = (f"{rarg} te nandayo! "
                                   f"You must give a number "
                                   f"lower than {util.RESIN_MAX}!")
                            util.strikes_inc(uid)
                        else:
                            if resin < 0:
                                msg = "Resin value must be positive!"
                                util.strikes_inc(uid)
                            elif resin >= util.RESIN_MAX:
                                msg = (f"You can't have more "
                                       f"than {util.RESIN_MAX} resin!")
                                util.strikes_inc(uid)
                            else:
                                msg = "Perfect. I'm tracking your resin."
                                fmt = "%M:%S"
                                try:
                                    datetime_obj = datetime.strptime(targ, fmt)
                                except ValueError:
                                    msg = (f"{targ} te nandayo! "
                                           f"You must use the format mm:ss!")
                                    util.strikes_inc(uid)
                                else:
                                    seconds = (
                                        int(datetime_obj.strftime('%M')) * 60
                                        + int(datetime_obj.strftime('%S')))

                                    if seconds:
                                        if uid in threads:
                                            threads[uid][0].set()
                                            del threads[uid]

                                        util.resin_set(uid, resin)

                                        resin_flag = Event()
                                        resin_thread = util.ResinThread(
                                            resin_flag,
                                            uid,
                                            seconds,
                                            context)
                                        threads[uid] = (resin_flag,
                                                        resin_thread)
                                        resin_thread.start()
                                    else:
                                        if uid in threads:
                                            cresin = util.resin(uid)
                                            if resin + cresin > util.RESIN_MAX:
                                                msg = (f"You can't refill "
                                                       f"more than "
                                                       f"{util.RESIN_MAX - cresin} resin!") # noqa
                                                util.strikes_inc(uid)
                                            else:
                                                util.resin_set(uid,
                                                               cresin + resin)
                                                msg = "I've updated your resin."
                                        else:
                                            msg = "You don't have tracking active!"

                                    clean_state(uid)

                                    util.strikes_dec(uid)

                else:
                    set_state(uid, 'refill')

                send_message(update, msg)


def spend(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        msg = "How many resin do you want to spend?"

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                if context.args:
                    rarg = context.args[0]

                    cur_resin = util.resin(uid)
                    try:
                        resin = int(rarg)
                    except ValueError:
                        msg = (f"{rarg} te nandayo! "
                               f"You must give a number "
                               f"lower than {util.RESIN_MAX}!")
                        util.strikes_inc(uid)
                    else:
                        if resin < 0:
                            msg = "You can't spend negative values of resin!"
                            util.strikes_inc(uid)
                        elif resin > cur_resin:
                            msg = (f"You can't spend more "
                                   f"than {cur_resin} resin!")
                            util.strikes_inc(uid)
                        else:
                            util.resin_dec(uid, resin)

                            if uid not in threads or (
                                    uid in threads and
                                    not threads[uid][1].is_alive()):
                                seconds = util.RESIN_REGEN_MIN * 60
                                resin_flag = Event()
                                resin_thread = util.ResinThread(resin_flag,
                                                                uid,
                                                                seconds,
                                                                context)
                                threads[uid] = (resin_flag, resin_thread)
                                resin_thread.start()

                            clean_state(uid)
                            cur_resin = util.resin(uid)
                            msg = f"I have updated your resin to {cur_resin}."
                            util.strikes_dec(uid)
                else:
                    set_state(uid, 'spend')

                send_message(update, msg)


def warn(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        msg = (f"Notification threshold can't be "
               f"higher than {util.RESIN_MAX} resin!")

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                if context.args:
                    warn_arg = context.args[0]

                    try:
                        twarn = int(warn_arg)
                    except ValueError:
                        msg = (f"{warn_arg} te nandayo! "
                               f"You must give a number "
                               f"lower than {util.RESIN_MAX}!")
                        util.strikes_inc(uid)
                    else:
                        if twarn < 0:
                            msg = "Notification threshold can't be negative!"
                            util.strikes_inc(uid)
                        elif twarn <= util.RESIN_MAX:
                            util.warn_threshold_set(uid, twarn)

                            clean_state(uid)
                            msg = (f"I've' updated your "
                                   f"warning threshold to {twarn} resin.")
                            util.strikes_dec(uid)
                else:
                    set_state(uid, 'twarn')
                    msg = "Tell me your new notification threshold."

                send_message(update, msg)


def myresin(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                clean_state(uid)
                resin = util.resin(uid)

                send_message(update,
                             f"You currently have {resin} resin.")


def maxresin(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                clean_state(uid)
                (hc_hour, hc_min), (sc_hour, sc_min) = util.resin_max(uid)

                if hc_hour == 0 and hc_min == 0:
                    msg = "You hit the resin cap. Hurry up!"

                else:
                    twarn = util.warn(uid)
                    rmax = util.RESIN_MAX
                    if util.timezone(uid):
                        tz = util.timezone_local(uid)
                        hhour, hmin = calc_approx_hour(tz, hc_hour, hc_min)
                        shour, smin = calc_approx_hour(tz, sc_hour, sc_min)
                        msg = (f"Your resin will reach the softcap ({twarn}) "
                               f"in {sc_hour}h{sc_min}m "
                               f"approx. at {shour:02}:{smin:02}h.\n"
                               f"Your resin will reach the cap ({rmax}) in "
                               f"{hc_hour}h{hc_min}m "
                               f"approx. at {hhour:02}:{hmin:02}h.")
                    else:
                        msg = (f"Your resin will reach the softcap ({twarn}) "
                               f"in {sc_hour:02}h{sc_min:02}m.\n"
                               f"Your resin will reach the cap ({rmax}) in "
                               f"{hc_hour:02} hours and {hc_min:02} minutes.")

                send_message(update, msg)


def timezone(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        msg = "Tell me your current hour. Use 24h format: hh:mm."

        if not util.user_banned(uid):
            if not util.user_exists(uid):
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
                        util.strikes_inc(uid)
                    else:
                        local_hour = datetime.strftime(datetime.now(), '%H')
                        user_hour = user_time.strftime('%H')
                        tz = int(user_hour) - int(local_hour)
                        clean_state(uid)
                        util.timezone_local_set(uid, tz)
                        msg = ("I have updated your timezone. "
                               "Command /maxresin "
                               "will show an estimated hour "
                               "when you'll hit the resin cap.")
                        util.strikes_dec(uid)
                else:
                    set_state(uid, 'timezone')

                send_message(update, msg)


def mytimezone(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                clean_state(uid)

                if util.timezone(uid):
                    tz = util.timezone_local(uid)
                    user_hour = (int(datetime.strftime(datetime.now(), '%H'))
                                 + tz) % 24
                    local_min = int(datetime.strftime(datetime.now(), '%M'))
                    msg = (f"Your current time is {user_hour:02}:{local_min:02} "
                           f"({'+' if tz > 0 else ''}{tz}).")
                else:
                    msg = ("You haven't set your timezone. "
                           "Command /maxresin will show only "
                           "the remaining time before you hit the resin cap.")

                send_message(update, msg)


def mywarn(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                clean_state(uid)
                twarn = util.warn(uid)

                send_message(update,
                             (f"Your current notification threshold "
                              f"is {twarn} resin."))


def notrack(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                clean_state(uid)
                msg = "Resin tracker isn't active."

                if uid in threads:
                    threads[uid][0].set()
                    del threads[uid]
                    msg = "I have stopped your resin tracker."

                send_message(update, msg)


def bothelp(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            send_message(update,
                         ("➡ /start Set up your information. "
                          "Mandatory to interact with the bot.\n"

                          "➡ /refill Change your current resin value. "
                          "Use it alone or passing value and time as parameters, "
                          "e.g. /refill, /refill 50 02:10 or /refill 50 00:00.\n"

                          "➡ /spend Spend your resin. "
                          "Use it alone or passing value as parameter, "
                          "e.g. /spend or /spend 80.\n"

                          "➡ /myresin Show your current resin value.\n"

                          "➡ /maxresin Show an estimation when you'll hit "
                          "the resin cap. To show an estimated hour, "
                          "set your timezone with /timezone command.\n"

                          "➡ /twarn Change your notification threshold. "
                          "Use it alone or passing value as parameter. "
                          "e.g. /twarn or /twarn 100.\n"

                          "➡ /mywarn Show your current notification threshold.\n"

                          "➡ /timezone Set your timezone to show an "
                          "estimated hour with /maxresin command. "
                          "Use it alone or passing hour as parameter, e.g. "
                          "/timezone or /timezone 17:45.\n"

                          "➡ /mytimezone Show your personalized timezone.\n"

                          "➡ /notrack Stop resin tracking.\n"

                          "➡ /notifycodes Enable automatic notifications "
                          "when new promo code is active.\n"

                          "➡ /activecodes List current active promo codes.\n"

                          "➡ /help Show bot usage.\n"

                          "➡ /cancel Cancel any pending operation.\n"

                          "➡ /stop Delete your information from bot database.\n"))


def cancel(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                clean_state(uid)
                send_message(update, "Current command cancelled.")


def stop(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        msg = "I don't have information about you."

        if not util.user_banned(uid):
            if util.user_exists(uid):
                bot_blocked(uid)
                msg = "I have deleted your information from my database."

            send_message(update, msg)


def announce(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        with open('.adminid', 'r') as ai:
            admin_id = ai.read().strip()

        if int(uid) == int(admin_id):
            msg = "‼ *Announcement:* " + " ".join(context.args) + " ‼"
            users = util.users()
            for user, in users:
                send_message_bot(context.bot, user, msg)


def text(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        txt = update.message.text

        msg = ("Bot restarted and lost all trackings. "
               "Please, refill your resin.")

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                if txt.startswith('/'):
                    msg = warn_user(uid, 'cmd')
                else:
                    if uid in user_state:
                        if user_state[uid] == 'refill':
                            try:
                                resin = int(txt)
                            except ValueError:
                                msg = (f"{txt} te nandayo! "
                                       f"You must give a number "
                                       f"lower than {util.RESIN_MAX}!")
                                util.strikes_inc(uid)
                            else:
                                if resin < 0:
                                    msg = ("You can't have negative "
                                           "values of resin!")
                                    util.strikes_inc(uid)
                                elif resin >= util.RESIN_MAX:
                                    msg = (f"You can't have more "
                                           f"than {util.RESIN_MAX} resin!")
                                    util.strikes_inc(uid)
                                else:
                                    tmp_resin[uid] = resin

                                    user_state[uid] = 'timer'
                                    msg = ("Now tell me the time "
                                           "until you get your next resin. "
                                           "Use the format mm:ss.")
                        elif user_state[uid] == 'timer':
                            fmt = "%M:%S"
                            try:
                                datetime_obj = datetime.strptime(txt, fmt)
                            except ValueError:
                                msg = (f"{txt} te nandayo! "
                                       f"You must use the format mm:ss!")
                                util.strikes_inc(uid)
                            else:
                                seconds = (int(datetime_obj.strftime('%M')) * 60
                                           + int(datetime_obj.strftime('%S')))

                                if seconds:
                                    if uid in threads:
                                        threads[uid][0].set()
                                        del threads[uid]

                                    if uid in tmp_resin:
                                        util.resin_set(uid, tmp_resin[uid])
                                        del tmp_resin[uid]

                                        resin_flag = Event()
                                        resin_thread = util.ResinThread(resin_flag,
                                                                        uid,
                                                                        seconds,
                                                                        context)
                                        threads[uid] = (resin_flag, resin_thread)
                                        resin_thread.start()

                                        msg = "Perfect. I'm tracking your resin."
                                        util.strikes_dec(uid)
                                    else:
                                        msg = ("Error happened processing "
                                               "your request. "
                                               "Start refill process again.")
                                else:
                                    if uid in threads:
                                        if uid in tmp_resin:
                                            cresin = util.resin(uid)
                                            util.resin_set(uid, cresin + tmp_resin[uid])
                                            msg = "Perfect. I've updated your resin."
                                            del tmp_resin[uid]
                                            util.strikes_dec(uid)
                                    else:
                                        msg = "You don't have tracking active!"
                        elif user_state[uid] == 'twarn':
                            try:
                                twarn = int(txt)
                            except ValueError:
                                msg = (f"{txt} te nandayo! "
                                       f"You must give a number "
                                       f"lower than {util.RESIN_MAX}!")
                                util.strikes_inc(uid)
                            else:
                                if twarn < 0:
                                    msg = ("Notification threshold "
                                           "can't be negative!")
                                    util.strikes_inc(uid)
                                elif twarn > util.RESIN_MAX:
                                    msg = (f"Notification threshold can't be "
                                           f"higher than {util.RESIN_MAX} resin!")
                                    util.strikes_inc(uid)

                                else:
                                    util.warn_threshold_set(uid, twarn)
                                    msg = (f"I have updated your "
                                           f"notifications to {twarn} resin.")
                                    util.strikes_dec(uid)
                        elif user_state[uid] == 'spend':
                            try:
                                resin = int(txt)
                            except ValueError:
                                msg = (f"{txt} te nandayo! "
                                       f"You must give a number "
                                       f"lower than {util.RESIN_MAX}!")
                                util.strikes_inc(uid)
                            else:
                                cur_resin = util.resin(uid)
                                if resin < 0:
                                    msg = ("You can't spend "
                                           "negative values of resin!")
                                    util.strikes_inc(uid)
                                elif resin > cur_resin:
                                    msg = (f"You can't spend more "
                                           f"than {cur_resin} resin!")
                                    util.strikes_inc(uid)
                                else:
                                    util.resin_dec(uid, resin)

                                    if uid not in threads or (
                                            uid in threads and
                                            not threads[uid][1].is_alive()):
                                        seconds = 8 * 60
                                        resin_flag = Event()
                                        resin_thread = util.ResinThread(
                                            resin_flag,
                                            uid,
                                            seconds,
                                            context)
                                        threads[uid] = (resin_flag,
                                                        resin_thread)
                                        resin_thread.start()

                                    cur_resin = util.resin(uid)

                                    msg = (f"I have updated your "
                                           f"resin to {cur_resin}.")
                                    util.strikes_dec(uid)
                        elif user_state[uid] == 'timezone':
                            fmt = "%H:%M"
                            try:
                                user_time = datetime.strptime(txt, fmt)
                            except ValueError:
                                msg = (f"{txt} te nandayo! "
                                       f"You must use the format hh:mm!")
                                util.strikes_inc(uid)
                            else:
                                local_hour = datetime.strftime(
                                    datetime.now(),
                                    '%H')
                                user_hour = user_time.strftime('%H')
                                tz = int(user_hour) - int(local_hour)
                                clean_state(uid)
                                util.timezone_local_set(uid, tz)
                                msg = ("I have updated your timezone. "
                                       "Command /maxresin "
                                       "will show an estimated hour "
                                       "when you'll hit the resin cap.")
                                util.strikes_dec(uid)
                        else:
                            msg = warn_user(uid, 'help')
                    else:
                        msg = warn_user(uid, 'restart')
                send_message(update, msg)


def notify_restart(bupdater):
    if bupdater is not None:
        msg = "⚠ Bot restarted. Please, refill"
        for user, in util.users():
            send_message_bot(bupdater.bot, user, msg)


def notify_promo_codes(bupdater):
    if bupdater is not None:
        if util.codes_unnotified_exists():
            keyboard = [
                [
                    InlineKeyboardButton("Rewards", callback_data='rew'),
                    InlineKeyboardButton("EU", callback_data='eu'),
                    InlineKeyboardButton("NA", callback_data='na'),
                    InlineKeyboardButton("SEA", callback_data='sea')
                ],
                [InlineKeyboardButton("Redeem", callback_data='redeem')],
            ]

            for idx, code in enumerate(util.codes_unnotified()):
                eu_code, na_code, sea_code, rewards = code
                keyboard.insert(
                    len(keyboard) - 1,
                    [InlineKeyboardButton(f"{rewards}",
                                          callback_data=f'Rewards: {rewards}'),
                     InlineKeyboardButton(f"{eu_code}",
                                          callback_data=f'EU Code: {eu_code}'),
                     InlineKeyboardButton(f"{na_code}",
                                          callback_data=f'NA Code: {na_code}'),
                     InlineKeyboardButton(f"{sea_code}",
                                          callback_data=f'SEA Code: {sea_code}')])
                util.code_notify(eu_code)

            reply_markup = InlineKeyboardMarkup(keyboard)

            users = util.users()

            for user, in users:
                if util.codes_notify(user):
                    send_message_bot(bupdater.bot, user,
                                     ("🎁 *Hurry up! "
                                      "New promo code(s) active* 🎁"),
                                     reply_markup=reply_markup)


def active_codes(update, context):
    if update is not None:
        keyboard = [
            [
                InlineKeyboardButton("Rewards", callback_data='rew'),
                InlineKeyboardButton("EU", callback_data='eu'),
                InlineKeyboardButton("NA", callback_data='na'),
                InlineKeyboardButton("SEA", callback_data='sea')
            ],
            [InlineKeyboardButton("Redeem", callback_data='redeem')],
        ]

        for idx, code in enumerate(util.codes_unexpired()):
            eu_code, na_code, sea_code, rewards = code
            keyboard.insert(
                len(keyboard) - 1,
                [InlineKeyboardButton(f"{rewards}",
                                      callback_data=f'code=Rewards: {rewards}'),
                 InlineKeyboardButton(f"{eu_code}",
                                      callback_data=f'code=EU Code: {eu_code}'),
                 InlineKeyboardButton(f"{na_code}",
                                      callback_data=f'code=NA Code: {na_code}'),
                 InlineKeyboardButton(f"{sea_code}",
                                      callback_data=f'code=SEA Code: {sea_code}')])

        reply_markup = InlineKeyboardMarkup(keyboard)

        send_message(update,
                     "🎁 *Promo code(s) active* 🎁",
                     reply_markup=reply_markup,
                     markdown=True)


def switch_notify_codes(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        allowed = util.codes_notify(uid)
        keyboard = [
            [
                InlineKeyboardButton(f"Notify new codes: "
                                     f"{'Yes' if allowed else 'No'}",
                                     callback_data='allow_codes'),
             ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        send_message(update,
                     "Allow new promo code notifications",
                     reply_markup=reply_markup)


def calc_approx_hour(tz, hh, mm):
    user_hour = (int(datetime.strftime(datetime.now(), '%H'))
                 + tz) % 24
    local_min = int(datetime.strftime(datetime.now(), '%M'))
    approx_min = (local_min + mm) % 60
    carry_hour = (local_min + mm) // 60
    approx_hour = (user_hour + hh + carry_hour) % 24
    return approx_hour, approx_min


def resin_cap(uid):
    (hc_hour, hc_min), (sc_hour, sc_min) = util.resin_max(uid)
    if util.timezone(uid):
        tz = util.timezone_local(uid)
        hhour, hmin = calc_approx_hour(tz, hc_hour, hc_min)
        shour, smin = calc_approx_hour(tz, sc_hour, sc_min)
        return (hc_hour, hc_min, hhour, hmin), (sc_hour, sc_min, shour, smin)
    else:
        return (hc_hour, hc_min, None, None), (sc_hour, sc_min, None, None)


def main_menu(update):
    keyboard = [[InlineKeyboardButton("🌙 Resin 🌙",
                                      callback_data='resin_menu')],
                [InlineKeyboardButton("🎁 Promotion Codes 🎁",
                                      callback_data='codes_menu')],
                [InlineKeyboardButton("⚙️ Settings ⚙️",
                                      callback_data='settings_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "What do you want to do?", reply_markup=reply_markup)


def resin_menu(update):
    uid = update.effective_message.chat.id
    cresin = util.resin(uid)
    (hc_hour, hc_min, hhour, hmin), (sc_hour, sc_min, shour, smin) = resin_cap(uid)
    tracking = '🟢' if uid in threads else '🔴'
    keyboard = [[InlineKeyboardButton(f"🌙 {cresin} 🌙",
                                      callback_data='resin_menu'),
                 InlineKeyboardButton(f"Tracking: {tracking}",
                                      callback_data='tracking_menu')],
                [InlineKeyboardButton(f"{sc_hour}h{sc_min}m ~> "
                                      f"{shour:02}:{smin:02}h ({warn})",
                                      callback_data='resin_menu'),
                 InlineKeyboardButton(f"{hc_hour}h{hc_min}m ~> "
                                      f"{hhour:02}:{hmin:02}h ({util.RESIN_MAX})",
                                      callback_data='resin_menu')],
                [InlineKeyboardButton("Spend Resin",
                                      callback_data='spend_menu'),
                 InlineKeyboardButton("Refill Resin",
                                      callback_data='refill_menu')],
                [InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "What do you want to do?", reply_markup=reply_markup)


def tracking_menu(update):
    uid = update.effective_message.chat.id
    if uid not in user_menu_state:
        user_menu_state[uid] = {}
    if 'track' not in user_menu_state[uid]:
        user_menu_state[uid]['track'] = list(util.TRACK_MAX)
    twarn = user_menu_state[uid]['track']
    tracking = uid in threads
    trck_icon = '🟢' if tracking else '🔴'
    keyboard = [[InlineKeyboardButton(f"Tracking: {trck_icon}",
                                      callback_data='tracking_menu')],
                [InlineKeyboardButton("« Back to Resin",
                                      callback_data='resin_menu'),
                 InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    if tracking:
        keyboard.insert(1, [InlineKeyboardButton("Stop Tracking",
                                                 callback_data='tracking_stop')])
    else:
        keyboard.insert(1, [InlineKeyboardButton("˄",
                                                 callback_data='tracking_up0'),
                            InlineKeyboardButton(" ",
                                                 callback_data='nop'),
                            InlineKeyboardButton("˄",
                                                 callback_data='tracking_up1'),
                            InlineKeyboardButton("˄",
                                                 callback_data='tracking_up2')])
        keyboard.insert(2, [InlineKeyboardButton(twarn[0],
                                                 callback_data='nop'),
                            InlineKeyboardButton(":",
                                                 callback_data='nop'),
                            InlineKeyboardButton(twarn[1],
                                                 callback_data='nop'),
                            InlineKeyboardButton(twarn[2],
                                                 callback_data='nop')])
        keyboard.insert(3, [InlineKeyboardButton("˅",
                                                 callback_data='tracking_down0'),
                            InlineKeyboardButton(" ",
                                                 callback_data='nop'),
                            InlineKeyboardButton("˅",
                                                 callback_data='tracking_down1'),
                            InlineKeyboardButton("˅",
                                                 callback_data='tracking_down2')])
        keyboard.insert(4, [InlineKeyboardButton("Start Tracking",
                                                 callback_data='tracking_start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "What is your timer?", reply_markup=reply_markup)


def tracking_start(update, context):
    uid = update.effective_message.chat.id
    mm = int(update.callback_query.message.reply_markup.inline_keyboard[2][0]['text'])
    s1 = int(update.callback_query.message.reply_markup.inline_keyboard[2][2]['text'])
    s2 = int(update.callback_query.message.reply_markup.inline_keyboard[2][3]['text'])
    if uid in threads:
        threads[uid][0].set()
    resin_flag = Event()
    resin_thread = util.ResinThread(resin_flag,
                                    uid,
                                    mm*60 + s1*10 + s2,
                                    context)
    threads[uid] = (resin_flag, resin_thread)
    resin_thread.start()
    tracking_menu(update)


def tracking_stop(update):
    uid = update.effective_message.chat.id
    if uid in threads:
        threads[uid][0].set()
        del threads[uid]
    tracking_menu(update)


def tracking_updown(update, up=True):
    uid = update.effective_message.chat.id
    if uid not in user_menu_state:
        user_menu_state[uid] = {}
    if 'track' not in user_menu_state[uid]:
        user_menu_state[uid]['track'] = list(util.TRACK_MAX)
    twarn = user_menu_state[uid]['track']
    txt = 'tracking_down'
    if up:
        txt = 'tracking_up'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        if twarn[pos] < util.TRACK_MAX[pos]:
            twarn[pos] += 1
    else:
        if twarn[pos] > 0:
            twarn[pos] -= 1
    tracking_menu(update)


def spend_menu(update):
    uid = update.effective_message.chat.id
    resin = util.resin(uid)
    keyboard = [[InlineKeyboardButton(f"🌙 {resin} 🌙",
                                      callback_data='spend_menu')],
                [],
                [InlineKeyboardButton("« Back to Resin", callback_data='resin_menu'),
                 InlineKeyboardButton("« Back to Menu", callback_data='main_menu')]]
    if resin >= 10:
        keyboard[1].append(InlineKeyboardButton("10", callback_data='spend_r10'))
    else:
        keyboard[1].append(InlineKeyboardButton("No Resin Left!", callback_data='nop'))
    if resin >= 20:
        keyboard[1].append(InlineKeyboardButton("20", callback_data='spend_r20'))
    if resin >= 40:
        keyboard[1].append(InlineKeyboardButton("40", callback_data='spend_r40'))
    if resin >= 60:
        keyboard[1].append(InlineKeyboardButton("60", callback_data='spend_r60'))
    if resin >= 80:
        keyboard[1].append(InlineKeyboardButton("80", callback_data='spend_r80'))
    if resin >= 120:
        keyboard[1].append(InlineKeyboardButton("120", callback_data='spend_r120'))
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "How many resin do you want to spend?", reply_markup=reply_markup)


def spend_resin(update):
    uid = update.effective_message.chat.id
    resin = int(update.callback_query.data.split('spend_r')[1])
    util.resin_dec(uid, resin)
    spend_menu(update)


def refill_menu(update):
    uid = update.effective_message.chat.id
    resin = util.resin(uid)
    if uid not in user_menu_state:
        user_menu_state[uid] = {}
    if 'refill' not in user_menu_state[uid]:
        user_menu_state[uid]['refill'] = [0, 0, 0]
    crefill = user_menu_state[uid]['refill']
    keyboard = [[InlineKeyboardButton(f"🌙 {resin} 🌙",
                                      callback_data='refill_menu')],
                [InlineKeyboardButton("˄",
                                      callback_data='refill_up0'),
                 InlineKeyboardButton("˄",
                                      callback_data='refill_up1'),
                 InlineKeyboardButton("˄",
                                      callback_data='refill_up2')],
                [InlineKeyboardButton(crefill[0],
                                      callback_data='nop'),
                 InlineKeyboardButton(crefill[1],
                                      callback_data='nop'),
                 InlineKeyboardButton(crefill[2],
                                      callback_data='nop')],
                [InlineKeyboardButton("˅",
                                      callback_data='refill_down0'),
                 InlineKeyboardButton("˅",
                                      callback_data='refill_down1'),
                 InlineKeyboardButton("˅",
                                      callback_data='refill_down2')],
                [InlineKeyboardButton("Refill",
                                      callback_data='refill_pool')],
                [InlineKeyboardButton("« Back to Resin",
                                      callback_data='resin_menu'),
                 InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "How many resin do you want to refill?", reply_markup=reply_markup)


def refill_pool(update):
    uid = update.effective_message.chat.id
    cresin = util.resin(uid)
    r0 = update.callback_query.message.reply_markup.inline_keyboard[2][0]['text']
    r1 = update.callback_query.message.reply_markup.inline_keyboard[2][1]['text']
    r2 = update.callback_query.message.reply_markup.inline_keyboard[2][2]['text']
    crefill = int("".join([r0, r1, r2]))
    util.resin_set(uid, cresin + crefill)
    refill_menu(update)


def refill_updown(update, up=True):
    uid = update.effective_message.chat.id
    if uid not in user_menu_state:
        user_menu_state[uid] = {}
    if 'refill' not in user_menu_state[uid]:
        user_menu_state[uid]['refill'] = [0, 0, 0]
    twarn = user_menu_state[uid]['refill']
    cresin = util.resin(uid)
    txt = 'refill_up'
    if not up:
        txt = 'refill_down'
    pos = int(update.callback_query.data.split(txt)[1])
    maxv = [int(el) for el in f"{util.RESIN_MAX - cresin:03d}"]
    if up:
        twarn[pos] += 1
    else:
        twarn[pos] = twarn[pos] - 1 if twarn[pos] > 0 else 0
    if int("".join([str(c) for c in twarn])) > util.RESIN_MAX - cresin:
        user_menu_state[uid]['refill'] = maxv
    refill_menu(update)


def codes_menu(update):
    keyboard = [[InlineKeyboardButton("Rewards",
                                      callback_data='rew'),
                 InlineKeyboardButton("EU",
                                      callback_data='eu'),
                 InlineKeyboardButton("NA",
                                      callback_data='na'),
                 InlineKeyboardButton("SEA",
                                      callback_data='sea')],
                [InlineKeyboardButton("How to redeem?",
                                      callback_data='codes_redeem')],
                [InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    pre = 'codes_desc'
    for idx, code in enumerate(util.codes_unexpired()):
        eu_code, na_code, sea_code, rewards = code
        keyboard.insert(
            len(keyboard) - 2,
            [InlineKeyboardButton(f"{rewards}",
                                  callback_data=f'{pre}Rewards: {rewards}'),
             InlineKeyboardButton(f"{eu_code}",
                                  callback_data=f'{pre}EU Code: {eu_code}'),
             InlineKeyboardButton(f"{na_code}",
                                  callback_data=f'{pre}NA Code: {na_code}'),
             InlineKeyboardButton(f"{sea_code}",
                                  callback_data=f'{pre}SEA Code: {sea_code}')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "Active promotion codes", reply_markup=reply_markup)


def code_menu(update, code):
    keyboard = [[InlineKeyboardButton("« Back to Active Codes",
                                      callback_data='codes_menu'),
                 InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    edit_message(update, code, reply_markup=reply_markup)


def redeem_menu(update):
    keyboard = [[InlineKeyboardButton("« Back to Active Codes",
                                      callback_data='codes_menu'),
                 InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    edit_message(update,
                 ("Codes can be redeemed in website or in-game:\n"
                  "Website: https://genshin.mihoyo.com/en/gift\n"
                  "In-game: Settings - Account - Redeem code."),
                 reply_markup=reply_markup)


def settings_menu(update):
    keyboard = [[InlineKeyboardButton("⏰ Resin Warnings ⏰",
                                      callback_data='settings_warn_menu')],
                [InlineKeyboardButton("📣 Promotion Code Notifications 📣",
                                      callback_data='settings_promo_menu')],
                [InlineKeyboardButton("🌎 Local Time Zone 🌎",
                                      callback_data='settings_timezone_menu')],
                [InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "What do you want to change?", reply_markup=reply_markup)


def settings_warn_menu(update):
    uid = update.effective_message.chat.id
    twarn = util.warn_threshold(uid)
    if uid not in user_menu_state:
        user_menu_state[uid] = {}
    if 'warn' not in user_menu_state[uid]:
        user_menu_state[uid]['warn'] = [int(cw) for cw in f"{twarn:03d}"]
    twarn = user_menu_state[uid]['warn']
    iwarn = '🔔' if util.warn_allowed(uid) else '🔕'
    keyboard = [[InlineKeyboardButton(f"Threshold: {twarn}",
                                      callback_data='nop'),
                 InlineKeyboardButton(f"Status: {iwarn}",
                                      callback_data='warn_toggle')],
                [InlineKeyboardButton("˄",
                                      callback_data='warn_up0'),
                 InlineKeyboardButton("˄",
                                      callback_data='warn_up1'),
                 InlineKeyboardButton("˄",
                                      callback_data='warn_up2')],
                [InlineKeyboardButton(twarn[0],
                                      callback_data='nop'),
                 InlineKeyboardButton(twarn[1],
                                      callback_data='nop'),
                 InlineKeyboardButton(twarn[2],
                                      callback_data='nop')],
                [InlineKeyboardButton("˅",
                                      callback_data='warn_down0'),
                 InlineKeyboardButton("˅",
                                      callback_data='warn_down1'),
                 InlineKeyboardButton("˅",
                                      callback_data='warn_down2')],
                [InlineKeyboardButton("Set Warning Threshold",
                                      callback_data='warn_threshold')],
                [InlineKeyboardButton("« Back to Settings",
                                      callback_data='settings_menu'),
                 InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "When should I warn you?", reply_markup=reply_markup)


def warn_toggle(update):
    uid = update.effective_message.chat.id
    util.warn_toggle(uid)
    settings_warn_menu(update)


def warn_threshold(update):
    uid = update.effective_message.chat.id
    r0 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][0]['text'])
    r1 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][1]['text'])
    r2 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][2]['text'])
    twarn = int("".join([r0, r1, r2]))
    util.warn_threshold_set(uid, twarn)
    settings_warn_menu(update)


def warn_updown(update, up=True):
    uid = update.effective_message.chat.id
    if uid not in user_menu_state:
        user_menu_state[uid] = {}
    if 'warn' not in user_menu_state[uid]:
        user_menu_state[uid]['warn'] = [int(cw)
                                        for cw
                                        in f"{util.warn_threshold(uid):03d}"]
    twarn = user_menu_state[uid]['warn']
    txt = 'warn_down'
    if up:
        txt = 'warn_up'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        if twarn[pos] < util.WARN_MAX[pos]:
            twarn[pos] += 1
    else:
        if twarn[pos] > 0:
            twarn[pos] -= 1
    settings_warn_menu(update)


def settings_promo_menu(update):
    uid = update.effective_message.chat.id
    ipromo = '🔔' if util.codes_notify_allowed(uid) else '🔕'
    keyboard = [[InlineKeyboardButton(f"Status: {ipromo}",
                                      callback_data='promo_toggle')],
                [InlineKeyboardButton("« Back to Settings",
                                      callback_data='settings_menu'),
                 InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "Do you want to be notified when a promotion code became active?", reply_markup=reply_markup)


def promo_toggle(update):
    uid = update.effective_message.chat.id
    util.codes_notify_toggle(uid)
    settings_promo_menu(update)


def settings_timezone_menu(update):
    uid = update.effective_message.chat.id
    ipromo = '🔔' if util.codes_notify_allowed(uid) else '🔕'
    keyboard = [[InlineKeyboardButton(f"Status: {ipromo}",
                                      callback_data='promo_toggle')],
                [InlineKeyboardButton("« Back to Settings",
                                      callback_data='settings_menu'),
                 InlineKeyboardButton("« Back to Menu",
                                      callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "Do you want to be notified when a promotion code became active?", reply_markup=reply_markup)


def timezone_menu(update):
    pass


def timezone_updown(update, up=True):
    pass


def timezone_toggle(update):
    pass


def button(update, context):
    if update is not None:
        query = update.callback_query
        # pprint(update.to_dict())
        query.answer()

        if query.data == 'main_menu':
            main_menu(update)
        elif query.data == 'resin_menu':
            query.answer(text="test")
            resin_menu(update)
        elif query.data == 'tracking_menu':
            tracking_menu(update)
        elif query.data == 'tracking_start':
            tracking_start(update, context)
        elif query.data == 'tracking_stop':
            tracking_stop(update)
        elif query.data.startswith('tracking_up'):
            tracking_updown(update)
        elif query.data.startswith('tracking_down'):
            tracking_updown(update, up=False)
        elif query.data == 'spend_menu':
            spend_menu(update)
        elif query.data.startswith('spend_r'):
            spend_resin(update)
        elif query.data == 'refill_menu':
            refill_menu(update)
        elif query.data.startswith('refill_up'):
            refill_updown(update)
        elif query.data.startswith('refill_down'):
            refill_updown(update, up=False)
        elif query.data == 'refill_pool':
            refill_pool(update)
        elif query.data == 'codes_menu':
            codes_menu(update)
        elif query.data.startswith('codes_desc'):
            code_menu(update, query.data.split('codes_desc')[1])
        elif query.data == 'codes_redeem':
            redeem_menu(update)
        elif query.data == 'settings_menu':
            settings_menu(update)
        elif query.data == 'settings_warn_menu':
            settings_warn_menu(update)
        elif query.data == 'warn_toggle':
            warn_toggle(update)
        elif query.data == 'warn_threshold':
            warn_threshold(update)
        elif query.data.startswith('warn_up'):
            warn_updown(update)
        elif query.data.startswith('warn_down'):
            warn_updown(update, up=False)
        elif query.data == 'settings_promo_menu':
            settings_promo_menu(update)
        elif query.data == 'promo_toggle':
            promo_toggle(update)
        elif query.data == 'settings_timezone_menu':
            settings_timezone_menu(update)


def menu(update, context):
    main_menu(update)


if __name__ == '__main__':
    logging.basicConfig(format=('%(asctime)s - %(name)s - '
                                '%(levelname)s - %(message)s'),
                        level=logging.INFO)
    with open(".apikey", 'r') as ak:
        API_KEY = ak.read().strip()
    util.set_up_db()

    updater = Updater(token=API_KEY, use_context=True)
    dispatcher = updater.dispatcher

    # promo_code_flag = Event()
    # promo_codes_thread = util.PromoCodeThread(promo_code_flag, updater)
    # promo_codes_thread.start()
    print("Promo codes thread disabled!")

    start_handler = CommandHandler('start', start,
                                   filters=~Filters.update.edited_message)
    dispatcher.add_handler(start_handler)
    refill_handler = CommandHandler('refill', refill,
                                    filters=~Filters.update.edited_message)
    dispatcher.add_handler(refill_handler)
    spend_handler = CommandHandler('spend', spend,
                                   filters=~Filters.update.edited_message)
    dispatcher.add_handler(spend_handler)
    warn_handler = CommandHandler('warn', warn,
                                  filters=~Filters.update.edited_message)
    dispatcher.add_handler(warn_handler)
    myresin_handler = CommandHandler('myresin', myresin,
                                     filters=~Filters.update.edited_message)
    dispatcher.add_handler(myresin_handler)
    maxresin_handler = CommandHandler('maxresin', maxresin,
                                      filters=~Filters.update.edited_message)
    dispatcher.add_handler(maxresin_handler)
    timezone_handler = CommandHandler('timezone', timezone,
                                      filters=~Filters.update.edited_message)
    dispatcher.add_handler(timezone_handler)
    mytimezone_handler = CommandHandler('mytimezone', mytimezone,
                                        filters=~Filters.update.edited_message)
    dispatcher.add_handler(mytimezone_handler)
    mywarn_handler = CommandHandler('mywarn', mywarn,
                                    filters=~Filters.update.edited_message)
    dispatcher.add_handler(mywarn_handler)
    notrack_handler = CommandHandler('notrack', notrack,
                                     filters=~Filters.update.edited_message)
    dispatcher.add_handler(notrack_handler)
    activecodes_handler = CommandHandler('activecodes', active_codes,
                                         filters=~Filters.update.edited_message)
    dispatcher.add_handler(activecodes_handler)
    dispatcher.add_handler(CallbackQueryHandler(button))
    notifycodes_handler = CommandHandler('notifycodes', switch_notify_codes,
                                         filters=~Filters.update.edited_message)
    dispatcher.add_handler(notifycodes_handler)
    help_handler = CommandHandler('help', bothelp,
                                  filters=~Filters.update.edited_message)
    dispatcher.add_handler(help_handler)
    cancel_handler = CommandHandler('cancel', cancel,
                                    filters=~Filters.update.edited_message)
    dispatcher.add_handler(cancel_handler)
    stop_handler = CommandHandler('stop', stop,
                                  filters=~Filters.update.edited_message)
    dispatcher.add_handler(stop_handler)
    announce_handler = CommandHandler('announce', announce,
                                      filters=~Filters.update.edited_message)
    dispatcher.add_handler(announce_handler)
    menu_handler = CommandHandler('menu', menu,
                                  filters=~Filters.update.edited_message)
    dispatcher.add_handler(menu_handler)
    text_handler = MessageHandler(Filters.text & ~Filters.update.edited_message, text)
    dispatcher.add_handler(text_handler)

    notify_restart(updater)

    updater.start_polling()
    updater.idle()
