#!/usr/bin/env python3

from datetime import datetime
import database as db
import threads as th
import util as ut


STATE = {}

HELP = (
    "I can help you manage your resin. "
    "Control me by sending these commands:"
    "\n\n"

    "❔ /menu - Interact with me using UI. <b>[beta]</b>"
    "\n\n"

    "<b>Manage Resin</b>"
    "\n"
    "❔ /resin <code>[#]</code> - Resin status. "
    "Use <code>number</code> to calculate hour before cap."
    "\n"
    "❔ /set <code>[#]</code> - Set resin value."
    "\n"
    "❔ /spend <code>[#]</code> - Spend resin."
    "\n"
    "❔ /refill <code>[#]</code> - Increase resin."
    "\n"
    "❔ /track <code>[mm:ss]</code> - Synchronize bot timer. "
    "Use <code>-1</code> to disable."
    "\n\n"

    "<b>Reminders</b>"
    "\n"
    "❔ /warnings <code>[#]</code> - Set resin warning threshold. "
    "Use <code>-1</code> to disable warnings."
    "\n"
    "❔ /notifications <code>[#]</code> - Promotion code notifications. "
    "Use <code>1/-1</code> to enable/disable notifications."
    "\n"
    "❔ /timezone <code>[mm:ss]</code> - Set your time zone. "
    "Use <code>-1</code> to disable timezone."
    "\n"
    "❔ /codes - List of promotion codes."
    "\n\n"

    "<b>Bot Usage</b>\n"
    "❔ /help - List of commands."
    "\n"
    "❔ /cancel - Cancel current action."
    "\n"
    "❔ /stop - Remove your information from the bot."
    "\n\n"
    "<i><b>Note:</b> Arguments inside brackets are optional.</i>"
)


def _state(uid, state=ut.CMD.NOP):
    STATE[uid] = state


def del_state(uid):
    if uid in STATE:
        del STATE[uid]


def _synchronized(uid, msg):
    if not th.is_tracked(uid):
        msg = (f"{msg}\n\n"
               f"⚠ Bot not tracking your "
               f"resin, send /track to synchronize bot timer.")
    return msg


