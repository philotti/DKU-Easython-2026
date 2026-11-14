"""Exercise actual comparison functions against contract schemas and known prices."""
from copy import deepcopy
from decimal import getcontext
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from budget_transparency.analysis import compare  # noqa: E402


def read(name):
    return json.loads((ROOT / "tests/fixtures/contracts-v1" / name).read_text(encoding="utf-8"))


SCHEMA = Draft202012Validator(
    json.loads((ROOT / "docs/contracts/analysis.schema.json").read_text(encoding="utf-8")),
    format_checker=FormatChecker(),
)
spec = importlib.util.spec_from_file_location("compare_contract_checks", ROOT / "scripts/check_contracts.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.rows = read("purchases.json")
        self.market = read("market-prices.json")
        self.policy = read("policy.json")
        self.engine = compare.ComparisonEngine(self.policy, "synthetic-v1")

    def result(self, kind="agency", record_id="demo-A", engine=None):
        value = (engine or self.engine).compare_purchase(record_id, self.rows, self.market, kind)
        SCHEMA.validate(value)
        checks.validate_analysis(value)
        return value

    def extra(self, source="demo-B", **changes):
        row = deepcopy(next(r for r in self.rows if r["record_id"] == source))
        row.update(record_id="extra", agency_id="agency-extra", contract_id="extra-contract")
        row.update(changes)
        self.rows.append(row)
        return row

    def test_agency_known_answer_and_evidence(self):
        result = self.result()
        expected = read("analysis.json")
        for key in ("reference_unit_price", "difference", "difference_pct", "comparison_records",
                    "comparison_count", "agency_count", "evidence_ids", "target", "policy_id"):
            self.assertEqual(result[key], expected[key])
        self.assertEqual({r["id"] for r in result["excluded_records"]}, {"demo-unknown", "demo-other"})

    def test_market_known_answer_and_small_sample(self):
        result = self.result("market")
        self.assertEqual((result["reference_unit_price"], result["difference"], result["difference_pct"]),
                         ("110000", "40000", "36.36"))
        self.assertIsNone(result["agency_count"])
        self.assertTrue(any("표본" in s for s in result["limitations"]))

    def test_fixture_failure_scenarios(self):
        for record, fixture in (("demo-other", "analysis-insufficient.json"),
                                ("demo-unknown", "analysis-unknown.json")):
            with self.subTest(record=record):
                value = self.result(record_id=record)
                self.assertEqual(value["status"], read(fixture)["status"])
        self.rows[0]["status"] = "cancelled"
        self.assertEqual(self.result()["status"], "unavailable")
        self.rows[0]["status"] = "active"
        self.market = []
        self.assertEqual(self.result("market")["status"], "insufficient_data")

    def test_target_status_precedes_unknown_costs_and_empty_market(self):
        self.rows[0].update(status="unknown", tax_included=None)
        self.market = []
        for kind in ("agency", "market"):
            self.assertEqual(self.result(kind)["status"], "unavailable")

    def test_invalid_target_prices_and_quantities(self):
        for field in ("unit_price", "quantity"):
            for value in (None, "0", "-1"):
                with self.subTest(field=field, value=value):
                    saved = self.rows[0][field]
                    self.rows[0][field] = value
                    self.assertEqual(self.result()["status"], "unavailable")
                    self.rows[0][field] = saved

    def test_missing_identification_and_costs(self):
        for key in (*compare.PRODUCT_FIELDS[:4], *compare.COST_FIELDS):
            with self.subTest(key=key):
                saved = self.rows[0][key]
                self.rows[0][key] = None
                self.assertEqual(self.result()["status"], "conditions_unknown")
                self.rows[0][key] = saved

    def test_peer_exclusions(self):
        cases = [dict(agency_id="agency-A"), dict(status="cancelled"), dict(status="superseded"),
                 dict(status="unknown"), dict(unit_price="0"), dict(quantity="0"), dict(quantity="2"),
                 dict(item_id="different"), dict(model="different"), dict(specification="different"),
                 dict(unit="box"), dict(tax_included=None), dict(delivery_included=False),
                 dict(installation_included=True), dict(purchased_at="2026-10-31")]
        for change in cases:
            with self.subTest(change=change):
                self.extra(**change)
                value = self.result()
                self.assertEqual(value["comparison_count"], 3)
                self.assertTrue(any(r["id"] == "extra" and r["reason"] for r in value["excluded_records"]))
                self.rows.pop()

    def test_empty_peer_group(self):
        self.rows = self.rows[:1]
        value = self.result()
        self.assertEqual((value["status"], value["comparison_count"]), ("insufficient_data", 0))

    def test_record_and_agency_minimums_independent(self):
        self.policy["min_peer_records"] = 4
        engine = compare.ComparisonEngine(self.policy, "synthetic-v1")
        self.assertEqual(self.result(engine=engine)["status"], "insufficient_data")
        self.rows[2]["agency_id"] = self.rows[1]["agency_id"]
        value = self.result()
        self.assertEqual((value["status"], value["comparison_count"], value["agency_count"]),
                         ("insufficient_data", 3, 2))
        self.assertEqual(len(value["evidence_ids"]), 4)

    def test_negative_difference_and_half_up(self):
        self.rows[0]["unit_price"] = "90000"
        self.assertEqual((self.result()["difference"], self.result()["difference_pct"]), ("-30000", "-25.00"))
        for price, expected in (("120006", "0.01"), ("119994", "-0.01"), ("119999", "0.00")):
            self.rows[0]["unit_price"] = price
            self.assertEqual(self.result()["difference_pct"], expected)

    def test_even_median_and_zero_difference(self):
        self.extra(unit_price="160000")
        self.rows[0]["unit_price"] = "130000"
        result = self.result()
        self.assertEqual((result["reference_unit_price"], result["difference"], result["difference_pct"]),
                         ("130000", "0", "0.00"))

    def test_decimal_precision_and_caller_context(self):
        amount = "123456789012345678901234567890.125"
        for row in self.rows[:4]:
            row["unit_price"] = amount
        before = getcontext().copy()
        result = self.engine.compare_purchase("demo-A", self.rows, self.market, "agency")
        SCHEMA.validate(result)
        self.assertEqual((result["reference_unit_price"], result["difference"]), (amount, "0.000"))
        self.assertEqual(getcontext().prec, before.prec)

    def test_decimal_quantity_equality(self):
        self.rows[1]["quantity"] = "1.0"
        value = self.engine.compare_purchase("demo-A", self.rows, self.market, "agency")
        SCHEMA.validate(value)
        self.assertEqual((value["status"], value["comparison_count"]), ("comparable", 3))

    def test_period_boundaries_and_target_outside(self):
        self.rows[1]["purchased_at"] = self.policy["agency_period"]["from"]
        self.rows[2]["purchased_at"] = self.policy["agency_period"]["to"]
        self.assertEqual(self.result()["status"], "comparable")
        self.rows[0]["purchased_at"] = "2026-11-14"
        self.assertEqual(self.result()["status"], "unavailable")

    def test_source_duplicate_excluded_but_parent_contract_not_deduplicated(self):
        self.rows[1].update(source_id="source", source_record_id="order/00/1")
        dup = deepcopy(self.rows[1]); dup["record_id"] = "duplicate"
        self.rows.append(dup)
        value = self.result()
        self.assertEqual(value["comparison_count"], 3)
        self.assertTrue(any(r["id"] == "duplicate" for r in value["excluded_records"]))
        self.rows.pop()
        for row in self.rows[:4]:
            row["contract_id"] = "same-parent-contract"
        self.assertEqual(self.result()["comparison_count"], 3)

    def test_conflicting_source_duplicates_rejected(self):
        self.rows[1].update(source_id="source", source_record_id="order/00/1")
        dup = deepcopy(self.rows[1]); dup.update(record_id="duplicate", unit_price="999")
        self.rows.append(dup)
        with self.assertRaises(ValueError):
            self.result()

    def test_latest_seller_record_and_tie_id(self):
        original = self.market[0]
        old = deepcopy(original); old.update(market_price_id="old", checked_at="2026-11-01T00:00:00+09:00", price="1")
        tie = deepcopy(original); tie.update(market_price_id="z-tie", price="2")
        self.market.extend([old, tie])
        result = self.result("market")
        self.assertEqual(result["reference_unit_price"], "110000")
        self.assertEqual({r["id"] for r in result["excluded_records"]}, {"old", "z-tie"})

    def test_latest_unknown_does_not_fall_back_to_older_price(self):
        latest = deepcopy(self.market[0])
        latest.update(market_price_id="latest", checked_at="2026-11-03T00:00:00+09:00", tax_included=None)
        self.market.append(latest)
        self.assertEqual(self.result("market")["status"], "insufficient_data")

    def test_market_uses_seller_median_not_cheapest(self):
        for i, price in enumerate(("90000", "150000")):
            row = deepcopy(self.market[0])
            row.update(market_price_id=f"seller-{i}", seller_name=f"seller-{i}", price=price)
            self.market.append(row)
        result = self.result("market")
        self.assertEqual((result["reference_unit_price"], result["comparison_count"]), ("110000", 3))

    def test_market_korean_date_and_timezone_aware_latest(self):
        self.market[0]["checked_at"] = "2026-10-31T15:00:00Z"  # Nov 1 in Korea
        self.assertEqual(self.result("market")["status"], "comparable")
        self.market[0]["checked_at"] = "2026-11-13T15:00:00Z"  # Nov 14 in Korea
        self.assertEqual(self.result("market")["status"], "insufficient_data")

    def test_zero_market_price_and_unknown_conditions(self):
        for change in (dict(price="0"), dict(price="-1"), dict(price=None),
                       dict(tax_included=None), dict(unit="box"), dict(model="other")):
            saved = deepcopy(self.market)
            self.market[0].update(change)
            self.assertEqual(self.result("market")["status"], "insufficient_data")
            self.market = saved

    def test_no_mutation_and_order_independent(self):
        before = deepcopy((self.rows, self.market, self.policy))
        first = self.result()
        self.assertEqual((self.rows, self.market, self.policy), before)
        self.rows.reverse(); self.market.reverse()
        self.assertEqual(self.result(), first)
        first["target"]["unit_price"] = "1"
        first["comparison_records"][0]["unit_price"] = "1"
        self.assertEqual(self.result()["difference"], "30000")
        self.policy["min_peer_records"] = 100
        self.assertEqual(self.result()["status"], "comparable")

    def test_bad_requests_and_duplicate_ids(self):
        with self.assertRaises(compare.PurchaseNotFoundError):
            self.result(record_id="missing")
        with self.assertRaises(ValueError):
            self.result("other")
        self.rows.append(deepcopy(self.rows[1]))
        with self.assertRaises(ValueError):
            self.result()

    def test_reject_mixed_synthetic_data(self):
        self.rows[1]["synthetic"] = False
        with self.assertRaises(ValueError):
            self.result()
        self.rows[1]["synthetic"] = True
        self.market[0]["synthetic"] = False
        with self.assertRaises(ValueError):
            self.result("market")

    def test_explicit_initialization_and_no_file_access(self):
        with patch.object(compare, "_default_engine", None):
            with self.assertRaises(compare.AnalysisConfigurationError):
                compare.compare_purchase("demo-A", self.rows, self.market, "agency")
            with patch("builtins.open", side_effect=AssertionError("No file loading")):
                compare.configure_analysis(self.policy, "synthetic-v1")
                value = compare.compare_purchase("demo-A", self.rows, self.market, "agency")
            self.assertEqual(value["difference"], "30000")

    def test_invalid_policy_rejected(self):
        for changes in ({"min_peer_records": True}, {"min_peer_agencies": 0},
                        {"agency_period": {"from": "2026-11-13", "to": "2026-11-01"}},
                        {"quantity_rule": "any"}):
            policy = deepcopy(self.policy); policy.update(changes)
            with self.assertRaises(compare.AnalysisConfigurationError):
                compare.ComparisonEngine(policy, "synthetic-v1")
        with self.assertRaises(compare.AnalysisConfigurationError):
            compare.ComparisonEngine(None, "actual-v1")

    def test_actual_rows_unknown_even_with_explicit_test_policy(self):
        rows = json.loads((ROOT / "data/demo/purchases.json").read_text(encoding="utf-8"))
        policy = deepcopy(self.policy)
        policy.update(policy_id="test-only-actual-status", agency_period={"from": "2025-11-14", "to": "2026-11-13"})
        engine = compare.ComparisonEngine(policy, "test-only-actual-v1")
        unknown_rows = [row for row in rows if row["status"] == "unknown"]
        if not unknown_rows:
            self.skipTest("No unknown actual rows in the current dataset")
        for row in unknown_rows:
            for kind in ("agency", "market"):
                value = engine.compare_purchase(row["record_id"], rows, [], kind)
                SCHEMA.validate(value)
                self.assertEqual(value["status"], "unavailable")
                self.assertIsNone(value["difference"])


if __name__ == "__main__":
    unittest.main()
