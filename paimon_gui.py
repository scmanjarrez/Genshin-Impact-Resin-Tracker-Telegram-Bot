#!/usr/bin/env python3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import database as db
import threads as th
import util as ut


STATE = {}


def _state(uid, state, value):
    if uid not in STATE:
        STATE[uid] = {}

    if state not in STATE[uid]:
        STATE[uid][state] = value


def del_state(uid):
    if uid in STATE:
        del STATE[uid]


def _del_substate(uid, state):
    if uid in STATE and state in STATE[uid]:
        del STATE[uid][state]


def button(buttons):
    return [InlineKeyboardButton(bt[0], callback_data=bt[1]) for bt in buttons]


def menu(update, context):
    uid = update.effective_message.chat.id
    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started(update)
        else:
            main_menu(update)


def main_menu(update):
    kb = [button([("🌙 Resin 🌙", 'resin_menu')]),
          button([("🎁 Promotion Codes 🎁", 'codes_menu')]),
          button([("⚙ Settings ⚙", 'settings_menu')])]
    resp = ut.send
    if update.callback_query is not None:
        resp = ut.edit
    resp(update, "Main Menu", reply_markup=InlineKeyboardMarkup(kb))


def _tracking_status(uid):
    if th.is_unsync(uid):
        return '🟠'
    if th.is_tracked(uid):
        return '🟢'
    return '🔴'


def resin_menu(update):
    uid = update.effective_message.chat.id
    cur_resin = db.get_resin(uid)
    tracking = _tracking_status(uid)
    kb = [button([(f"🌙 {cur_resin} 🌙", 'resin_menu'),
                  (f"Tracking: {tracking}", 'tracking_menu')]),
          button(ut.gui_cap_format(uid)),
          button([("Spend", 'spend_menu'),
                  ("Refill", 'refill_menu')]),
          button([("« Back to Menu", 'main_menu')])]
    ut.edit(update, "Resin Menu", InlineKeyboardMarkup(kb))


def tracking_menu(update):
    uid = update.effective_message.chat.id
    _state(uid, ut.CMD.TRACK, list(ut.TRACK_MAX))
    st_track = STATE[uid][ut.CMD.TRACK]
    tracking = _tracking_status(uid)
    kb = [button([(f"Tracking: {tracking}", 'tracking_menu')]),
          button([("« Back to Resin", 'resin_menu'),
                  ("« Back to Menu", 'main_menu')])]
    track_txt = "Start Tracking"
    if th.is_unsync(uid):
        track_txt = "Synchronize"
    if th.is_unsync(uid) or not th.is_tracked(uid):
        kb.insert(1, button([("˄", 'tracking_up0'),
                             (" ", 'nop'),
                             ("˄", 'tracking_up1'),
                             ("˄", 'tracking_up2')]))
        kb.insert(2, button([(st_track[0], 'nop'),
                             (":", 'nop'),
                             (st_track[1], 'nop'),
                             (st_track[2], 'nop')]))
        kb.insert(3, button([("˅", 'tracking_down0'),
                             (" ", 'nop'),
                             ("˅", 'tracking_down1'),
                             ("˅", 'tracking_down2')]))
        kb.insert(4, button([(track_txt, 'tracking_start')]))
    if th.is_unsync(uid) or th.is_tracked(uid):
        idx = 1
        if th.is_unsync(uid):
            idx = 5
        kb.insert(idx, button([("Stop Tracking", 'tracking_stop')]))

    ut.edit(update, "Tracking Menu", InlineKeyboardMarkup(kb))


def tracking_start(update, context):
    uid = update.effective_message.chat.id
    mm = int(update.callback_query.message.reply_markup
             .inline_keyboard[2][0]['text'])
    s1 = int(update.callback_query.message.reply_markup
             .inline_keyboard[2][2]['text'])
    s2 = int(update.callback_query.message.reply_markup
             .inline_keyboard[2][3]['text'])

    th.new_thread(context.bot, uid, mm*60 + s1*10 + s2)
    tracking_menu(update)


def tracking_stop(update):
    uid = update.effective_message.chat.id
    th.del_thread(uid)
    tracking_menu(update)


def tracking_updown(update, up=True):
    uid = update.effective_message.chat.id
    _state(uid, ut.CMD.TRACK, list(ut.TRACK_MAX))
    st_track = STATE[uid][ut.CMD.TRACK]
    txt = 'tracking_down'
    if up:
        txt = 'tracking_up'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        if st_track[pos] < ut.TRACK_MAX[pos]:
            st_track[pos] += 1
    else:
        if st_track[pos] > 0:
            st_track[pos] -= 1
    tracking_menu(update)


