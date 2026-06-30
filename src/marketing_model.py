from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


REQUIRED_COLUMNS = {
    "Month",
    "Segment",
    "Channel",
    "Campaign",
    "Spend",
    "Impressions",
    "Clicks",
    "Leads",
    "MQLs",
    "Customers",
    "Revenue",
    "Gross_Margin",
    "Retention_Rate",
}


@dataclass(frozen=True)
class MarketingWeights:
    roi: float = 0.30
    ltv_cac: float = 0.25
    conversion: float = 0.20
    payback: float = 0.15
    retention: float = 0.10


def load_campaign_data(path: str) -> pd.DataFrame:
    return normalize_campaign_data(pd.read_csv(path))


def normalize_campaign_data(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    output = df.copy()
    output["Month"] = pd.to_datetime(output["Month"], errors="coerce")
    numeric_columns = REQUIRED_COLUMNS.difference({"Month", "Segment", "Channel", "Campaign"})
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="coerce")

    output = output.dropna(subset=["Month", "Segment", "Channel", "Campaign", "Spend", "Revenue"])
    output["Gross_Margin"] = output["Gross_Margin"].clip(lower=0.0, upper=1.0)
    output["Retention_Rate"] = output["Retention_Rate"].clip(lower=0.0, upper=0.99)
    return output.reset_index(drop=True)


def score_campaign_data(df: pd.DataFrame, weights: MarketingWeights = MarketingWeights()) -> pd.DataFrame:
    data = normalize_campaign_data(df)
    output = data.copy()
    output["CTR"] = safe_divide(output["Clicks"], output["Impressions"])
    output["Click_To_Lead"] = safe_divide(output["Leads"], output["Clicks"])
    output["Lead_To_MQL"] = safe_divide(output["MQLs"], output["Leads"])
    output["MQL_To_Customer"] = safe_divide(output["Customers"], output["MQLs"])
    output["Lead_To_Customer"] = safe_divide(output["Customers"], output["Leads"])
    output["CAC"] = safe_divide(output["Spend"], output["Customers"])
    output["CPL"] = safe_divide(output["Spend"], output["Leads"])
    output["ROAS"] = safe_divide(output["Revenue"], output["Spend"])
    output["Gross_Profit"] = output["Revenue"] * output["Gross_Margin"]
    output["Contribution"] = output["Gross_Profit"] - output["Spend"]
    output["ROI"] = safe_divide(output["Contribution"], output["Spend"])
    output["Monthly_GP_Per_Customer"] = safe_divide(output["Gross_Profit"], output["Customers"])
    output["Expected_Lifetime_Months"] = 1 / (1 - output["Retention_Rate"])
    output["LTV"] = output["Monthly_GP_Per_Customer"] * output["Expected_Lifetime_Months"]
    output["LTV_CAC"] = safe_divide(output["LTV"], output["CAC"])
    output["Payback_Months"] = safe_divide(output["CAC"], output["Monthly_GP_Per_Customer"])
    output["Campaign_Score"] = score_rows(output, weights)
    output["Risk_Flags"] = output.apply(build_risk_flags, axis=1)
    output["Recommendation"] = output.apply(classify_campaign, axis=1)
    return output.sort_values("Campaign_Score", ascending=False).reset_index(drop=True)


