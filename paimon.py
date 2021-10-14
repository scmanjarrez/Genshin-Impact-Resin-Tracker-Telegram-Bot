#!/usr/bin/env python3
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, Updater)
from telegram.error import BadRequest
import paimon_cli as cli
import paimon_gui as gui
import database as db
import threads as th
import util as ut
import logging
import os


def button_handler(update, context):
    uid = ut.uid(update)
    query = update.callback_query
    try:
        query.answer()
    except BadRequest:
        pass

    if not db.banned(uid):
        if not db.cached(uid):
            ut.not_started_gui(update)
        else:
            if query.data == 'main_menu':
                gui.main_menu(update)
            elif query.data == 'resin_menu':
                gui.resin_menu(update)
            elif query.data == 'tracking_menu':
                gui.tracking_menu(update)
            elif query.data == 'tracking_start':
                gui.tracking_start(update, context)
            elif query.data == 'tracking_stop':
                gui.tracking_stop(update)
            elif query.data.startswith('tracking_up'):
                gui.tracking_updown(update)
            elif query.data.startswith('tracking_down'):
                gui.tracking_updown(update, up=False)
            elif query.data == 'spend_menu':
                gui.spend_menu(update)
            elif query.data.startswith('spend_r'):
                gui.spend_resin(update)
            elif query.data == 'refill_menu':
                gui.refill_menu(update)
            elif query.data.startswith('refill_up'):
                gui.refill_updown(update)
            elif query.data.startswith('refill_down'):
                gui.refill_updown(update, up=False)
            elif query.data == 'refill_r':
                gui.refill_resin(update)
            elif query.data == 'settings_menu':
                gui.settings_menu(update)
            elif query.data == 'settings_warn_menu':
                gui.settings_warn_menu(update)
            elif query.data == 'warn_toggle':
                gui.warn_toggle(update)
            elif query.data == 'warn_threshold':
                gui.warn_threshold(update)
            elif query.data.startswith('warn_up'):
                gui.warn_updown(update)
            elif query.data.startswith('warn_down'):
                gui.warn_updown(update, up=False)
            elif query.data == 'settings_timezone_menu':
                gui.settings_timezone_menu(update)
            elif query.data == 'timezone_menu':
                gui.timezone_menu(update)
            elif query.data == 'timezone_disable':
                gui.timezone_disable(update)
            elif query.data == 'timezone_set':
                gui.timezone_set(update)
            elif query.data.startswith('timezone_up'):
                gui.timezone_updown(update)
            elif query.data.startswith('timezone_down'):
                gui.timezone_updown(update, up=False)


def setup_handlers(dispatch, job_queue):
    start_handler = CommandHandler('start', cli.start,
                                   filters=~Filters.update.edited_message)
    dispatch.add_handler(start_handler)

    help_handler = CommandHandler('help', cli.bot_help,
                                  filters=~Filters.update.edited_message)
    dispatch.add_handler(help_handler)

    menu_handler = CommandHandler('menu', gui.menu,
                                  filters=~Filters.update.edited_message)
    dispatch.add_handler(menu_handler)

    resin_handler = CommandHandler('resin', cli.resin,
                                   filters=~Filters.update.edited_message)
    dispatch.add_handler(resin_handler)

    set_handler = CommandHandler('set', cli.set_resin,
                                 filters=~Filters.update.edited_message)
    dispatch.add_handler(set_handler)

    spend_handler = CommandHandler('spend', cli.spend,
                                   filters=~Filters.update.edited_message)
    dispatch.add_handler(spend_handler)

    refill_handler = CommandHandler('refill', cli.refill,
                                    filters=~Filters.update.edited_message)
    dispatch.add_handler(refill_handler)

    track_handler = CommandHandler('track', cli.track,
                                   filters=~Filters.update.edited_message)
    dispatch.add_handler(track_handler)

    warnings_handler = CommandHandler('warnings', cli.warnings,
                                      filters=~Filters.update.edited_message)
    dispatch.add_handler(warnings_handler)

    timezone_handler = CommandHandler('timezone', cli.timezone,
                                      filters=~Filters.update.edited_message)
    dispatch.add_handler(timezone_handler)

    cancel_handler = CommandHandler('cancel', cli.cancel,
                                    filters=~Filters.update.edited_message)
    dispatch.add_handler(cancel_handler)

    stop_handler = CommandHandler('stop', cli.stop,
                                  filters=~Filters.update.edited_message)
    dispatch.add_handler(stop_handler)

    announce_handler = CommandHandler('announce', cli.announce,
                                      filters=~Filters.update.edited_message)
    dispatch.add_handler(announce_handler)

    restart_handler = CommandHandler('restart', cli.restart,
                                     filters=~Filters.update.edited_message)
    dispatch.add_handler(restart_handler)

    text_handler = MessageHandler(
        Filters.text & ~Filters.update.edited_message, cli.text)
    dispatch.add_handler(text_handler)

    dispatch.add_handler(CallbackQueryHandler(button_handler))


def load_config():
    with open(".config", 'r') as f:
        config = {k: v for k, v in
                  [line.split('=') for line in f.read().splitlines()]}
    return config


if __name__ == '__main__':
    logging.basicConfig(format=('%(asctime)s - %(name)s - '
                                '%(levelname)s - %(message)s'),
                        level=logging.INFO)

    if os.path.isfile('.config'):
        config = load_config()
        db.setup_db()

        updater = Updater(token=config['apikey'], use_context=True)
        dispatcher = updater.dispatcher

        setup_handlers(dispatcher, updater.job_queue)

        ut.restore_trackings(updater.bot)

        updater.start_webhook(listen=config['listen'],
                              port=config['port'],
                              url_path=config['apikey'],
                              key=config['key'],
                              cert=config['cert'],
                              webhook_url=(f"https://"
                                           f"{config['ip']}:"
                                           f"{config['port']}/"
                                           f"{config['apikey']}"))
        updater.idle()

        ut.backup_trackings()
    else:
        print("File .config not found.")