def spend_menu(update):
    uid = update.effective_message.chat.id
    cur_resin = db.get_resin(uid)
    kb = [button([(f"🌙 {cur_resin} 🌙", 'spend_menu')]),
          [],
          button([("« Back to Resin", 'resin_menu'),
                  ("« Back to Menu", 'main_menu')])]
    if cur_resin >= 10:
        kb[1].append(button([("10", 'spend_r10')])[0])
    else:
        kb[1].append(button([("No Resin Left!", 'nop')])[0])
    if cur_resin >= 20:
        kb[1].append(button([("20", 'spend_r20')])[0])
    if cur_resin >= 30:
        kb[1].append(button([("30", 'spend_r30')])[0])
    if cur_resin >= 40:
        kb[1].append(button([("40", 'spend_r40')])[0])
    if cur_resin >= 60:
        kb[1].append(button([("60", 'spend_r60')])[0])
    if cur_resin >= 80:
        kb[1].append(button([("80", 'spend_r80')])[0])
    if cur_resin >= 90:
        kb[1].append(button([("90", 'spend_r90')])[0])
    if cur_resin >= 120:
        kb[1].append(button([("120", 'spend_r120')])[0])

    ut.edit(update, "Spend Menu", InlineKeyboardMarkup(kb))


def spend_resin(update):
    uid = update.effective_message.chat.id
    resin = int(update.callback_query.data.split('spend_r')[1])
    db.dec_resin(uid, resin)
    spend_menu(update)


def refill_menu(update):
    uid = update.effective_message.chat.id
    cur_resin = db.get_resin(uid)
    _state(uid, ut.CMD.REFILL, list(ut.REFILL_BASE))
    st_refill = STATE[uid][ut.CMD.REFILL]
    kb = [button([(f"🌙 {cur_resin} 🌙", 'refill_menu')]),
          button([("˄", 'refill_up0'),
                  ("˄", 'refill_up1'),
                  ("˄", 'refill_up2')]),
          button([(st_refill[0], 'nop'),
                  (st_refill[1], 'nop'),
                  (st_refill[2], 'nop')]),
          button([("˅", 'refill_down0'),
                  ("˅", 'refill_down1'),
                  ("˅", 'refill_down2')]),
          button([("Refill", 'refill_r')]),
          button([("« Back to Resin", 'resin_menu'),
                  ("« Back to Menu", 'main_menu')])]
    ut.edit(update, "Refill Menu", InlineKeyboardMarkup(kb))


def refill_resin(update):
    uid = update.effective_message.chat.id
    r0 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][0]['text'])
    r1 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][1]['text'])
    r2 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][2]['text'])
    value = int("".join([r0, r1, r2]))
    db.inc_resin(uid, value)
    refill_menu(update)


def refill_updown(update, up=True):
    uid = update.effective_message.chat.id
    _state(uid, ut.CMD.REFILL, list(ut.REFILL_BASE))
    st_refill = STATE[uid][ut.CMD.REFILL]
    cur_resin = db.get_resin(uid)
    txt = 'refill_up'
    if not up:
        txt = 'refill_down'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        st_refill[pos] = (st_refill[pos] + 1) % 10
    else:
        st_refill[pos] = (st_refill[pos] - 1) % 10
    if int("".join(str(c) for c in st_refill)) > ut.RESIN_MAX - cur_resin:
        new_state = ut.RESIN_MAX - cur_resin
        if new_state < 0:
            new_state = 0
        STATE[uid][ut.CMD.REFILL] = [int(el) for el in f"{new_state:03d}"]
    refill_menu(update)


def codes_menu(update):
    kb = [button([("Rewards", 'codes_menu'),
                  ("EU", 'codes_menu'),
                  ("NA", 'codes_menu'),
                  ("SEA", 'codes_menu')]),
          button([("How to redeem?", 'codes_redeem')]),
          button([("« Back to Menu", 'main_menu')])]
    pre = 'code_desc'
    for idx, code in enumerate(db.unexpired_codes()):
        rewards, eu_code, na_code, sea_code = code
        kb.insert(len(kb) - 2,
                  button([(f"{rewards}", f'{pre}:rewards:{eu_code}'),
                          (f"{eu_code}", f'{pre}:eu_code:{eu_code}'),
                          (f"{na_code}", f'{pre}:na_code:{eu_code}'),
                          (f"{sea_code}", f'{pre}:sea_code:{eu_code}')]))
    ut.edit(update, "Active Promotion Codes", InlineKeyboardMarkup(kb))


