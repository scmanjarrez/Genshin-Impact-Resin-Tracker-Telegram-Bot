from telegram.error import Unauthorized, BadRequest
from telegram import ParseMode
from datetime import datetime
from enum import Enum
import paimon_cli as cli
import paimon_gui as gui
import database as db
import threads as th
import traceback

RESIN_MAX = 160
RESIN_REGEN = 8
REFILL_BASE = (0, 6, 0)
TRACK_MAX = (7, 5, 9)
WARN_MAX = (1, 5, 9)
STRIKE_BAN = 75
TIME_BETWEEN_NOTIFY = 2
USERS_TO_NOTIFY = 20


class CMD(Enum):
    NOP = ''
    SET = 'set'
    SPEND = 'spend'
    REFILL = 'refill'
    TRACK = 'track'
    WARN = 'warnings'
    TZ = 'timezone'


def blocked(uid):
    th.del_thread(uid)
    cli.del_state(uid)
    gui.del_state(uid)
    db.del_user(uid)


def notify_callback(context):
    uid, msg = context.job.context
    send_bot(context.bot, uid, msg)


def notify(queue, msg, force=True):
    if force:
        users = db.all_users()
    else:
        users = db.all_users_notify()
    cnt = USERS_TO_NOTIFY
    time = 0
    for uid, in users:
        if cnt == 0:
            cnt = USERS_TO_NOTIFY
            time += TIME_BETWEEN_NOTIFY
        queue.run_once(notify_callback, time,
                       context=(uid, msg), name=f"{uid}: {msg[:15]}")
        cnt -= 1


def notify_restart(queue):
    msg = "⚠ Bot restarted. Please, synchronize bot timer /track."
    notify(queue, msg)


def notify_codes(queue):
    unmarked = db.unmarked_codes()
    if unmarked:
        msg = codes_format(unmarked)
        notify(queue, msg, force=False)
        db.mark_codes([(c[1],) for c in unmarked])


def strike_user(uid, msg=""):
    db.inc_strikes(uid)
    cur_strikes = db.get_strikes(uid)
    if cur_strikes >= STRIKE_BAN:
        msg = "⛔ You've been banned for spam/flooding ⛔"
        db.ban_user(uid)
    if not msg:
        msg = ["🚫 Unknown command 🚫\n\n",
               "ℹ️ Send /help for a list of commands.\n\n",
               "⛔ Don't flood the bot or you will be banned ⛔"]
    return "".join(msg)


def user_hour(hour, minutes, tz_hour, tz_minutes):
    bot_hour = int(datetime.strftime(datetime.now(), '%H'))
    bot_min = int(datetime.strftime(datetime.now(), '%M'))
    local_min = (bot_min + minutes + tz_minutes) % 60
    carry_hour = (bot_min + minutes) // 60
    local_hour = (bot_hour + hour + carry_hour + tz_hour) % 24
    return local_hour, local_min


def resin_cap(uid, resin):
    (hard_h, hard_m), (soft_h, soft_m) = db.max_resin(uid, resin)
    tz_hour, tz_minutes = db.get_timezone(uid).split(':')
    cap = ([(hard_h, hard_m), None], [(soft_h, soft_m), None])
    if tz_hour != 'null':
        tz_hour, tz_minutes = int(tz_hour), int(tz_minutes)
        hard_hour, hard_min = user_hour(hard_h, hard_m, tz_hour, tz_minutes)
        soft_hour, soft_min = user_hour(soft_h, soft_m, tz_hour, tz_minutes)
        cap[0][1] = (hard_hour, hard_min)
        cap[1][1] = (soft_hour, soft_min)
    return cap


def cap_format(uid, resin=None):
    no_soft = False
    if resin is None:
        resin = db.get_warn(uid)
        if resin == -1:
            no_soft = True
            resin = RESIN_MAX
    cur_resin = db.get_resin(uid)
    hard, soft = resin_cap(uid, resin)

    soft_time = f"<code>{soft[0][0]}h+{soft[0][1]}m</code>"
    hard_time = f"<code>{hard[0][0]}h+{hard[0][1]}m</code>"
    hard_h = ""
    soft_h = ""
    if hard[1] is not None:
        soft_hour = f"<code>{soft[1][0]:02}:{soft[1][1]:02}h</code>"
        hard_hour = f"<code>{hard[1][0]:02}:{hard[1][1]:02}h</code>"
        soft_h = f" @ {soft_hour}"
        hard_h = f" @ {hard_hour}"

    soft_str = f"<b>Soft Cap (<code>{resin}</code>):</b> {soft_time}{soft_h}\n"

    return (f"<b>Current resin:</b> <code>{cur_resin}</code>\n\n"
            f"{soft_str if not no_soft else ''}"
            f"<b>Hard Cap (<code>{RESIN_MAX}</code>):</b> {hard_time}{hard_h}")