def build_segment_summary(scored: pd.DataFrame, weights: MarketingWeights = MarketingWeights()) -> pd.DataFrame:
    summary = scored.groupby("Segment", as_index=False).agg(
        Spend=("Spend", "sum"),
        Revenue=("Revenue", "sum"),
        Gross_Profit=("Gross_Profit", "sum"),
        Contribution=("Contribution", "sum"),
        Impressions=("Impressions", "sum"),
        Clicks=("Clicks", "sum"),
        Leads=("Leads", "sum"),
        MQLs=("MQLs", "sum"),
        Customers=("Customers", "sum"),
        Retention_Rate=("Retention_Rate", "mean"),
    )
    summary["CTR"] = safe_divide(summary["Clicks"], summary["Impressions"])
    summary["Lead_To_Customer"] = safe_divide(summary["Customers"], summary["Leads"])
    summary["CAC"] = safe_divide(summary["Spend"], summary["Customers"])
    summary["ROAS"] = safe_divide(summary["Revenue"], summary["Spend"])
    summary["ROI"] = safe_divide(summary["Contribution"], summary["Spend"])
    summary["Monthly_GP_Per_Customer"] = safe_divide(summary["Gross_Profit"], summary["Customers"])
    summary["Expected_Lifetime_Months"] = 1 / (1 - summary["Retention_Rate"].clip(upper=0.99))
    summary["LTV"] = summary["Monthly_GP_Per_Customer"] * summary["Expected_Lifetime_Months"]
    summary["LTV_CAC"] = safe_divide(summary["LTV"], summary["CAC"])
    summary["Payback_Months"] = safe_divide(summary["CAC"], summary["Monthly_GP_Per_Customer"])
    summary["Segment_Score"] = score_rows(summary, weights)
    summary["Risk_Flags"] = summary.apply(build_risk_flags, axis=1)
    summary["Recommendation"] = summary.apply(classify_segment, axis=1)
    return summary.sort_values("Segment_Score", ascending=False).reset_index(drop=True)


def build_channel_summary(scored: pd.DataFrame) -> pd.DataFrame:
    summary = scored.groupby("Channel", as_index=False).agg(
        Spend=("Spend", "sum"),
        Revenue=("Revenue", "sum"),
        Contribution=("Contribution", "sum"),
        Customers=("Customers", "sum"),
        Leads=("Leads", "sum"),
    )
    summary["CAC"] = safe_divide(summary["Spend"], summary["Customers"])
    summary["ROAS"] = safe_divide(summary["Revenue"], summary["Spend"])
    summary["ROI"] = safe_divide(summary["Contribution"], summary["Spend"])
    summary["Lead_To_Customer"] = safe_divide(summary["Customers"], summary["Leads"])
    return summary.sort_values("Contribution", ascending=False).reset_index(drop=True)


def build_budget_reallocation(segment_summary: pd.DataFrame) -> pd.DataFrame:
    output = segment_summary[["Segment", "Spend", "Revenue", "Contribution", "Segment_Score", "ROI", "LTV_CAC"]].copy()
    total_spend = float(output["Spend"].sum())
    opportunity = (
        output["Segment_Score"].clip(lower=0)
        * output["ROI"].clip(lower=0.01)
        * output["LTV_CAC"].clip(lower=0.25)
    )
    if float(opportunity.sum()) == 0:
        output["Recommended_Spend"] = output["Spend"]
    else:
        output["Recommended_Spend"] = total_spend * opportunity / opportunity.sum()
    output["Budget_Change"] = output["Recommended_Spend"] - output["Spend"]
    output["Budget_Action"] = output["Budget_Change"].apply(classify_budget_action)
    return output.sort_values("Budget_Change", ascending=False).reset_index(drop=True)


