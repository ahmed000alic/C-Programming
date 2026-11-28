"""Electricity Consumption Analysis and Bill Prediction System - Flask app."""
import csv, io
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, render_template, request

import billing, database as db, predictor

app = Flask(__name__)
db.init()


def bad(msg, code=400):
    return jsonify(error=msg), code


def parse_date(s):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"'{s}' isn't a date. Use YYYY-MM-DD or DD-MM-YYYY.")


def parse_kwh(v):
    try:
        k = float(v)
    except (TypeError, ValueError):
        raise ValueError("Units must be a number.")
    if not 0 <= k <= 1000:
        raise ValueError("Daily units must be between 0 and 1000.")
    return round(k, 2)


def appliance_rows():
    rows = db.appliances()
    for a in rows:
        a["kwh_month"] = round(a["watts"] * a["qty"] * a["hours"] * 30 / 1000, 1)
    return rows


@app.get("/")
def index():
    return render_template("index.html")


# ---------- overview ----------
@app.get("/api/summary")
def summary():
    today, rows, tariff = date.today(), db.readings(), db.get_tariff()
    if not rows:
        return jsonify(empty=True)
    months = predictor.monthly_totals(rows, today)
    cur = next((m for m in months if m["current"]), None)
    prev = next((m for m in months if m["ord"] == today.year * 12 + today.month - 2 and m["days"] >= 0.8 * m["dim"]), None)
    fc = predictor.forecast(months, 6, today)
    for p in fc["points"]:
        p["bill"] = billing.calc_bill(p["kwh"], tariff)["total"]
    history = [{"month": m["month"], "kwh": m["kwh"], "bill": billing.calc_bill(m["kwh"], tariff)["total"],
                "current": m["current"]} for m in months[-12:]]
    since = (today - timedelta(days=29)).isoformat()
    last30 = [r for r in rows if r["date"] >= since]
    avg30 = sum(r["kwh"] for r in last30) / len(last30) if last30 else 0

    kpi = {"avg_daily": round(avg30, 1), "logged_days": len(rows)}
    if cur:
        kpi.update(so_far=cur["actual"], days_logged=cur["days"], days_in_month=cur["dim"],
                   projected_kwh=cur["kwh"], projected_bill=billing.calc_bill(cur["kwh"], tariff)["total"])
    if prev:
        kpi.update(last_kwh=prev["kwh"], last_bill=billing.calc_bill(prev["kwh"], tariff)["total"])

    tips = []
    if cur and prev:
        ch = (cur["kwh"] - prev["kwh"]) / prev["kwh"] * 100
        tips.append({"tone": "up" if ch > 5 else "down" if ch < -5 else "flat",
                     "text": f"This month is on track for {cur['kwh']:.0f} units, "
                             f"{abs(ch):.0f}% {'above' if ch > 0 else 'below'} last month."})
    if cur:
        slabs = tariff["slabs"]
        for i, s in enumerate(slabs[:-1]):
            if s["upto"] > cur["kwh"]:
                gap = s["upto"] - cur["kwh"]
                if gap <= 40 and slabs[i + 1]["rate"] > s["rate"]:
                    tips.append({"tone": "warn", "text": f"You're about {gap:.0f} units from the next slab, where each unit "
                                 f"costs ₹{slabs[i + 1]['rate']:.2f} instead of ₹{s['rate']:.2f}."})
                break
    if last30:
        peak = max(last30, key=lambda r: r["kwh"])
        tips.append({"tone": "flat", "text": f"Your highest day in the last 30 was {parse_date(peak['date']).strftime('%d %b')} "
                                              f"at {peak['kwh']:.1f} units (average {avg30:.1f})."})
    apps = appliance_rows()
    if apps:
        top = max(apps, key=lambda a: a["kwh_month"])
        total = sum(a["kwh_month"] for a in apps)
        tips.append({"tone": "flat", "text": f"{top['name']} is your biggest appliance load, about "
                                              f"{top['kwh_month'] / total * 100:.0f}% of estimated usage."})
    return jsonify(empty=False, kpi=kpi, history=history, forecast=fc,
                   daily=last30, avg30=round(avg30, 2), insights=tips)


