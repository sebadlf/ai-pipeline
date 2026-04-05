# COT Report

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cot-report](https://site.financialmodelingprep.com/developer/docs/stable/cot-report)

Access comprehensive Commitment of Traders (COT) reports with the FMP COT Report API. This API provides detailed information about long and short positions across various sectors, helping you assess market sentiment and track positions in commodities, indices, and financial instruments.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/commitment-of-traders-report`

## Description
The FMP COT Report API is designed for traders, analysts, and market observers to evaluate the positions of market participants. This includes:


Market Sentiment Tracking: Understand how commercial and non-commercial traders are positioned, giving you insights into the current sentiment of a specific market.
Sector-Wide Analysis: Analyze trader positions across different sectors such as soft commodities, energy, and financials, offering a holistic view of market trends.
Long and Short Positions: Get detailed data on long, short, and spread positions, helping you make informed decisions on market direction.

This API is perfect for anyone looking to gain a deeper understanding of market dynamics by observing how various market participants are positioned.

Example Use Case
A commodity trader can use the COT Report API to analyze the open interest and trader positions in the cocoa market, identifying trends in long and short positions to refine their trading strategy.

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