def build_executive_memo(scored: pd.DataFrame, segment_summary: pd.DataFrame, channel_summary: pd.DataFrame) -> str:
    top_segment = segment_summary.iloc[0]
    weak_segment = segment_summary.iloc[-1]
    top_channel = channel_summary.iloc[0]
    total_spend = float(scored["Spend"].sum())
    total_revenue = float(scored["Revenue"].sum())
    total_contribution = float(scored["Contribution"].sum())
    blended_cac = safe_scalar(total_spend, float(scored["Customers"].sum()))
    blended_roi = safe_scalar(total_contribution, total_spend)
    blended_roas = safe_scalar(total_revenue, total_spend)
    invest_segments = int((segment_summary["Recommendation"] == "Invest").sum())
    optimize_segments = int((segment_summary["Recommendation"] == "Optimize").sum())
    pause_segments = int((segment_summary["Recommendation"] == "Pause / fix economics").sum())

    return f"""### Marketing ROI Executive Memo

**Portfolio readout:** The campaign portfolio generated {format_money(total_revenue)} of revenue on {format_money(total_spend)} of spend, with {blended_roas:.1f}x ROAS, {blended_roi:.1%} contribution ROI, and blended CAC of {format_money(blended_cac)}.

**Best segment:** {top_segment.Segment} is the strongest segment with a {float(top_segment.Segment_Score):.1f}/100 score, {float(top_segment.ROI):.1%} ROI, {float(top_segment.LTV_CAC):.1f}x LTV:CAC, and {float(top_segment.Payback_Months):.1f} month payback.

**Weakest segment:** {weak_segment.Segment} needs review because it screens at {float(weak_segment.Segment_Score):.1f}/100 with flags: {weak_segment.Risk_Flags}.

**Channel readout:** {top_channel.Channel} produced the highest contribution at {format_money(float(top_channel.Contribution))}.

**Decision summary:** {invest_segments} segment(s) should receive incremental budget, {optimize_segments} should be optimized, and {pause_segments} should be paused or fixed before scaling.

**Recommended action:** Shift budget toward segments with strong contribution ROI and LTV:CAC, reduce spend where payback is slow or CAC is above customer value, and use the funnel diagnostics to locate whether the issue is audience quality, lead conversion, or sales handoff.
"""


def score_rows(df: pd.DataFrame, weights: MarketingWeights) -> pd.Series:
    total_weight = weights.roi + weights.ltv_cac + weights.conversion + weights.payback + weights.retention
    total_weight = total_weight or 1.0
    return (
        score_positive(df["ROI"], -0.40, 1.20) * weights.roi
        + score_positive(df["LTV_CAC"], 0.75, 4.00) * weights.ltv_cac
        + score_positive(df["Lead_To_Customer"], 0.02, 0.16) * weights.conversion
        + score_negative(df["Payback_Months"], 1.0, 12.0) * weights.payback
        + score_positive(df["Retention_Rate"], 0.60, 0.92) * weights.retention
    ) / total_weight


def classify_campaign(row: pd.Series) -> str:
    score = float(row["Campaign_Score"])
    flags = count_flags(str(row["Risk_Flags"]))
    if score >= 72 and flags <= 1:
        return "Scale"
    if score < 45 or flags >= 3:
        return "Pause / fix economics"
    return "Optimize"


def classify_segment(row: pd.Series) -> str:
    score = float(row["Segment_Score"])
    flags = count_flags(str(row["Risk_Flags"]))
    if score >= 72 and flags <= 1:
        return "Invest"
    if score < 45 or flags >= 3:
        return "Pause / fix economics"
    return "Optimize"


def build_risk_flags(row: pd.Series) -> str:
    flags = []
    if float(row["ROI"]) < 0:
        flags.append("Negative contribution ROI")
    if float(row["LTV_CAC"]) < 1.5:
        flags.append("Weak LTV:CAC")
    if float(row["Payback_Months"]) > 9:
        flags.append("Slow payback")
    if float(row["Lead_To_Customer"]) < 0.04:
        flags.append("Low lead conversion")
    if float(row["Retention_Rate"]) < 0.70:
        flags.append("Retention risk")
    return ", ".join(flags) if flags else "None"


def classify_budget_action(change: float) -> str:
    if change > 5000:
        return "Increase budget"
    if change < -5000:
        return "Reduce budget"
    return "Hold"


def count_flags(flags: str) -> int:
    if flags == "None":
        return 0
    return sum(1 for flag in flags.split(",") if flag.strip())


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator / denominator.replace(0, pd.NA)
    return result.fillna(0.0).replace([float("inf"), float("-inf")], 0.0)


def safe_scalar(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def score_positive(series: pd.Series, floor: float, ceiling: float) -> pd.Series:
    return ((series - floor) / (ceiling - floor) * 100).clip(lower=0, upper=100)


def score_negative(series: pd.Series, floor: float, ceiling: float) -> pd.Series:
    return (100 - ((series - floor) / (ceiling - floor) * 100)).clip(lower=0, upper=100)


def format_money(value: float) -> str:
    return f"${value:,.0f}"
