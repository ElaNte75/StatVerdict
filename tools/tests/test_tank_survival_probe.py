import unittest

from tools import tank_survival_probe as probe


class ProbeMathTests(unittest.TestCase):
    def test_spearman_of_same_and_reversed_orders(self) -> None:
        order = ["haste", "crit", "mastery", "versatility"]
        self.assertEqual(1.0, probe.spearman(order, order))
        self.assertEqual(-1.0, probe.spearman(order, list(reversed(order))))

    def test_taken_metrics_are_negated_into_benefit(self) -> None:
        run = {
            "dps": {"crit": 1.0, "haste": 3.0, "mastery": 2.0, "versatility": 0.5},
            "dtps": {"crit": -0.1, "haste": -0.2, "mastery": -0.4, "versatility": -0.3},
        }
        summary = probe.summarize([run, run], {"all": ["mastery", "versatility", "haste", "crit"]})
        self.assertEqual(["haste", "mastery", "crit", "versatility"], summary["metrics"]["dps"]["order"])
        self.assertEqual(["mastery", "versatility", "haste", "crit"], summary["metrics"]["dtps"]["order"])
        self.assertEqual(1.0, summary["agreement"]["dtps_seed_vs_seed"])
        self.assertEqual(1.0, summary["agreement"]["guide_all_vs_dtps"])

    def test_guide_orders_flatten_ties(self) -> None:
        priority = {"value": {"all": {"all": {"secondary": [["haste"], ["versatility"], ["mastery", "crit"]]}}}}
        self.assertEqual({"all": ["haste", "versatility", "mastery", "crit"]}, probe.guide_orders(priority))

    def test_six_tanks(self) -> None:
        self.assertEqual(6, len(probe.TANK_SPECS))


if __name__ == "__main__":
    unittest.main()