def gui_cap_format(uid):
    no_soft = False
    resin = db.get_warn(uid)
    if resin == -1:
        no_soft = True
        resin = RESIN_MAX
    hard, soft = resin_cap(uid, resin)

    soft_time = f"{soft[0][0]}h+{soft[0][1]}m"
    hard_time = f"{hard[0][0]}h+{hard[0][1]}m"
    hard_h = ""
    soft_h = ""
    if hard[1] is not None:
        soft_hour = f"{soft[1][0]:02}:{soft[1][1]:02}h"
        hard_hour = f"{hard[1][0]:02}:{hard[1][1]:02}h"
        soft_h = f" @ {soft_hour}"
        hard_h = f" @ {hard_hour}"

    soft_str = f"{soft_time}{soft_h} ({resin})"
    hard_str = f"{hard_time}{hard_h} ({RESIN_MAX})"
    if not no_soft:
        return [(soft_str, 'resin_menu'), (hard_str, 'resin_menu')]
    else:
        return [(hard_str, 'resin_menu')]


def codes_format(codes):
    formatted = [f"<b>Rewards:</b> <code>{rew}</code>\n"
                 f"<b>EU:</b> <code>{eu}</code>\n"
                 f"<b>NA:</b> <code>{na}</code>\n"
                 f"<b>SEA:</b> <code>{sea}</code>\n\n"
                 for rew, eu, na, sea in codes]
    formatted.append("Codes can be redeemed in:\n"
                     "<b>Website:</b> https://genshin.mihoyo.com/en/gift\n"
                     "<b>In-game:</b> Settings - Account - Redeem code.")
    return "".join(formatted)


def normalize_timezone(hour, minutes):
    if isinstance(hour, str):
        hour = int(hour)
        minutes = int(minutes)
    sym_hour = '-'
    zero_hour = ''
    sym_minutes = '-'
    zero_minutes = ''
    if hour >= 0:
        sym_hour = '+'
    if -10 < hour < 10:
        zero_hour = '0'
    if minutes >= 0:
        sym_minutes = '+'
    if -10 < minutes < 10:
        zero_minutes = '0'
    return (f"{sym_hour}{zero_hour}{abs(hour)}h"
            f"{sym_minutes}{zero_minutes}{abs(minutes)}m")


def text_format(first, second):
    return f"<b>{first}:</b> <code>{second}</code>."


def not_started(update):
    send(update, "Send /start before continuing.")


def not_started_gui(update):
    edit(update, "Send /start before continuing.", None)


def send(update, msg, quote=True, reply_markup=None):
    try:
        update.message.reply_html(msg, quote=quote, reply_markup=reply_markup,
                                  disable_web_page_preview=True)
    except Unauthorized:
        blocked(update.effective_message.chat.id)


def send_bot(bot, uid, msg, reply_markup=None):
    try:
        bot.send_message(uid, msg, ParseMode.HTML, reply_markup=reply_markup,
                         disable_web_page_preview=True)
    except Unauthorized:
        blocked(uid)


def edit(update, msg, reply_markup):
    try:
        update.callback_query.edit_message_text(msg, ParseMode.HTML,
                                                reply_markup=reply_markup,
                                                disable_web_page_preview=True)
    except BadRequest as br:
        if not str(br).startswith("Message is not modified:"):
            print(f"***  Exception caught in edit "
                  f"({update.effective_message.chat.id}): ", br)
            traceback.print_stack()


def backup_trackings():
    with open('.trackings', 'w') as f:
        f.write("\n".join([str(uid)
                           for uid in th.THREADS if th.is_tracked(uid)]))


def restore_trackings(bot):
    try:
        with open('.trackings', 'r') as f:
            trackings = map(int, f.read().splitlines())
            for uid in trackings:
                th.new_thread(bot, uid, RESIN_REGEN * 60)
    except FileNotFoundError:
        pass
