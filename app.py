import pandas as pd
import streamlit as st

from src.marketing_model import (
    MarketingWeights,
    build_budget_reallocation,
    build_channel_summary,
    build_executive_memo,
    build_segment_summary,
    format_money,
    load_campaign_data,
    score_campaign_data,
)


def format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(lambda value: f"{value:.1%}")
    return output


def format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(lambda value: format_money(float(value)))
    return output


def format_number_columns(df: pd.DataFrame, columns: list[str], suffix: str = "") -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(lambda value: f"{value:,.1f}{suffix}")
    return output


st.set_page_config(
    page_title="Campaign ROI & Customer Segmentation Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)


@st.cache_data
def load_sample_campaigns() -> pd.DataFrame:
    return load_campaign_data("data/campaign_performance.csv")


st.title("Customer Segmentation & Campaign ROI Dashboard")
st.caption("Prioritize marketing spend by segment economics, funnel quality, CAC, LTV:CAC, payback, and contribution ROI.")

with st.sidebar:
    st.header("Campaign Controls")
    uploaded_file = st.file_uploader("Upload campaign performance CSV", type="csv")
    active_data = pd.read_csv(uploaded_file) if uploaded_file else load_sample_campaigns()

    segment_filter = st.multiselect("Segment filter", sorted(active_data["Segment"].dropna().unique()))
    channel_filter = st.multiselect("Channel filter", sorted(active_data["Channel"].dropna().unique()))
    st.caption("No selections = full portfolio.")

    st.header("Scoring Weights")
    roi_weight = st.slider("Contribution ROI", 0.00, 0.50, 0.30, 0.01)
    ltv_cac_weight = st.slider("LTV:CAC", 0.00, 0.50, 0.25, 0.01)
    conversion_weight = st.slider("Lead conversion", 0.00, 0.40, 0.20, 0.01)
    payback_weight = st.slider("Payback speed", 0.00, 0.35, 0.15, 0.01)
    retention_weight = st.slider("Retention quality", 0.00, 0.30, 0.10, 0.01)

raw_weights = {
    "roi": roi_weight,
    "ltv_cac": ltv_cac_weight,
    "conversion": conversion_weight,
    "payback": payback_weight,
    "retention": retention_weight,
}
total_weight = sum(raw_weights.values()) or 1.0
weights = MarketingWeights(**{key: value / total_weight for key, value in raw_weights.items()})

try:
    filtered_data = active_data.copy()
    if segment_filter:
        filtered_data = filtered_data.loc[filtered_data["Segment"].isin(segment_filter)]
    if channel_filter:
        filtered_data = filtered_data.loc[filtered_data["Channel"].isin(channel_filter)]
    if filtered_data.empty:
        st.warning("No campaigns match the selected filters.")
        st.stop()

    scored = score_campaign_data(filtered_data, weights)
    segment_summary = build_segment_summary(scored, weights)
    channel_summary = build_channel_summary(scored)
    budget_plan = build_budget_reallocation(segment_summary)
except Exception as exc:
    st.error(f"Could not score campaign data: {exc}")
    st.stop()

total_spend = float(scored["Spend"].sum())
total_revenue = float(scored["Revenue"].sum())
total_contribution = float(scored["Contribution"].sum())
total_customers = float(scored["Customers"].sum())
blended_cac = total_spend / total_customers if total_customers else 0.0
roas = total_revenue / total_spend if total_spend else 0.0
roi = total_contribution / total_spend if total_spend else 0.0
top_segment = segment_summary.iloc[0]

hero = st.columns(5)
hero[0].metric("Revenue", format_money(total_revenue))
hero[1].metric("Contribution ROI", f"{roi:.1%}")
hero[2].metric("ROAS", f"{roas:.1f}x")
hero[3].metric("Blended CAC", format_money(blended_cac))
hero[4].metric("Top Segment", str(top_segment.Segment))

st.divider()

portfolio_tab, segment_tab, channel_tab, budget_tab, memo_tab, data_tab = st.tabs(
    ["Portfolio", "Segments", "Channels", "Budget Plan", "Memo", "Data"]
)

with portfolio_tab:
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Monthly Revenue and Spend")
        monthly = scored.groupby("Month", as_index=False).agg(Revenue=("Revenue", "sum"), Spend=("Spend", "sum"))
        st.line_chart(monthly.set_index("Month"), width="stretch")
    with right:
        st.subheader("Campaign Recommendations")
        recommendation_mix = scored["Recommendation"].value_counts().rename_axis("Recommendation").reset_index(name="Campaigns")
        st.bar_chart(recommendation_mix.set_index("Recommendation"), width="stretch")

    st.subheader("Campaign Score Ranking")
    st.bar_chart(scored.set_index("Campaign")["Campaign_Score"], width="stretch")

with segment_tab:
    st.subheader("Segment Economics")
    segment_display = segment_summary[
        [
            "Segment",
            "Segment_Score",
            "Recommendation",
            "Spend",
            "Revenue",
            "Contribution",
            "ROI",
            "LTV_CAC",
            "Payback_Months",
            "Lead_To_Customer",
            "Risk_Flags",
        ]
    ].copy()
    segment_display = format_money_columns(segment_display, ["Spend", "Revenue", "Contribution"])
    segment_display = format_percent_columns(segment_display, ["ROI", "Lead_To_Customer"])
    segment_display = format_number_columns(segment_display, ["Segment_Score"], "/100")
    segment_display = format_number_columns(segment_display, ["LTV_CAC"], "x")
    segment_display = format_number_columns(segment_display, ["Payback_Months"], " mo")
    st.dataframe(segment_display, width="stretch", hide_index=True)

    st.subheader("LTV:CAC by Segment")
    st.bar_chart(segment_summary.set_index("Segment")["LTV_CAC"], width="stretch")

with channel_tab:
    st.subheader("Channel Contribution")
    channel_display = channel_summary.copy()
    channel_display = format_money_columns(channel_display, ["Spend", "Revenue", "Contribution", "CAC"])
    channel_display = format_percent_columns(channel_display, ["ROI", "Lead_To_Customer"])
    channel_display = format_number_columns(channel_display, ["ROAS"], "x")
    st.dataframe(channel_display, width="stretch", hide_index=True)
    st.bar_chart(channel_summary.set_index("Channel")[["Revenue", "Contribution"]], width="stretch")

with budget_tab:
    st.subheader("Budget Reallocation Recommendation")
    budget_display = budget_plan.copy()
    budget_display = format_money_columns(budget_display, ["Spend", "Recommended_Spend", "Budget_Change", "Revenue", "Contribution"])
    budget_display = format_percent_columns(budget_display, ["ROI"])
    budget_display = format_number_columns(budget_display, ["Segment_Score"], "/100")
    budget_display = format_number_columns(budget_display, ["LTV_CAC"], "x")
    st.dataframe(budget_display, width="stretch", hide_index=True)

    st.subheader("Current vs Recommended Spend")
    budget_chart = budget_plan.set_index("Segment")[["Spend", "Recommended_Spend"]]
    st.bar_chart(budget_chart, width="stretch")

with memo_tab:
    st.subheader("Executive Marketing ROI Memo")
    memo = build_executive_memo(scored, segment_summary, channel_summary)
    st.markdown(memo)
    st.download_button("Download memo", memo, "marketing_roi_memo.md", "text/markdown")

with data_tab:
    st.subheader("Source Campaign Data")
    st.dataframe(filtered_data, width="stretch", hide_index=True)
    st.subheader("Scoring Methodology")
    st.write("Campaign and segment scores use fixed thresholds for contribution ROI, LTV:CAC, lead-to-customer conversion, payback months, and retention.")
    st.write("LTV is estimated from monthly gross profit per customer and expected lifetime months using retention rate.")
    st.write("Contribution equals gross profit less marketing spend. CAC equals spend divided by customers.")
    st.write("Budget recommendations preserve total spend and shift dollars toward segments with stronger score, positive ROI, and stronger LTV:CAC.")
