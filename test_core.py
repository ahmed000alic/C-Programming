import os, sys, tempfile, unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import billing, predictor, app as flask_app  # noqa: E402


class BillingTests(unittest.TestCase):
    def test_slabs(self):
        t = {"slabs": [{"upto": 100, "rate": 0}, {"upto": 200, "rate": 2}, {"upto": None, "rate": 5}],
             "fixed_charge": 10, "tax_pct": 10}
        b = billing.calc_bill(250, t)
        self.assertEqual(b["energy"], 100 * 2 + 50 * 5)
        self.assertAlmostEqual(b["total"], (450 + 10) * 1.1, places=2)

    def test_validation(self):
        with self.assertRaises(ValueError):
            billing.validate_tariff({"slabs": [{"upto": 100, "rate": 1}], "fixed_charge": 0, "tax_pct": 0})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.c = flask_app.app.test_client()

    def test_demo_flow(self):
        self.assertEqual(self.c.get("/api/summary").json["empty"], True)
        self.assertEqual(self.c.post("/api/demo").status_code, 200)
        s = self.c.get("/api/summary").json
        self.assertTrue(s["forecast"]["ok"])
        self.assertEqual(len(s["forecast"]["points"]), 6)
        self.assertGreater(s["forecast"]["accuracy"], 80)

    def test_validation(self):
        self.assertEqual(self.c.post("/api/readings", json={"date": "2999-01-01", "kwh": 5}).status_code, 400)
        self.assertEqual(self.c.post("/api/readings", json={"date": "2024-01-01", "kwh": "x"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
