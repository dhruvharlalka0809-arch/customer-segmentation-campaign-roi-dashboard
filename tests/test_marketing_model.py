import unittest

import pandas as pd

from src.marketing_model import (
    build_budget_reallocation,
    build_channel_summary,
    build_executive_memo,
    build_segment_summary,
    count_flags,
    load_campaign_data,
    score_campaign_data,
)


class MarketingModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_campaign_data("data/campaign_performance.csv")
        cls.scored = score_campaign_data(cls.raw)
        cls.segment_summary = build_segment_summary(cls.scored)

    def test_campaign_scores_are_bounded(self):
        self.assertTrue((self.scored["Campaign_Score"] >= 0).all())
        self.assertTrue((self.scored["Campaign_Score"] <= 100).all())

    def test_required_outputs_exist(self):
        for column in ["CAC", "ROAS", "ROI", "LTV_CAC", "Payback_Months", "Recommendation", "Risk_Flags"]:
            self.assertIn(column, self.scored.columns)

    def test_segment_summary_reconciles_spend(self):
        self.assertAlmostEqual(float(self.segment_summary["Spend"].sum()), float(self.scored["Spend"].sum()))

    def test_budget_plan_preserves_total_spend(self):
        budget_plan = build_budget_reallocation(self.segment_summary)
        self.assertAlmostEqual(float(budget_plan["Recommended_Spend"].sum()), float(self.segment_summary["Spend"].sum()))

    def test_channel_summary_reconciles_revenue(self):
        channel_summary = build_channel_summary(self.scored)
        self.assertAlmostEqual(float(channel_summary["Revenue"].sum()), float(self.scored["Revenue"].sum()))

    def test_top_segment_has_valid_recommendation(self):
        top = self.segment_summary.iloc[0]
        self.assertIn(top.Recommendation, {"Invest", "Optimize", "Pause / fix economics"})

    def test_count_flags(self):
        self.assertEqual(count_flags("None"), 0)
        self.assertEqual(count_flags("Weak LTV:CAC, Slow payback"), 2)

    def test_memo_mentions_budget_decision(self):
        channel_summary = build_channel_summary(self.scored)
        memo = build_executive_memo(self.scored, self.segment_summary, channel_summary)
        self.assertIn("Recommended action", memo)
        self.assertIn("Marketing ROI Executive Memo", memo)

    def test_missing_columns_raise_clear_error(self):
        with self.assertRaises(ValueError):
            score_campaign_data(pd.DataFrame({"Segment": ["A"]}))


if __name__ == "__main__":
    unittest.main()
