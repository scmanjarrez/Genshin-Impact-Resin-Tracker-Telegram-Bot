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
user_state_menu = {}
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
    util.strikes_inc(uid)
    msg = ["ℹ️ Send /help for a list of commands.\n\n",
           "⛔ Don't flood the bot or you will be banned ⛔"]
    if reason == 'cmd':
        msg.insert(0, "🚫 Unknown command 🚫\n\n")
    elif reason == 'restarted':
        msg.insert(0, "❌ Bot restarted and lost all trackings ❌\n\n")
    cstrikes = util.strikes(uid)
    if cstrikes >= util.STRIKE_BAN:
        msg = "⛔ You've been banned for spam/flooding ⛔"
        util.user_ban(uid)
    return "".join(msg)


def warn_not_started(update):
    send_message(update, "Send /start before continuing.")


def send_message(update, msg, quote=True, reply_markup=None, markdown=False, html=False):
    if update is not None:
        if markdown:
            reply = getattr(update.message, 'reply_markdown_v2')
        elif html:
            reply = getattr(update.message, 'reply_html')
        else:
            reply = getattr(update.message, 'reply_text')
        try:
            reply(msg, quote=quote, reply_markup=reply_markup)
        except Unauthorized:
            bot_blocked(update.effective_message.chat.id)


def send_message_bot(bot, uid, msg, reply_markup=None, markdown=False):
    if bot is not None:
        parse = None
        if markdown:
            parse = ParseMode.MARKDOWN
        try:
            bot.send_message(chat_id=uid, text=msg, parse_mode=parse,
                             reply_markup=reply_markup)
        except Unauthorized:
            bot_blocked(uid)


def edit_message(update, msg, reply_markup):
    try:
        update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
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
                         "Welcome, traveler.\n"
                         "ℹ️ Send /help for a list of commands.")


