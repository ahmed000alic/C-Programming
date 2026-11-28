"""Monthly aggregation and consumption forecasting.

Model: Ridge regression on a linear trend, plus month-of-year sine/cosine terms
once 12+ complete months exist (so it can learn seasonality, e.g. summer peaks).
Accuracy is measured with leave-one-out cross-validation.
"""
import calendar
from datetime import date

import numpy as np
from sklearn.linear_model import Ridge


def monthly_totals(rows, today):
    by = {}
    for r in rows:
        d = date.fromisoformat(r["date"])
        by.setdefault((d.year, d.month), []).append(r["kwh"])
    out = []
    for (y, m), v in sorted(by.items()):
        dim, n = calendar.monthrange(y, m)[1], len(v)
        current = (y, m) == (today.year, today.month)
        out.append({"month": f"{y}-{m:02d}", "ord": y * 12 + m - 1, "days": n, "dim": dim,
                    "actual": round(sum(v), 1), "kwh": round(sum(v) / n * dim, 1),  # projected for partial months
                    "current": current, "complete": (not current) and n >= 0.8 * dim})
    return out


def _features(ords, base, seasonal):
    o = np.asarray(ords, float)
    cols = [o - base]
    if seasonal:
        ang = 2 * np.pi * (o % 12) / 12
        cols += [np.sin(ang), np.cos(ang)]
    return np.column_stack(cols)


def forecast(months, horizon, today):
    train = [m for m in months if m["complete"]]
    if len(train) < 2:
        return {"ok": False, "points": [], "reason": "Add at least 2 complete months of readings to unlock forecasts."}
    o = np.array([m["ord"] for m in train])
    y = np.array([m["kwh"] for m in train])
    base, seasonal = o[0], len(train) >= 12

    def fit(idx):
        return Ridge(alpha=0.5).fit(_features(o[idx], base, seasonal), y[idx])

    idx = np.arange(len(y))
    model = fit(idx)
    mae = None
    if len(y) >= 6:
        errs = np.array([y[i] - fit(np.delete(idx, i)).predict(_features([o[i]], base, seasonal))[0] for i in idx])
        mae, spread = float(np.abs(errs).mean()), float(errs.std())
    else:
        spread = float((y - model.predict(_features(o, base, seasonal))).std()) or 0.1 * float(y.mean())
    start = today.year * 12 + today.month  # first month after the current one
    ords = [start + i for i in range(horizon)]
    pred = np.maximum(model.predict(_features(ords, base, seasonal)), 0)
    points = []
    for ordinal, p in zip(ords, pred):
        points.append({"month": f"{ordinal // 12}-{ordinal % 12 + 1:02d}", "kwh": round(float(p), 1),
                       "low": round(max(0.0, float(p) - 1.28 * spread), 1), "high": round(float(p) + 1.28 * spread, 1)})
    return {"ok": True, "points": points, "trained_on": len(train),
            "model": "Trend + seasonality" if seasonal else "Linear trend",
            "mae": None if mae is None else round(mae, 1),
            "accuracy": None if mae is None else round(max(0.0, 100 * (1 - mae / float(y.mean()))), 1)}
