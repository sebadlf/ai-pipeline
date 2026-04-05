# COT Analysis By Dates

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cot-report-analysis](https://site.financialmodelingprep.com/developer/docs/stable/cot-report-analysis)

Gain in-depth insights into market sentiment with the FMP COT Report Analysis API. Analyze the Commitment of Traders (COT) reports for a specific date range to evaluate market dynamics, sentiment, and potential reversals across various sectors.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/commitment-of-traders-analysis`

## Description
The FMP COT Report Analysis API is designed for traders, analysts, and market strategists to interpret the long and short positions of traders over time, helping to track sentiment trends and potential market shifts. This API includes:


Market Sentiment Evaluation: Analyze the bullish or bearish sentiment based on long and short positions, helping you gauge the current market situation.
Net Position Changes: Track changes in net positions to understand whether sentiment is becoming more bullish or bearish.
Historical Sentiment Comparison: Compare current market sentiment with previous periods to detect trends or potential reversal points in the market.

This API enables market participants to make informed decisions by providing detailed insights into how traders are positioned in various markets and how sentiment evolves over time.

Example Use Case
A commodity trader can use the COT Report Analysis API to assess the bullish sentiment in the energy market by tracking changes in the net position of Brent crude oil traders, allowing them to refine their trading strategy accordingly.

## Parameters (from docs JSON)
```json
{
  "query": {
    "header": [
      "Query Parameter",
      "Type",
      "Example"
    ],
    "rows": [
      [
        "symbol",
        "string",
        "AAPL"
      ],
      [
        "from",
        "date",
        "2024-01-01"
      ],
      [
        "to",
        "date",
        "2024-03-01"
      ]
    ]
  }
}
```

## Related API slugs
`COT-report`, `COT-report-analysis`, `COT-report-list`
