from telegram.error import Unauthorized
from threading import Event, Thread
from contextlib import closing
import database as db
import util as ut
import requests
import html
import re


THREADS = {}
UNSYNC = []
CODE_CHECK_HOUR = 168
URL = "https://www.gensh.in/events/promotion-codes"
TBODY = re.compile(r"<tbody[^>]*>(.*?)</tbody>", re.IGNORECASE | re.DOTALL)
TR = re.compile(r"<tr>\s*(.*?)\s*</tr>")
TD = re.compile(r"<td>\s*(.*?)\s*</td>")
CHUNK = 1024


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


def new_promo_thread(job_queue):
    flag = Event()
    thread = PromoCodeThread(job_queue, flag)
    thread.start()


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


def scrape_genshin():
    table = ""
    with closing(requests.get(URL, stream=True)) as req:
        for chunk in req.iter_content(chunk_size=CHUNK, decode_unicode=True):
            table = "".join([table, chunk])
            match = TBODY.search(table)
            if match:
                tbody = html.unescape(match.group(1))
                tr = TR.findall(tbody)
                codes = [TD.findall(row) for row in tr]
                return codes


class PromoCodeThread(Thread):
    def __init__(self, queue, flag):
        Thread.__init__(self)
        self.queue = queue
        self.flag = flag
        self.row_elem = 6
        self.next_req = 5
        self.daemon = True

    def run(self):
        while not self.flag.wait(self.next_req):
            self.next_req = CODE_CHECK_HOUR * 60 * 60
            codes = scrape_genshin()
            for c in codes:
                _, rewards, expired, eu_code, na_code, sea_code = c
                db.add_code(rewards, expired, eu_code, na_code, sea_code)
            ut.notify_codes(self.queue)
