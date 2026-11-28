"""Slab-based electricity bill calculation.

The default tariff is illustrative. Edit it from the Tariff page in the app
so it matches your electricity board's current domestic rates.
"""

DEFAULT_TARIFF = {
    "slabs": [
        {"upto": 100, "rate": 0.0},
        {"upto": 200, "rate": 2.35},
        {"upto": 400, "rate": 4.70},
        {"upto": 500, "rate": 6.30},
        {"upto": 600, "rate": 8.40},
        {"upto": 800, "rate": 9.45},
        {"upto": 1000, "rate": 10.50},
        {"upto": None, "rate": 11.55},
    ],
    "fixed_charge": 50.0,
    "tax_pct": 5.0,
}


def validate_tariff(t):
    """Return a cleaned tariff dict or raise ValueError with a readable message."""
    try:
        slabs = [{"upto": None if s.get("upto") in (None, "") else float(s["upto"]),
                  "rate": float(s["rate"])} for s in t["slabs"]]
        fixed, tax = float(t["fixed_charge"]), float(t["tax_pct"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Tariff is incomplete. Check every slab, the fixed charge and the tax.")
    if not slabs:
        raise ValueError("Add at least one slab.")
    if slabs[-1]["upto"] is not None:
        raise ValueError("Leave the last slab's upper limit empty so it covers all higher usage.")
    prev = 0
    for s in slabs[:-1]:
        if s["upto"] is None or s["upto"] <= prev:
            raise ValueError("Slab limits must increase from one slab to the next.")
        prev = s["upto"]
    if any(s["rate"] < 0 for s in slabs) or fixed < 0 or not 0 <= tax <= 100:
        raise ValueError("Rates and charges can't be negative, and tax must be 0-100%.")
    return {"slabs": slabs, "fixed_charge": fixed, "tax_pct": tax}


def calc_bill(units, tariff):
    remaining = max(0.0, float(units))
    prev, energy, lines = 0.0, 0.0, []
    for s in tariff["slabs"]:
        cap = s["upto"]
        span = remaining if cap is None else cap - prev
        used = min(remaining, span)
        if used > 0:
            amount = used * s["rate"]
            energy += amount
            lines.append({"from": prev, "to": cap, "units": round(used, 2),
                          "rate": s["rate"], "amount": round(amount, 2)})
        remaining -= used
        if cap is not None:
            prev = cap
        if remaining <= 0:
            break
    fixed = tariff["fixed_charge"]
    tax = (energy + fixed) * tariff["tax_pct"] / 100
    return {"units": round(float(units), 2), "lines": lines, "energy": round(energy, 2),
            "fixed": round(fixed, 2), "tax": round(tax, 2),
            "total": round(energy + fixed + tax, 2)}
