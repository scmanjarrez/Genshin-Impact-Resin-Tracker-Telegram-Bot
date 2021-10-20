# SPDX-License-Identifier: MIT

# Copyright (c) 2021 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

from telegram.error import Unauthorized
from threading import Event, Thread
import database as db
import util as ut


THREADS = {}
UNSYNC = []


def del_thread(uid):
    if uid in THREADS:
        THREADS[uid][1].set()
        del THREADS[uid]


def is_tracked(uid):
    return uid in THREADS and THREADS[uid][0].is_alive()


def is_unsync(uid):
    return uid in UNSYNC and is_tracked(uid)


def new_thread(bot, uid, timer):
    del_thread(uid)
    flag = Event()
    thread = ResinThread(bot, uid, timer, flag)
    thread.start()
    THREADS[uid] = (thread, flag)
    if uid in UNSYNC:
        UNSYNC.remove(uid)


class ResinThread(Thread):
    def __init__(self, bot, uid, timer, flag):
        Thread.__init__(self)
        self.bot = bot
        self.uid = uid
        self.timer = timer
        self.flag = flag
        self.notified = False
        self.daemon = True

    def notify(self, msg):
        try:
            ut.send_bot(self.bot, self.uid, msg)
        except Unauthorized:
            ut.blocked(self.uid)
            self.flag.set()

    def run(self):
        while not self.flag.wait(self.timer):
            db.inc_resin(self.uid, 1)
            resin = db.get_resin(self.uid)
            warn = db.get_warn(self.uid)
            if warn != -1:
                if resin >= ut.RESIN_MAX:
                    self.notify("‼ Hey, you have hit the resin cap!")
                    self.flag.set()
                elif resin >= warn and not self.notified:
                    self.notify(f"❗ Hey, your resin is: {resin}")
                    self.notified = True
                elif resin < warn and self.notified:
                    self.notified = False
            self.timer = ut.RESIN_REGEN * 60