def start(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        msg = f"I'm glad to see you again, Traveler!"
        if not db.cached(uid):
            _state(uid)
            db.add_user(uid)
            msg = f"Hi Traveler, I'm Paimon!\n\n{HELP}"
        ut.send(update, msg)


def bot_help(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        ut.send(update, HELP)


def resin(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            cur_resin = db.get_resin(uid)
            msg = (f"❗ Argument must be an integer greater than "
                   f"{cur_resin} and lower than {ut.RESIN_MAX}, "
                   f"e.g. /resin, /resin 135")
            if context.args:
                try:
                    value = int(context.args[0])
                except ValueError:
                    msg = ut.strike_user(uid, msg)
                else:
                    if cur_resin < value < ut.RESIN_MAX:
                        msg = ut.cap_format(uid, value)
                        msg = _synchronized(uid, msg)
                        db.dec_strikes(uid)
                    else:
                        msg = ut.strike_user(uid, msg)
            else:
                msg = ut.cap_format(uid)
                db.dec_strikes(uid)
            _state(uid)
            ut.send(update, msg)


def _set_resin(args, uid, msg):
    try:
        value = int(args[0])
    except ValueError:
        msg = ut.strike_user(uid, msg)
    else:
        if 0 < value < ut.RESIN_MAX:
            db.set_resin(uid, value)
            msg = ut.text_format("Current resin", value)
            msg = _synchronized(uid, msg)
            db.dec_strikes(uid)
        else:
            msg = ut.strike_user(uid, msg)
    return msg


def set_resin(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            msg = (f"❗ Argument must be an integer lower than {ut.RESIN_MAX}, "
                   f"e.g. /set, /set 12")
            if context.args:
                msg = _set_resin(context.args, uid, msg)
            else:
                msg = (f"Tell me your current resin "
                       f"(max: <code>{ut.RESIN_MAX}</code>)")
                _state(uid, ut.CMD.SET)
                db.dec_strikes(uid)
            ut.send(update, msg)


def _spend(args, uid, msg, current):
    try:
        value = int(args[0])
    except ValueError:
        msg = ut.strike_user(uid, msg)
    else:
        if 0 < value < current:
            db.dec_resin(uid, value)
            msg = ut.text_format("Current resin", current - value)
            msg = _synchronized(uid, msg)
            db.dec_strikes(uid)
        else:
            msg = ut.strike_user(uid, msg)
    return msg


def spend(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            cur_resin = db.get_resin(uid)
            msg = (f"❗ Argument must be an integer greater than 0 "
                   f"and lower than {cur_resin}, "
                   f"e.g. /spend, /spend 20")
            if context.args:
                msg = _spend(context.args, uid, msg, cur_resin)
            else:
                msg = (f"Tell me how much resin to spend "
                       f"(max: <code>{cur_resin}</code>)")
                _state(uid, ut.CMD.SPEND)
                db.dec_strikes(uid)
            ut.send(update, msg)


def _refill(args, uid, msg, current, max_resin):
    try:
        value = int(args[0])
    except ValueError:
        msg = ut.strike_user(uid, msg)
    else:
        if 0 < value < max_resin:
            db.inc_resin(uid, value)
            msg = ut.text_format("Current resin", current + value)
            msg = _synchronized(uid, msg)
            db.dec_strikes(uid)
        else:
            msg = ut.strike_user(uid, msg)
    return msg


def refill(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            cur_resin = db.get_resin(uid)
            max_resin = ut.RESIN_MAX - cur_resin
            msg = (f"❗ Argument must be an integer greater than 0 "
                   f"and lower than {max_resin}, "
                   f"e.g. /refill, /refill 20")
            if context.args:
                msg = _refill(context.args, uid, msg, cur_resin, max_resin)
            else:
                msg = (f"Tell me how much resin to refill "
                       f"(max: <code>{max_resin}</code>)")
                _state(uid, ut.CMD.REFILL)
                db.dec_strikes(uid)
            ut.send(update, msg)


def _track(args, bot, uid, msg):
    try:
        datetime.strptime(args[0], "%M:%S")
    except ValueError:
        try:
            value = int(args[0])
        except ValueError:
            msg = ut.strike_user(uid, msg)
        else:
            if value == -1:
                th.del_thread(uid)
                msg = ut.text_format("Current tracking status", "disabled")
                db.dec_strikes(uid)
            else:
                msg = ut.strike_user(uid, msg)
    else:
        minutes, seconds = map(int, args[0].split(':'))
        timer = minutes * 60 + seconds
        th.new_thread(bot, uid, timer)
        msg = "Bot timer synchronized."
        db.dec_strikes(uid)
    return msg


def track(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            msg = ("❗ Argument must have format: mm:ss, "
                   "e.g. /track, /track 5:35m /track -1")
            if context.args:
                msg = _track(context.args, context.bot, uid, msg)
            else:
                msg = ("Tell me your genshin timer "
                       "in format <code>mm:ss</code>, "
                       "or <code>-1</code> to disable")
                _state(uid, ut.CMD.TRACK)
                db.dec_strikes(uid)
            ut.send(update, msg)


def _warnings(args, uid, msg):
    try:
        value = int(args[0])
    except ValueError:
        msg = ut.strike_user(uid, msg)
    else:
        if value == -1 or 0 < value < ut.RESIN_MAX:
            if value == -1:
                value = "disabled"
                db.unset_warn(uid)
            else:
                db.set_warn(uid, value)
            msg = ut.text_format("Current warning threshold", value)
            msg = _synchronized(uid, msg)
            db.dec_strikes(uid)
        else:
            msg = ut.strike_user(uid, msg)
    return msg


def warnings(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            msg = (f"❗ Argument must be an integer greater than 0 "
                   f"and lower than {ut.RESIN_MAX}, or -1, "
                   f"e.g. /warnings, /warnings -1, /warning 140")
            if context.args:
                msg = _warnings(context.args, uid, msg)
            else:
                cur_warn = db.get_warn(uid)
                if cur_warn == -1:
                    cur_warn = "disabled"
                msg = (f"{ut.text_format('Warning threshold', cur_warn)}\n\n"
                       f"Tell me resin value to be warned at, "
                       f"or <code>-1</code> to disable")
                _state(uid, ut.CMD.WARN)
                db.dec_strikes(uid)
            ut.send(update, msg)


def notifications(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            msg = ("❗ Argument must be 1 or -1, "
                   "e.g. /notifications 1, /notifications -1")
            if context.args:
                try:
                    value = int(context.args[0])
                except ValueError:
                    msg = ut.strike_user(uid, msg)
                else:
                    if abs(value) == 1:
                        if value == -1:
                            db.unset_notifications(uid)
                            value = "disabled"
                        else:
                            db.set_notifications(uid)
                            value = "enabled"
                        msg = ut.text_format("Current notifications status",
                                             value)
                        db.dec_strikes(uid)
                    else:
                        msg = ut.strike_user(uid, msg)
            else:
                status = ('enabled' if db.get_notifications(uid) == 1
                          else 'disabled')
                msg = ut.text_format("Current notifications status", status)
                db.dec_strikes(uid)
            ut.send(update, msg)


def _timezone(args, uid, msg):
    try:
        datetime.strptime(args[0], "%H:%M")
    except ValueError:
        try:
            value = int(args[0])
        except ValueError:
            msg = ut.strike_user(uid, msg)
        else:
            if value == -1:
                db.unset_timezone(uid)
                msg = ut.text_format("Current timezone", "disabled")
                db.dec_strikes(uid)
            else:
                msg = ut.strike_user(uid, msg)
    else:
        hour, minutes = map(int, args[0].split(':'))
        bot_hour, bot_minutes = map(int, datetime.now()
                                    .strftime("%H:%M").split(':'))
        tz_hour = hour - bot_hour
        tz_minutes = minutes - bot_minutes
        db.set_timezone(uid, tz_hour, tz_minutes)
        tz = ut.normalize_timezone(tz_hour, tz_minutes)
        msg = (f"{ut.text_format('Bot hour', f'{bot_hour:02}:{bot_minutes:02}')}\n\n"  # noqa
               f"{ut.text_format('Current timezone', f'{tz}')}")
        db.dec_strikes(uid)
    return msg


def timezone(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            msg = ("❗ Argument must have format(24h): hh:mm or -1, "
                   "e.g. /timezone, /timezone -1, /timezone 18:30")
            if context.args:
                msg = _timezone(context.args, uid, msg)
            else:
                tz_hour, tz_minutes = db.get_timezone(uid).split(':')
                if tz_hour == 'null':
                    tz = "disabled"
                else:
                    tz = ut.normalize_timezone(tz_hour, tz_minutes)
                msg = (f"{ut.text_format('Current timezone', tz)}\n\n"
                       f"Tell me your current hour "
                       f"in format(24h): <code>hh:mm</code>, "
                       f"or <code>-1</code> to disable")
                _state(uid, ut.CMD.TZ)
                db.dec_strikes(uid)
            ut.send(update, msg)


def text(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            msg = "❗ Send only one argument, following the format."
            args = update.message.text.split()
            if len(args) == 1:
                if STATE[uid] == ut.CMD.SET:
                    msg = (f"❗ Value must be an integer lower "
                           f"than {ut.RESIN_MAX}.")
                    msg = _set_resin(args, uid, msg)
                elif STATE[uid] == ut.CMD.SPEND:
                    cur_resin = db.get_resin(uid)
                    msg = (f"❗ Value must be an integer greater than 0 "
                           f"and lower than {cur_resin}.")
                    msg = _spend(args, uid, msg, cur_resin)
                elif STATE[uid] == ut.CMD.REFILL:
                    cur_resin = db.get_resin(uid)
                    max_resin = ut.RESIN_MAX - cur_resin
                    msg = (f"❗ Value must be an integer greater than 0 "
                           f"and lower than {max_resin}.")
                    msg = _refill(args, uid, msg, cur_resin, max_resin)
                elif STATE[uid] == ut.CMD.TRACK:
                    msg = "❗ Timer must have format: <code>mm:ss</code>."
                    msg = _track(args, context.bot, uid, msg)
                elif STATE[uid] == ut.CMD.WARN:
                    msg = (f"❗ Value must be an integer greater than 0 "
                           f"and lower than {ut.RESIN_MAX}, "
                           f"or <code>-1</code>.")
                    msg = _warnings(args, uid, msg)
                elif STATE[uid] == ut.CMD.TZ:
                    msg = ("❗ Hour must have format(24h): <code>hh:mm</code> "
                           "or <code>-1</code>.")
                    msg = _timezone(args, uid, msg)
            ut.send(update, msg)


def codes(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            unexpired = db.unexpired_codes()
            ut.send(update, ut.codes_format(unexpired))


def cancel(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            if uid in STATE and STATE[uid] != ut.CMD.NOP:
                msg = (f"The command <code>{STATE[uid].value}</code> "
                       f"has been cancelled. Anything else I can do for you?"
                       f"\n\n"
                       f"Send /help for a list of commands.")
            else:
                msg = ("No active command to cancel. "
                       "I wasn't doing anything anyway.\nZzzzz...")
            ut.send(update, msg)
            _state(uid)


def stop(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        msg = "Bot doesn't have information about you."
        if db.cached(uid):
            ut.blocked(uid)
            msg = "Your information has been removed from the bot."
        ut.send(update, msg)


def announce(update, context):
    uid = update.effective_message.chat.id
    with open('.adminid', 'r') as f:
        admin = int(f.read().strip())
    if uid == admin:
        msg = f"❗ <b>Announcement:</b> {' '.join(context.args)}"
        ut.notify(context.job_queue, msg)
