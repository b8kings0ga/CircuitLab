from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from scripts.verify_e2e_scenarios import load_scenarios, validate_scenario, verify_all


class E2EScenarioTests(unittest.TestCase):
    def test_all_catalog_backed_designs_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="circuitlab-e2e-test-") as temporary:
            report = verify_all(Path(temporary))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["physicalStatus"], "PHYSICAL_UNVERIFIED")
        self.assertEqual(report["scenarioCount"], 4)
        self.assertEqual({row["status"] for row in report["scenarios"]}, {"PASS"})
        self.assertEqual({tuple(row["hilStates"]) for row in report["scenarios"]}, {("PREPARED", "ARMED", "PASSED")})

    def test_unknown_catalog_pin_is_rejected(self) -> None:
        scenario = copy.deepcopy(load_scenarios()[0])
        scenario["nets"][0]["endpoints"][0] = "mcu:NOT_A_REAL_PIN"
        with self.assertRaisesRegex(ValueError, "unknown pin"):
            validate_scenario(scenario)

    def test_fixture_mapping_must_match_declared_net(self) -> None:
        scenario = copy.deepcopy(load_scenarios()[0])
        scenario["fixture"]["testPoints"][0]["logicalNet"] = "GND"
        with self.assertRaisesRegex(ValueError, "logical net does not match"):
            validate_scenario(scenario)

    def test_physical_verification_cannot_be_claimed(self) -> None:
        scenario = copy.deepcopy(load_scenarios()[0])
        scenario["verificationStatus"] = "PHYSICAL_VERIFIED"
        with self.assertRaisesRegex(ValueError, "PHYSICAL_UNVERIFIED"):
            validate_scenario(scenario)


if __name__ == "__main__":
    unittest.main()
