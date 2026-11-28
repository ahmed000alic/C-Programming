# Watt Ledger: Electricity Consumption Analysis and Bill Prediction System

A full-stack web app that records daily meter readings, analyses consumption, forecasts future
usage with machine learning and converts it into a bill using a configurable slab tariff.

## Features
- **Overview**: predicted next-month bill (odometer display), month-to-date progress, 12-month history, 30-day trend, plain-language insights (slab warnings, month-on-month change, peak day).
- **Forecast**: 3/6/12-month predictions with an 80% likely range, leave-one-out accuracy score, and a "cut usage by X%" savings what-if.
- **Meter readings**: add/update daily units, import CSV (`date,units`; dates as `YYYY-MM-DD` or `DD-MM-YYYY`), delete.
- **Appliances**: estimate monthly units, share and cost per appliance with a doughnut chart.
- **Tariff and calculator**: edit slabs, fixed charge and tax; compute a bill with a line-by-line breakdown.

## Tech stack
| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask, SQLite (stdlib `sqlite3`) |
| ML | scikit-learn Ridge regression (trend + month-of-year sine/cosine seasonality), NumPy |
| Frontend | HTML, CSS, vanilla JavaScript, Chart.js (bundled in `static/js`, works offline except Google Fonts) |

## Run it
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                   # open http://127.0.0.1:5000
```
Click **Load sample data** on the first screen to explore with two years of demo readings.

Run tests: `python -m unittest tests.test_core`

## Project structure
```
app.py          Flask routes (REST API + page)
billing.py      Slab tariff validation and bill calculation
predictor.py    Monthly aggregation, Ridge forecast, cross-validated accuracy
database.py     SQLite access and demo data
templates/      index.html (single-page UI)
static/         css/style.css, js/app.js, js/chart.umd.js
tests/          Unit and API tests
```

## How the prediction works
1. Daily readings are grouped by month; partial months are scaled to a full month.
2. With 2-11 complete months the model fits a linear trend. With 12+ it adds seasonality so recurring peaks (e.g. summer cooling) are learned.
3. Accuracy comes from leave-one-out cross-validation (each month is predicted from all the others); the residual spread gives the 80% range.
4. Predicted units go through the slab tariff to produce the bill.

## API
`GET /api/summary`, `GET|POST /api/readings`, `DELETE /api/readings/<date>`, `POST /api/readings/import`,
`GET|POST /api/appliances`, `DELETE /api/appliances/<id>`, `GET /api/forecast?horizon=6&reduce=10`,
`GET|PUT /api/tariff`, `POST /api/bill`, `POST /api/demo`, `DELETE /api/data`

## Note on tariff
The default slabs are sample rates. Update them on the Tariff page to match your electricity board's current domestic tariff.
