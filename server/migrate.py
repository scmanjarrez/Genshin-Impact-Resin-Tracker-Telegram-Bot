#!/usr/bin/env python3
from contextlib import closing
import argparse
import sqlite3 as sql


def v1_info(v1):
    with closing(sql.connect(v1)) as db:
        with closing(db.cursor()) as cur:
            cur.execute('SELECT user_id, resin, warn, '
                        'notify_codes, custom_timezone, timezone '
                        'FROM users')
            return cur.fetchall()


def v2_info(v2, data):
    with closing(sql.connect(v2)) as db:
        with closing(db.cursor()) as cur:
            cur.executemany('INSERT INTO users '
                            '(uid, resin, warn, notifications, timezone) '
                            'VALUES (?, ?, ?, ?, ?)',
                            data)
            db.commit()


def main(args):
    info1 = v1_info(args.input)
    info2 = []
    for v1 in info1:
        uid, resin, warn, notifications, tz1, tz2 = v1
        if tz1 == 0:
            timezone = "null:null"
        elif tz1 != 1:
            timezone = f"{tz1}:00"
        else:
            timezone = f"{tz2}:00"
        info2.append((uid, resin, warn, notifications, timezone))

    v2_info(args.output, info2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Migrate paimon database v1 to v2.')

    parser.add_argument('-i', '--input', required=True,
                        help='Input database (v1)')
    parser.add_argument('-o', '--output', required=True,
                        help='Output database (v2)')

    args = parser.parse_args()
    main(args)
