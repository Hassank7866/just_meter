import unittest
from datetime import datetime

from backend.compliance_engine import assess_violation_risk, evaluate_compliance


class ComplianceDecisionTests(unittest.TestCase):
    def setUp(self):
        self.vehicle = {
            "authorized_areas": "Mzd. Division|Mirpur Division",
            "duty_schedule": "09:00-17:00",
        }

    def test_lawful_area_and_duty_rules_are_reported(self):
        decision = evaluate_compliance(
            self.vehicle, "Mzd. Division", datetime.fromisoformat("2026-10-03T12:00:00+05:00"),
        )
        self.assertEqual(decision["status"], "LAWFUL")
        # No GPS location or geofence policy is configured in this test, so
        # polygon enforcement is explicitly not applicable to this capture.
        self.assertEqual(
            [rule["outcome"] for rule in decision["rules"]],
            ["PASS", "PASS", "NOT_APPLICABLE"],
        )
        self.assertEqual(decision["rules"][2]["rule_id"], "GPS_GEOFENCE")

    def test_multiple_failed_rules_are_combined(self):
        decision = evaluate_compliance(
            self.vehicle, "Poonch Division", datetime.fromisoformat("2026-10-03T20:00:00+05:00"),
        )
        self.assertEqual(decision["status"], "VIOLATION")
        self.assertEqual(decision["violation_criteria"], "UNAUTHORIZED_AREA|OUTSIDE_DUTY_HOURS")
        # The area and schedule violations remain independently reported while
        # the unconfigured GPS geofence rule is retained as not applicable.
        self.assertEqual(
            [rule["outcome"] for rule in decision["rules"]],
            ["FAIL", "FAIL", "NOT_APPLICABLE"],
        )
        self.assertEqual(decision["rules"][2]["rule_id"], "GPS_GEOFENCE")

    def test_overnight_schedule_is_evaluated_across_midnight(self):
        vehicle = self.vehicle | {"duty_schedule": "22:00-06:00"}
        decision = evaluate_compliance(
            vehicle, "Mzd. Division", datetime.fromisoformat("2026-10-03T02:00:00+05:00"),
        )
        self.assertEqual(decision["status"], "LAWFUL")

    def test_invalid_or_missing_policy_requires_review(self):
        vehicle = self.vehicle | {"duty_schedule": "not-a-schedule"}
        decision = evaluate_compliance(
            vehicle, "Poonch Division", datetime.fromisoformat("2026-10-03T20:00:00+05:00"),
        )
        self.assertEqual(decision["status"], "REVIEW_REQUIRED")
        self.assertEqual(decision["violation_criteria"], "UNAUTHORIZED_AREA")
        risk = assess_violation_risk(decision, prior_violation_count=5)
        self.assertEqual(risk["risk_level"], "PENDING_REVIEW")
        self.assertEqual(risk["risk_score"], 0)

    def test_unregistered_plate_is_not_enforcement_violation(self):
        decision = evaluate_compliance(
            None, "Mzd. Division", datetime.fromisoformat("2026-10-03T12:00:00+05:00"),
        )
        self.assertEqual(decision["status"], "UNREGISTERED")
        self.assertEqual(assess_violation_risk(decision)["risk_level"], "NOT_APPLICABLE")


class ViolationRiskTests(unittest.TestCase):
    def test_risk_score_is_explainable_and_increases_with_recurrence(self):
        violation = {
            "status": "VIOLATION",
            "violation_criteria": "UNAUTHORIZED_AREA|OUTSIDE_DUTY_HOURS",
        }
        first = assess_violation_risk(violation, prior_violation_count=0)
        repeat = assess_violation_risk(violation, prior_violation_count=2)
        self.assertEqual((first["risk_score"], first["risk_level"]), (60, "HIGH"))
        self.assertEqual((repeat["risk_score"], repeat["risk_level"]), (80, "CRITICAL"))
        self.assertTrue(any("Prior violations" in factor for factor in repeat["risk_factors"]))

    def test_risk_score_and_repeat_factor_are_capped(self):
        violation = {"status": "VIOLATION", "violation_criteria": "UNAUTHORIZED_AREA"}
        risk = assess_violation_risk(violation, prior_violation_count=100)
        self.assertEqual((risk["risk_score"], risk["risk_level"]), (65, "HIGH"))
        self.assertIn("Prior violations in 30 days (100): +30", risk["risk_factors"])


if __name__ == "__main__":
    unittest.main()