def code_menu(update, code_type, code_id):
    if code_type == "rewards":
        desc = "Rewards"
    elif code_type == "eu_code":
        desc = "EU Code"
    elif code_type == "na_code":
        desc = "NA Code"
    elif code_type == "sea_code":
        desc = "SEA Code"
    msg = f"<b>{desc}:</b> <code>{db.info_code(code_id, code_type)}</code>"
    kb = [button([("« Back to Active Codes", 'codes_menu'),
                  ("« Back to Menu", 'main_menu')])]
    ut.edit(update, msg, InlineKeyboardMarkup(kb))


def redeem_menu(update):
    kb = [button([("« Back to Active Codes", 'codes_menu'),
                  ("« Back to Menu", 'main_menu')])]
    ut.edit(update,
            ("Codes can be redeemed in:\n"
             "<b>Website:</b> https://genshin.mihoyo.com/en/gift\n"
             "<b>In-game:</b> Settings - Account - Redeem code."),
            InlineKeyboardMarkup(kb))


def settings_menu(update):
    kb = [button([("⏰ Warning Settings ⏰", 'settings_warn_menu')]),
          button([("📣 Notification Settings 📣", 'settings_promo_menu')]),
          button([("🌎 Timezone Settings 🌎", 'settings_timezone_menu')]),
          button([("« Back to Menu", 'main_menu')])]
    ut.edit(update, "Settings Menu", InlineKeyboardMarkup(kb))


def settings_warn_menu(update):
    uid = update.effective_message.chat.id
    cur_warn = db.get_warn(uid)
    if cur_warn != -1:
        _state(uid, ut.CMD.WARN, [int(cw) for cw in f"{cur_warn:03d}"])
        warn_icon = '🔔'
    else:
        _state(uid, ut.CMD.WARN, [int(cw) for cw in f"{ut.RESIN_MAX-10:03d}"])
        cur_warn = 'disabled'
        warn_icon = '🔕'
    st_warn = STATE[uid][ut.CMD.WARN]
    kb = [button([(f"Threshold: {cur_warn}", 'settings_warn_menu'),
                  (f"Resin Warnings: {warn_icon}", 'warn_toggle')]),
          button([("˄", 'warn_up0'),
                  ("˄", 'warn_up1'),
                  ("˄", 'warn_up2')]),
          button([(st_warn[0], 'nop'),
                  (st_warn[1], 'nop'),
                  (st_warn[2], 'nop')]),
          button([("˅", 'warn_down0'),
                  ("˅", 'warn_down1'),
                  ("˅", 'warn_down2')]),
          button([("Set Warning Threshold", 'warn_threshold')]),
          button([("« Back to Settings", 'settings_menu'),
                  ("« Back to Menu", 'main_menu')])]
    ut.edit(update, "Warnings Settings Menu", InlineKeyboardMarkup(kb))


def _warn_value(update):
    r0 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][0]['text'])
    r1 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][1]['text'])
    r2 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][2]['text'])
    value = int("".join([r0, r1, r2]))
    return value


def warn_toggle(update):
    uid = update.effective_message.chat.id
    cur_warn = db.get_warn(uid)
    if cur_warn == -1:
        db.set_warn(uid, _warn_value(update))
    else:
        db.unset_warn(uid)
    settings_warn_menu(update)


def warn_threshold(update):
    uid = update.effective_message.chat.id
    db.set_warn(uid, _warn_value(update))
    settings_warn_menu(update)


def warn_updown(update, up=True):
    uid = update.effective_message.chat.id
    cur_warn = db.get_warn(uid)
    if cur_warn != -1:
        _state(uid, ut.CMD.WARN, [int(cw) for cw in f"{cur_warn:03d}"])
    else:
        _state(uid, ut.CMD.WARN, [int(cw) for cw in f"{ut.RESIN_MAX-10:03d}"])
    st_warn = STATE[uid][ut.CMD.WARN]
    txt = 'warn_down'
    if up:
        txt = 'warn_up'
    pos = int(update.callback_query.data.split(txt)[1])
    if up:
        st_warn[pos] = (st_warn[pos] + 1) % 10
    else:
        st_warn[pos] = (st_warn[pos] - 1) % 10
    value = int(''.join(str(c) for c in st_warn))
    if value > 159:
        STATE[uid][ut.CMD.WARN] = [1, 5, 9]
    settings_warn_menu(update)


def settings_promo_menu(update):
    uid = update.effective_message.chat.id
    promo_icon = '🔔' if db.get_notifications(uid) == 1 else '🔕'
    kb = [button([(f"Promotion Code Notifications: {promo_icon}",
                   'promo_toggle')]),
          button([("« Back to Settings", 'settings_menu'),
                  ("« Back to Menu", 'main_menu')])]
    ut.edit(update, "Notifications Settings Menu", InlineKeyboardMarkup(kb))


