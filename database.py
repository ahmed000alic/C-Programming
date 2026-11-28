"""SQLite storage: readings, appliances, tariff settings."""
import json, os, random, sqlite3
from contextlib import closing
from datetime import timedelta

from billing import DEFAULT_TARIFF

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db"))


def _run(sql, args=(), many=False, fetch=False):
    with closing(sqlite3.connect(DB_PATH)) as c:
        c.row_factory = sqlite3.Row
        cur = c.executemany(sql, args) if many else c.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()] if fetch else None
        c.commit()
        return rows if fetch else cur.lastrowid


def init():
    for sql in (
        "CREATE TABLE IF NOT EXISTS readings (date TEXT PRIMARY KEY, kwh REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS appliances (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,"
        " watts REAL NOT NULL, qty INTEGER NOT NULL, hours REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    ):
        _run(sql)


# readings
def readings():
    return _run("SELECT date, kwh FROM readings ORDER BY date", fetch=True)


def save_readings(pairs):
    _run("INSERT INTO readings(date,kwh) VALUES(?,?) ON CONFLICT(date) DO UPDATE SET kwh=excluded.kwh",
         pairs, many=True)


def delete_reading(d):
    _run("DELETE FROM readings WHERE date=?", (d,))


def clear_all():
    _run("DELETE FROM readings")
    _run("DELETE FROM appliances")


# appliances
def appliances():
    return _run("SELECT * FROM appliances ORDER BY id", fetch=True)


def add_appliance(name, watts, qty, hours):
    return _run("INSERT INTO appliances(name,watts,qty,hours) VALUES(?,?,?,?)", (name, watts, qty, hours))


def delete_appliance(i):
    _run("DELETE FROM appliances WHERE id=?", (i,))


# tariff
def get_tariff():
    r = _run("SELECT value FROM settings WHERE key='tariff'", fetch=True)
    return json.loads(r[0]["value"]) if r else DEFAULT_TARIFF


def set_tariff(t):
    _run("INSERT INTO settings(key,value) VALUES('tariff',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
         (json.dumps(t),))


def seed_demo(today):
    """Two years of daily readings with a summer peak, plus a typical appliance list."""
    rng, start = random.Random(42), today - timedelta(days=730)
    season = {1: -1.5, 2: 0, 3: 3, 4: 7, 5: 9, 6: 6, 7: 3, 8: 3, 9: 2, 10: 0, 11: -1, 12: -2}
    pairs, d = [], start
    while d < today:
        kwh = 9 + season[d.month] + (1.5 if d.weekday() >= 5 else 0) + (d - start).days / 730 * 1.2 + rng.gauss(0, 1.2)
        pairs.append((d.isoformat(), round(max(2.0, kwh), 2)))
        d += timedelta(days=1)
    save_readings(pairs)
    if not appliances():
        for a in [("Air conditioner (1.5 ton)", 1500, 1, 5), ("Refrigerator", 150, 1, 10),
                  ("Ceiling fan", 75, 4, 10), ("LED lights", 12, 8, 6), ("Television", 100, 1, 4),
                  ("Washing machine", 500, 1, 1), ("Water pump", 750, 1, 1)]:
            add_appliance(*a)
    return len(pairs)
