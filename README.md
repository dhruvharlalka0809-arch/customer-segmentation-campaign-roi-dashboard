# Customer Segmentation & Campaign ROI Dashboard

A Streamlit dashboard for marketing performance analysis, customer segmentation, campaign ROI diagnostics, CAC/LTV review, payback analysis, and budget reallocation recommendations.

## What It Does

- Scores campaigns and customer segments on a 0-100 marketing quality scale
- Calculates CAC, CPL, ROAS, contribution ROI, LTV:CAC, payback months, and funnel conversion rates
- Ranks segments as Invest, Optimize, or Pause / fix economics
- Flags marketing risks such as negative ROI, weak LTV:CAC, slow payback, low lead conversion, and retention risk
- Compares channel contribution and customer acquisition efficiency
- Recommends budget shifts while preserving total spend
- Generates an executive marketing ROI memo
- Supports CSV upload for custom campaign datasets

## Why This Project Matters

This project shows commercial marketing analytics, not just charting. It connects campaigns to financial outcomes and gives a growth, business analyst, or marketing strategy team a practical way to decide where budget should move.

## Tech Stack

- Python
- Streamlit
- Pandas
- Standard-library tests with `unittest`

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Validate

```bash
python scripts/validate.py
```

## Portfolio Talking Points

- Built a marketing ROI dashboard connecting spend, revenue, gross profit, CAC, LTV:CAC, payback, and funnel conversion
- Created segment-level recommendation logic for Invest, Optimize, and Pause decisions
- Added budget reallocation logic that shifts spend toward stronger segment economics
- Converted campaign analytics into an executive memo suitable for marketing ops, growth strategy, and business analyst roles

## Author

Dhruv Harlalka

MBA Finance, Middlesex University Dubai