def help(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            send_message(update,
                         ("I can help you manage your resin.\n\n"

                          "You can control me by sendings these commands:\n\n"

                          "Arguments inside brackets are optional\n\n"

                          "❔ /menu. Interact with the bot buttons-only. "
                          "<b>[beta]</b>\n\n"

                          "<b>Manage Resin</b>\n"
                          "❔ /resin <code>[#]</code>. Show your current resin "
                          "and time remaining to cap. "
                          "If argument, list time remaining to reach "
                          "the amount.\n"
                          "❔ /spend <code>[#]</code>. Spend your resin.\n"
                          "❔ /refill <code>[#]</code>. Increase your resin.\n"
                          "❔ /track <code>[mm:ss]</code>. Synchronize your "
                          "in-game timer.\n\n"

                          "<b>Notifications Settings</b>\n"
                          "❔ /resinwarn <code>[#]</code>. Set your resin "
                          "warning threshold.\n"
                          "❔ /timezone <code>[mm:ss]</code>. Synchronize your "
                          "hour.\n"
                          "❔ /codenotify. Toggle promotion "
                          "codes notifications.\n"
                          "❔ /codeactive. List active promotion codes.\n\n"

                          "<b>Bot Usage</b>\n"
                          "❔ /help. List of commands.\n"
                          "❔ /cancel. Cancel active action.\n"
                          "❔ /stop. Delete your information from bot.\n"),
                         html=True)


def resin_cap_format(hcinfo, scinfo, cwarn):
    hc_hour, hc_min, hhour, hmin = hcinfo
    sc_hour, sc_min, shour, smin = scinfo
    hc = f"{hc_hour}h{hc_min}m ({util.RESIN_MAX})"
    sc = f"{sc_hour}h{sc_min}m ({cwarn})"
    if hhour is not None:
        hc = f"{hc_hour}h{hc_min}m ~> {hhour:02}:{hmin:02}h ({util.RESIN_MAX})"
        sc = f"{sc_hour}h{sc_min}m ~> {shour:02}:{smin:02}h ({cwarn})"
    return hc, sc


def update_resin_ui(update, context, send=False, tmp_cap=None):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                cresin = util.resin(uid)
                cwarn = (util.warn_threshold(uid)
                         if tmp_cap is None else tmp_cap)
                hcinfo, scinfo = resin_cap(uid, tmp_cap)
                hc, sc = resin_cap_format(hcinfo, scinfo, cwarn)
                keyboard = [
                    [InlineKeyboardButton(f"🌙 {cresin} 🌙",
                                          callback_data='nop')],
                    [InlineKeyboardButton(sc,
                                          callback_data='nop'),
                     InlineKeyboardButton(hc,
                                          callback_data='nop')],
                    [InlineKeyboardButton("↻ Update ↻",
                                          callback_data='update_resin_ui')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                msg = "You resin information:"
                if send:
                    send_message(update, msg, reply_markup=reply_markup)
                else:
                    edit_message(update, msg, reply_markup=reply_markup)


def resin(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                cresin = util.resin(uid)
                msg = (f"Invalid input. Must be a number greater than "
                       f"{cresin} and lower than {util.RESIN_MAX}.")
                reply_markup = None
                tmp_cap = None
                error = False
                if context.args:
                    error = True
                    arg_resin = context.args[0]
                    if arg_resin.isdigit():
                        arg_resin = int(arg_resin)
                        if arg_resin > cresin and arg_resin < util.RESIN_MAX:
                            error = False
                            tmp_cap = int(arg_resin)
                if not error:
                    update_resin_ui(update, context, send=True, tmp_cap=tmp_cap)
                else:
                    send_message(update, msg, reply_markup=reply_markup)


def update_spend_ui(update, context, send=False):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                cresin = util.resin(uid)
                cwarn = (util.warn_threshold(uid)
                         if tmp_cap is None else tmp_cap)
                hcinfo, scinfo = resin_cap(uid, tmp_cap)
                hc, sc = resin_cap_format(hcinfo, scinfo, cwarn)
                keyboard = [
                    [InlineKeyboardButton(f"🌙 {cresin} 🌙",
                                          callback_data='nop')],
                    [InlineKeyboardButton(sc,
                                          callback_data='nop'),
                     InlineKeyboardButton(hc,
                                          callback_data='nop')],
                    [InlineKeyboardButton("↻ Update ↻",
                                          callback_data='update_resin_ui')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                msg = "You resin information:"
                if send:
                    send_message(update, msg, reply_markup=reply_markup)
                else:
                    edit_message(update, msg, reply_markup=reply_markup)



def spend(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                pass

def track(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            msg = "Your timer has been updated."
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                if context.args:
                    targ = context.args[0]
                    try:
                        dtime = datetime.strptime(targ, "%M:%S")
                    except ValueError:
                        msg = "Invalid input. Use format MM:SS."
                        util.strikes_inc(uid)
                    else:
                        seconds = (
                            int(dtime.strftime('%M')) * 60 +
                            int(dtime.strftime('%S')))

                        if uid in threads:
                            threads[uid][0].set()
                            del threads[uid]

                        resin_flag = Event()
                        resin_thread = util.ResinThread(
                            resin_flag,
                            uid,
                            seconds,
                            context)
                        threads[uid] = (resin_flag, resin_thread)
                        resin_thread.start()
                else:
                    state(uid, 'track')
            send_message(update, msg)


def refill(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        rmax = util.RESIN_MAX
        msg = "How many resin do you have?"

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                if context.args:
                    if len(context.args) > 2:
                        msg = ("Incorrect number of parameters. "
                               "Use /refill VALUE [MM:SS]. Second parameter is optional.")
                        util.strikes_inc(uid)
                    else:
                        if len(context.args) == 1:
                            rarg = context.args[0]
                        elif len(context.args) == 2:
                            rarg = context.args[0]
                            targ = context.args[1]
                            try:
                                resin = int(rarg)
                            except ValueError:
                                msg = (f"Incorrect VALUE. "
                                       f"Must be a number lower than {rmax}. "
                                       f"Use /refill VALUE MM:SS")
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

                                        state(uid)

                                        util.strikes_dec(uid)
                        else:
                            pass
                else:
                    state(uid, 'refill')

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

                            state(uid)
                            cur_resin = util.resin(uid)
                            msg = f"I have updated your resin to {cur_resin}."
                            util.strikes_dec(uid)
                else:
                    state(uid, 'spend')

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
                        strack = int(warn_arg)
                    except ValueError:
                        msg = (f"{warn_arg} te nandayo! "
                               f"You must give a number "
                               f"lower than {util.RESIN_MAX}!")
                        util.strikes_inc(uid)
                    else:
                        if strack < 0:
                            msg = "Notification threshold can't be negative!"
                            util.strikes_inc(uid)
                        elif strack <= util.RESIN_MAX:
                            util.warn_threshold_set(uid, strack)

                            state(uid)
                            msg = (f"I've' updated your "
                                   f"warning threshold to {strack} resin.")
                            util.strikes_dec(uid)
                else:
                    state(uid, 'strack')
                    msg = "Tell me your new notification threshold."

                send_message(update, msg)


def maxresin(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                state(uid)
                (hc_hour, hc_min), (sc_hour, sc_min) = util.resin_max(uid)

                if hc_hour == 0 and hc_min == 0:
                    msg = "You hit the resin cap. Hurry up!"

                else:
                    strack = util.warn(uid)
                    rmax = util.RESIN_MAX
                    if util.timezone(uid):
                        tz = util.timezone_local(uid)
                        hhour, hmin = calc_approx_hour(tz, hc_hour, hc_min)
                        shour, smin = calc_approx_hour(tz, sc_hour, sc_min)
                        msg = (f"Your resin will reach the softcap ({strack}) "
                               f"in {sc_hour}h{sc_min}m "
                               f"approx. at {shour:02}:{smin:02}h.\n"
                               f"Your resin will reach the cap ({rmax}) in "
                               f"{hc_hour}h{hc_min}m "
                               f"approx. at {hhour:02}:{hmin:02}h.")
                    else:
                        msg = (f"Your resin will reach the softcap ({strack}) "
                               f"in {sc_hour:02}h{sc_min:02}m.\n"
                               f"Your resin will reach the cap ({rmax}) in "
                               f"{hc_hour:02} hours and {hc_min:02} minutes.")

                send_message(update, msg)


def calculate_timezone(hh):
    return int(hh) - int(datetime.strftime(datetime.now(), '%H'))


def current_hour(hh, mm):
    return datetime.datetime.strftime(
        datetime.datetime.now() - datetime.timedelta(hours=hh, minutes=mm),
        '%H:%M')


def timezone(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        msg = "What's your current hour? Use 24h format: hh:mm."
        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                if context.args:
                    hour_arg = context.args[0]
                    try:
                        user_time = datetime.strptime(hour_arg, "%H:%M")
                    except ValueError:
                        msg = "Please, use format hh:mm"
                        util.strikes_inc(uid)
                    else:
                        uhour = user_time.strftime('%H')
                        util.timezone_local_set(uid, calculate_timezone(uhour))
                        msg = ("I've updated your timezone. "
                               "Send /maxresin to check the hour you'll "
                               "hit the resin cap.")
                        util.strikes_dec(uid)
                        state(uid)
                else:
                    state(uid, 'timezone')

                send_message(update, msg)


def mytimezone(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                state(uid)

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
                state(uid)
                strack = util.warn(uid)

                send_message(update,
                             (f"Your current notification threshold "
                              f"is {strack} resin."))


def notrack(update, context):
    if update is not None:
        uid = update.effective_message.chat.id

        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                state(uid)
                msg = "Resin tracker isn't active."

                if uid in threads:
                    threads[uid][0].set()
                    del threads[uid]
                    msg = "I have stopped your resin tracker."

                send_message(update, msg)


def cancel(update, context):
    if update is not None:
        uid = update.effective_message.chat.id
        if not util.user_banned(uid):
            if not util.user_exists(uid):
                warn_not_started(update)
            else:
                state(uid)
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
                        elif user_state[uid] == 'strack':
                            try:
                                strack = int(txt)
                            except ValueError:
                                msg = (f"{txt} te nandayo! "
                                       f"You must give a number "
                                       f"lower than {util.RESIN_MAX}!")
                                util.strikes_inc(uid)
                            else:
                                if strack < 0:
                                    msg = ("Notification threshold "
                                           "can't be negative!")
                                    util.strikes_inc(uid)
                                elif strack > util.RESIN_MAX:
                                    msg = (f"Notification threshold can't be "
                                           f"higher than {util.RESIN_MAX} resin!")
                                    util.strikes_inc(uid)

                                else:
                                    util.warn_threshold_set(uid, strack)
                                    msg = (f"I have updated your "
                                           f"notifications to {strack} resin.")
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
                                state(uid)
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


def resin_cap(uid, tc=None):
    (hc_hour, hc_min), (sc_hour, sc_min) = util.resin_max(uid, tc)
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
    cwarn = util.warn_threshold(uid)
    hcinfo, scinfo = resin_cap(uid)
    hc, sc = resin_cap_format(hcinfo, scinfo, cwarn)
    tracking = '🟢' if uid in threads else '🔴'
    keyboard = [
        [InlineKeyboardButton(f"🌙 {cresin} 🌙",
                              callback_data='resin_menu'),
         InlineKeyboardButton(f"Tracking: {tracking}",
                              callback_data='tracking_menu')],
        [InlineKeyboardButton(sc,
                              callback_data='resin_menu'),
         InlineKeyboardButton(hc,
                              callback_data='resin_menu')],
        [InlineKeyboardButton("Spend Resin",
                              callback_data='spend_menu'),
         InlineKeyboardButton("Refill Resin",
                              callback_data='refill_menu')],
        [InlineKeyboardButton("« Back to Menu",
                              callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "What do you want to do?", reply_markup=reply_markup)


def tracking_menu(update):
    uid = update.effective_message.chat.id
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'track' not in user_state_menu[uid]:
        user_state_menu[uid]['track'] = list(util.TRACK_MAX)
    strack = user_state_menu[uid]['track']
    tracking = uid in threads
    trck_icon = '🟢' if tracking else '🔴'
    keyboard = [
        [InlineKeyboardButton(f"Tracking: {trck_icon}",
                              callback_data='tracking_menu')],
        [InlineKeyboardButton("« Back to Resin",
                              callback_data='resin_menu'),
         InlineKeyboardButton("« Back to Menu",
                              callback_data='main_menu')]
    ]
    if tracking:
        keyboard.insert(1,
                        [InlineKeyboardButton("Stop Tracking",
                                              callback_data='tracking_stop')])
    else:
        keyboard.insert(1,
                        [InlineKeyboardButton("˄",
                                              callback_data='tracking_up0'),
                         InlineKeyboardButton(" ",
                                              callback_data='nop'),
                         InlineKeyboardButton("˄",
                                              callback_data='tracking_up1'),
                         InlineKeyboardButton("˄",
                                              callback_data='tracking_up2')])
        keyboard.insert(2,
                        [InlineKeyboardButton(strack[0],
                                              callback_data='nop'),
                         InlineKeyboardButton(":",
                                              callback_data='nop'),
                         InlineKeyboardButton(strack[1],
                                              callback_data='nop'),
                         InlineKeyboardButton(strack[2],
                                              callback_data='nop')])
        keyboard.insert(3,
                        [InlineKeyboardButton("˅",
                                              callback_data='tracking_down0'),
                         InlineKeyboardButton(" ",
                                              callback_data='nop'),
                         InlineKeyboardButton("˅",
                                              callback_data='tracking_down1'),
                         InlineKeyboardButton("˅",
                                              callback_data='tracking_down2')])
        keyboard.insert(4,
                        [InlineKeyboardButton("Start Tracking",
                                              callback_data='tracking_start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "What is your timer?", reply_markup=reply_markup)


def tracking_start(update, context):
    uid = update.effective_message.chat.id
    mm = int(update.callback_query.message.reply_markup
             .inline_keyboard[2][0]['text'])
    s1 = int(update.callback_query.message.reply_markup
             .inline_keyboard[2][2]['text'])
    s2 = int(update.callback_query.message.reply_markup
             .inline_keyboard[2][3]['text'])
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
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'track' not in user_state_menu[uid]:
        user_state_menu[uid]['track'] = list(util.TRACK_MAX)
    strack = user_state_menu[uid]['track']
    txt = 'tracking_down'
    if up:
        txt = 'tracking_up'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        if strack[pos] < util.TRACK_MAX[pos]:
            strack[pos] += 1
    else:
        if strack[pos] > 0:
            strack[pos] -= 1
    tracking_menu(update)


def spend_menu(update):
    uid = update.effective_message.chat.id
    cresin = util.resin(uid)
    keyboard = [
        [InlineKeyboardButton(f"🌙 {cresin} 🌙",
                              callback_data='spend_menu')],
        [],
        [InlineKeyboardButton("« Back to Resin", callback_data='resin_menu'),
         InlineKeyboardButton("« Back to Menu", callback_data='main_menu')]
    ]
    if resin >= 10:
        keyboard[1].append(InlineKeyboardButton("10",
                                                callback_data='spend_r10'))
    else:
        keyboard[1].append(InlineKeyboardButton("No Resin Left!",
                                                callback_data='nop'))
    if resin >= 20:
        keyboard[1].append(InlineKeyboardButton("20",
                                                callback_data='spend_r20'))
    if resin >= 40:
        keyboard[1].append(InlineKeyboardButton("40",
                                                callback_data='spend_r40'))
    if resin >= 60:
        keyboard[1].append(InlineKeyboardButton("60",
                                                callback_data='spend_r60'))
    if resin >= 80:
        keyboard[1].append(InlineKeyboardButton("80",
                                                callback_data='spend_r80'))
    if resin >= 120:
        keyboard[1].append(InlineKeyboardButton("120",
                                                callback_data='spend_r120'))
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "How many resin do you want to spend?",
         reply_markup=reply_markup)


def spend_resin(update):
    uid = update.effective_message.chat.id
    sresin = int(update.callback_query.data.split('spend_r')[1])
    util.resin_dec(uid, sresin)
    spend_menu(update)


def refill_menu(update):
    uid = update.effective_message.chat.id
    cresin = util.resin(uid)
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'refill' not in user_state_menu[uid]:
        user_state_menu[uid]['refill'] = [0, 0, 0]
    srefill = user_state_menu[uid]['refill']
    keyboard = [
        [InlineKeyboardButton(f"🌙 {cresin} 🌙",
                              callback_data='refill_menu')],
        [InlineKeyboardButton("˄",
                              callback_data='refill_up0'),
         InlineKeyboardButton("˄",
                              callback_data='refill_up1'),
         InlineKeyboardButton("˄",
                              callback_data='refill_up2')],
        [InlineKeyboardButton(srefill[0],
                              callback_data='nop'),
         InlineKeyboardButton(srefill[1],
                              callback_data='nop'),
         InlineKeyboardButton(srefill[2],
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
                              callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "How many resin do you want to refill?",
         reply_markup=reply_markup)


def refill_pool(update):
    uid = update.effective_message.chat.id
    r0 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][0]['text'])
    r1 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][1]['text'])
    r2 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][2]['text'])
    irefill = int("".join([r0, r1, r2]))
    util.resin_inc(uid, irefill)
    refill_menu(update)


def refill_updown(update, up=True):
    uid = update.effective_message.chat.id
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'refill' not in user_state_menu[uid]:
        user_state_menu[uid]['refill'] = [0, 0, 0]
    srefill = user_state_menu[uid]['refill']
    cresin = util.resin(uid)
    txt = 'refill_up'
    if not up:
        txt = 'refill_down'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        srefill[pos] = srefill[pos] + 1 if srefill[pos] < 9 else srefill[pos]
    else:
        srefill[pos] = srefill[pos] - 1 if srefill[pos] > 0 else srefill[pos]
    if int("".join([str(c) for c in srefill])) > util.RESIN_MAX - cresin:
        user_state_menu[uid]['refill'] = [int(el) for el in f"{util.RESIN_MAX - cresin:03d}"]
    refill_menu(update)


def codes_menu(update):
    keyboard = [
        [InlineKeyboardButton("Rewards",
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
                              callback_data='main_menu')]
    ]
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
    keyboard = [
        [InlineKeyboardButton("« Back to Active Codes",
                              callback_data='codes_menu'),
         InlineKeyboardButton("« Back to Menu",
                              callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    edit_message(update, code, reply_markup=reply_markup)


def redeem_menu(update):
    keyboard = [
        [InlineKeyboardButton("« Back to Active Codes",
                              callback_data='codes_menu'),
         InlineKeyboardButton("« Back to Menu",
                              callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    edit_message(update,
                 ("Codes can be redeemed in website or in-game:\n"
                  "Website: https://genshin.mihoyo.com/en/gift\n"
                  "In-game: Settings - Account - Redeem code."),
                 reply_markup=reply_markup)


def settings_menu(update):
    keyboard = [
        [InlineKeyboardButton("⏰ Resin Warnings ⏰",
                              callback_data='settings_warn_menu')],
        [InlineKeyboardButton("📣 Promotion Code Notifications 📣",
                              callback_data='settings_promo_menu')],
        [InlineKeyboardButton("🌎 Local Time Zone 🌎",
                              callback_data='settings_timezone_menu')],
        [InlineKeyboardButton("« Back to Menu",
                              callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "What do you want to change?", reply_markup=reply_markup)


def settings_warn_menu(update):
    uid = update.effective_message.chat.id
    cwarn = util.warn_threshold(uid)
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'warn' not in user_state_menu[uid]:
        user_state_menu[uid]['warn'] = [int(cw) for cw in f"{cwarn:03d}"]
    swarn = user_state_menu[uid]['warn']
    iwarn = '🔔' if util.warn_allowed(uid) else '🔕'
    keyboard = [
        [InlineKeyboardButton(f"Threshold: {cwarn}",
                              callback_data='nop'),
         InlineKeyboardButton(f"Resin Warnings: {iwarn}",
                              callback_data='warn_toggle')],
        [InlineKeyboardButton("˄",
                              callback_data='warn_up0'),
         InlineKeyboardButton("˄",
                              callback_data='warn_up1'),
         InlineKeyboardButton("˄",
                              callback_data='warn_up2')],
        [InlineKeyboardButton(swarn[0],
                              callback_data='nop'),
         InlineKeyboardButton(swarn[1],
                              callback_data='nop'),
         InlineKeyboardButton(swarn[2],
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
                              callback_data='main_menu')]
    ]
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
    swarn = int("".join([r0, r1, r2]))
    util.warn_threshold_set(uid, swarn)
    settings_warn_menu(update)


def warn_updown(update, up=True):
    uid = update.effective_message.chat.id
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'warn' not in user_state_menu[uid]:
        user_state_menu[uid]['warn'] = [int(cw)
                                        for cw
                                        in f"{util.warn_threshold(uid):03d}"]
    swarn = user_state_menu[uid]['warn']
    txt = 'warn_down'
    if up:
        txt = 'warn_up'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        swarn[pos] = swarn[pos] + 1 if swarn[pos] < 9 else swarn[pos]
    else:
        swarn[pos] = swarn[pos] - 1 if swarn[pos] > 0 else swarn[pos]
    twarn = int("".join([str(c) for c in swarn]))
    if twarn > 159:
        user_state_menu[uid]['warn'] = [1, 5, 9]
    settings_warn_menu(update)


def settings_promo_menu(update):
    uid = update.effective_message.chat.id
    ipromo = '🔔' if util.codes_notify_allowed(uid) else '🔕'
    keyboard = [
        [InlineKeyboardButton(f"Promotion Code Notifications: {ipromo}",
                              callback_data='promo_toggle')],
        [InlineKeyboardButton("« Back to Settings",
                              callback_data='settings_menu'),
         InlineKeyboardButton("« Back to Menu",
                              callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update,
         "Do you want to be notified when a promotion code become active?",
         reply_markup=reply_markup)


def promo_toggle(update):
    uid = update.effective_message.chat.id
    util.codes_notify_toggle(uid)
    settings_promo_menu(update)


def settings_timezone_menu(update, updown=False):
    uid = update.effective_message.chat.id
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'timezone' not in user_state_menu[uid]:
        user_state_menu[uid]['timezone'] = 0
    ictz = '🟢' if util.timezone(uid) else '🔴'
    ctzl = util.timezone_local(uid)
    keyboard = [
        [InlineKeyboardButton(f"Local Hour: {ctz}",
                              callback_data='timezone_local'),
         InlineKeyboardButton(f"Custom Time Zone: {ictz}",
                              callback_data='timezone_toggle')],
        [InlineKeyboardButton("« Back to Settings",
                              callback_data='settings_menu'),
         InlineKeyboardButton("« Back to Menu",
                              callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    resp = send_message
    if update.callback_query is not None:
        resp = edit_message
    resp(update, "Do you want personalized hour (based on your time zone)?",
         reply_markup=reply_markup)


def timezone_updown(update, up=True):
    uid = update.effective_message.chat.id
    if uid not in user_state_menu:
        user_state_menu[uid] = {}
    if 'timezone' not in user_state_menu[uid]:
        hh = int(datetime.strftime(datetime.now(), '%H'))
        user_state_menu[uid]['timezone'] = [hh//10, hh%10]
    stz = user_state_menu[uid]['timezone']
    txt = 'timezone_down'
    if up:
        txt = 'timezone_up'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        stz[pos] = stz[pos] + 1 if stz[pos] < 9 else stz[pos]
    else:
        stz[pos] = stz[pos] - 1 if stz[pos] > 0 else stz[pos]
    ttz = int("".join([str(c) for c in stz]))
    if ttz > 23:
        user_state_menu[uid]['timezone'] = [2, 3]
    settings_timezone_menu(update)


def timezone_toggle(update):
    uid = update.effective_message.chat.id
    util.timezone_toggle(uid)
    settings_timezone_menu(update)


def timezone_set(update):
    uid = update.effective_message.chat.id
    r0 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][0]['text'])
    r1 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][1]['text'])
    stz = int("".join([r0, r1]))
    util.timezone_local_set(uid, stz)
    settings_timezone_menu(update)


def button_handler(update, context):
    if update is not None:
        query = update.callback_query
        # pprint(update.to_dict())
        try:
            query.answer()
        except BadRequest:
            pass

        if query.data == 'update_resin_ui':
            update_resin_ui(update, context)
        elif query.data == 'main_menu':
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
        elif query.data == 'timezone_toggle':
            timezone_toggle(update)
        elif query.data == 'timezone_set':
            timezone_set(update)
        elif query.data.startswith('timezone_up'):
            timezone_updown(update)
        elif query.data.startswith('timezone_down'):
            timezone_updown(update, up=False)


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

    help_handler = CommandHandler('help', help,
                                  filters=~Filters.update.edited_message)
    dispatcher.add_handler(help_handler)

    menu_handler = CommandHandler('menu', menu,
                                  filters=~Filters.update.edited_message)
    dispatcher.add_handler(menu_handler)

    resin_handler = CommandHandler('resin', resin,
                                   filters=~Filters.update.edited_message)
    dispatcher.add_handler(resin_handler)

    # spend_handler = CommandHandler('spend', spend,
    #                                filters=~Filters.update.edited_message)
    # dispatcher.add_handler(spend_handler)

    # refill_handler = CommandHandler('refill', refill,
    #                                 filters=~Filters.update.edited_message)
    # dispatcher.add_handler(refill_handler)

    # track_handler = CommandHandler('track', track,
    #                                filters=~Filters.update.edited_message)
    # dispatcher.add_handler(track_handler)

    # resinwarn_handler = CommandHandler('resinwarn', warn,
    #                                    filters=~Filters.update.edited_message)
    # dispatcher.add_handler(resinwarn_handler)

    # timezone_handler = CommandHandler('timezone', timezone,
    #                                   filters=~Filters.update.edited_message)
    # dispatcher.add_handler(timezone_handler)

    # codenotify_handler = CommandHandler('codenotify', codenotify,
    #                                     filters=~Filters.update.edited_message)
    # dispatcher.add_handler(codenotify_handler)

    # codeactive_handler = CommandHandler('codeactive', codeactive,
    #                                     filters=~Filters.update.edited_message)
    # dispatcher.add_handler(codeactive_handler)

    cancel_handler = CommandHandler('cancel', cancel,
                                    filters=~Filters.update.edited_message)
    dispatcher.add_handler(cancel_handler)

    stop_handler = CommandHandler('stop', stop,
                                  filters=~Filters.update.edited_message)
    dispatcher.add_handler(stop_handler)

    announce_handler = CommandHandler('announce', announce,
                                      filters=~Filters.update.edited_message)
    dispatcher.add_handler(announce_handler)

    text_handler = MessageHandler(
        Filters.text & ~Filters.update.edited_message, text)
    dispatcher.add_handler(text_handler)

    dispatcher.add_handler(CallbackQueryHandler(button_handler))

    notify_restart(updater)

    updater.start_polling()
    updater.idle()