def promo_toggle(update):
    uid = update.effective_message.chat.id
    if db.get_notifications(uid) == 1:
        db.unset_notifications(uid)
    else:
        db.set_notifications(uid)
    settings_promo_menu(update)


def settings_timezone_menu(update):
    uid = update.effective_message.chat.id
    bot_hour, bot_minutes = map(int, datetime.now()
                                .strftime("%H:%M").split(':'))
    tz_hour, tz_minutes = db.get_timezone(uid).split(':')
    if tz_hour == 'null':
        tz = 'disabled'
    else:
        tz = ut.normalize_timezone(tz_hour, tz_minutes)
    kb = [button([(f"Bot Hour: {bot_hour:02}:{bot_minutes:02}",
                   'settings_timezone_menu')]),
          button([(f"Current timezone: {tz}", 'timezone_menu')]),
          button([("« Back to Settings", 'settings_menu'),
                  ("« Back to Menu", 'main_menu')])]
    ut.edit(update, "Timezone Settings Menu", InlineKeyboardMarkup(kb))


def timezone_menu(update, modified=False):
    uid = update.effective_message.chat.id
    tz_hour, tz_minutes = db.get_timezone(uid).split(':')
    if tz_hour == 'null':
        tz = 'disabled'
        cur_hour, cur_minutes = ut.user_hour(0, 0, 0, 0)
    else:
        tz = ut.normalize_timezone(tz_hour, tz_minutes)
        cur_hour, cur_minutes = ut.user_hour(0, 0,
                                             int(tz_hour), int(tz_minutes))
    if modified:
        cur_hour, cur_minutes = STATE[uid][ut.CMD.TZ]
    else:
        _del_substate(uid, ut.CMD.TZ)
    kb = [button([(f"Current timezone: {tz}", 'timezone_menu')]),
          button([("˄", 'timezone_up0'),
                  ("˄", 'timezone_up1'),
                  ("˄", 'timezone_up2'),
                  ("˄", 'timezone_up3')]),
          button([(cur_hour // 10, 'nop'),
                  (cur_hour % 10, 'nop'),
                  (cur_minutes // 10, 'nop'),
                  (cur_minutes % 10, 'nop')]),
          button([("˅", 'timezone_down0'),
                  ("˅", 'timezone_down1'),
                  ("˅", 'timezone_down2'),
                  ("˅", 'timezone_down3')]),
          button([("Set Hour", 'timezone_set')]),
          button([("« Back to Timezone Settings", 'settings_timezone_menu'),
                  ("« Back to Menu", 'main_menu')])]
    if tz != 'disabled':
        kb.insert(len(kb) - 1,
                  button([("Disable Timezone", 'timezone_disable')]))
    ut.edit(update, "Timezone Menu", InlineKeyboardMarkup(kb))


def _timezone_value(update):
    r0 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][0]['text'])
    r1 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][1]['text'])
    r2 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][2]['text'])
    r3 = (update.callback_query.message.reply_markup
          .inline_keyboard[2][3]['text'])
    tz_hour = int("".join([r0, r1]))
    tz_minutes = int("".join([r2, r3]))
    return tz_hour, tz_minutes


def timezone_updown(update, up=True):
    uid = update.effective_message.chat.id
    txt = 'timezone_down'
    if up:
        txt = 'timezone_up'
    pos = int(update.callback_query.data.split(txt)[1])
    tz_hour, tz_minutes = _timezone_value(update)
    values = [tz_hour // 10, tz_hour % 10, tz_minutes // 10, tz_minutes % 10]
    if up:
        values[pos] = (values[pos] + 1) % 10
    else:
        values[pos] = (values[pos] - 1) % 10
    tz_hour = int("".join(str(v) for v in values[:2]))
    if tz_hour > 23:
        tz_hour = 23
    tz_minutes = int("".join(str(v) for v in values[2:]))
    if tz_minutes > 59:
        tz_minutes = 59
    _state(uid, ut.CMD.TZ, [tz_hour, tz_minutes])  # only update first time
    STATE[uid][ut.CMD.TZ] = [tz_hour, tz_minutes]
    timezone_menu(update, modified=True)


def timezone_disable(update):
    uid = update.effective_message.chat.id
    db.unset_timezone(uid)
    settings_timezone_menu(update)


def timezone_set(update):
    uid = update.effective_message.chat.id
    value_hour, value_minutes = _timezone_value(update)
    bot_hour, bot_minutes = map(int, datetime.now()
                                .strftime("%H:%M").split(':'))
    tz_hour = value_hour - bot_hour
    tz_minutes = value_minutes - bot_minutes
    db.set_timezone(uid, tz_hour, tz_minutes)
    settings_timezone_menu(update)