# ---------- readings ----------
@app.get("/api/readings")
def list_readings():
    return jsonify(db.readings()[::-1][:90])


@app.post("/api/readings")
def add_reading():
    b = request.get_json(silent=True) or {}
    try:
        d = parse_date(str(b.get("date", "")))
        if d > date.today():
            raise ValueError("Readings can't be dated in the future.")
        db.save_readings([(d.isoformat(), parse_kwh(b.get("kwh")))])
    except ValueError as e:
        return bad(str(e))
    return jsonify(ok=True)


@app.delete("/api/readings/<d>")
def remove_reading(d):
    db.delete_reading(d)
    return jsonify(ok=True)


@app.post("/api/readings/import")
def import_readings():
    text = (request.get_json(silent=True) or {}).get("csv", "")
    pairs, skipped = [], 0
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            skipped += bool(row)
            continue
        try:
            pairs.append((parse_date(row[0]).isoformat(), parse_kwh(row[1])))
        except ValueError:
            skipped += 1
    if not pairs:
        return bad("No valid rows found. Use two columns: date, units (kWh).")
    db.save_readings(pairs)
    return jsonify(imported=len(pairs), skipped=skipped)


@app.post("/api/demo")
def demo():
    return jsonify(imported=db.seed_demo(date.today()))


@app.delete("/api/data")
def clear():
    db.clear_all()
    return jsonify(ok=True)


# ---------- appliances ----------
@app.get("/api/appliances")
def list_appliances():
    rows, tariff = appliance_rows(), db.get_tariff()
    total = round(sum(a["kwh_month"] for a in rows), 1)
    bill = billing.calc_bill(total, tariff)["total"] if rows else 0
    for a in rows:
        a["share"] = round(a["kwh_month"] / total * 100, 1) if total else 0
        a["cost"] = round(bill * a["share"] / 100)
    return jsonify(items=rows, total_kwh=total, total_bill=bill)


@app.post("/api/appliances")
def add_appliance():
    b = request.get_json(silent=True) or {}
    try:
        name = str(b.get("name", "")).strip()
        watts, qty, hours = float(b["watts"]), int(b["qty"]), float(b["hours"])
    except (KeyError, TypeError, ValueError):
        return bad("Enter a name, wattage, quantity and hours per day.")
    if not name or watts <= 0 or qty < 1 or not 0 < hours <= 24:
        return bad("Wattage and quantity must be above zero, and hours per day between 0 and 24.")
    db.add_appliance(name[:60], watts, qty, hours)
    return jsonify(ok=True)


@app.delete("/api/appliances/<int:i>")
def remove_appliance(i):
    db.delete_appliance(i)
    return jsonify(ok=True)


# ---------- forecast & tariff ----------
@app.get("/api/forecast")
def forecast():
    try:
        horizon = min(max(int(request.args.get("horizon", 6)), 1), 12)
        reduce = min(max(float(request.args.get("reduce", 0)), 0), 60)
    except ValueError:
        return bad("Invalid parameters.")
    today, tariff = date.today(), db.get_tariff()
    fc = predictor.forecast(predictor.monthly_totals(db.readings(), today), horizon, today)
    for p in fc["points"]:
        p["bill"] = billing.calc_bill(p["kwh"], tariff)["total"]
        p["bill_reduced"] = billing.calc_bill(p["kwh"] * (1 - reduce / 100), tariff)["total"]
    return jsonify(fc)


@app.get("/api/tariff")
def get_tariff():
    return jsonify(db.get_tariff())


@app.put("/api/tariff")
def put_tariff():
    try:
        t = billing.validate_tariff(request.get_json(silent=True) or {})
    except ValueError as e:
        return bad(str(e))
    db.set_tariff(t)
    return jsonify(t)


@app.post("/api/bill")
def bill():
    try:
        units = float((request.get_json(silent=True) or {}).get("units"))
        if not 0 <= units <= 100000:
            raise ValueError
    except (TypeError, ValueError):
        return bad("Enter units between 0 and 100000.")
    return jsonify(billing.calc_bill(units, db.get_tariff()))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
