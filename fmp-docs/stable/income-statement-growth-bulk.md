# Income Statement Growth Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/income-statement-growth-bulk](https://site.financialmodelingprep.com/developer/docs/stable/income-statement-growth-bulk)

The Bulk Income Statement Growth API provides access to growth data for income statements across multiple companies. Track and analyze growth trends over time for key financial metrics such as revenue, net income, and operating income, enabling a better understanding of corporate performance trends.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/income-statement-growth-bulk?year=2025&period=Q1`

## Description
This API is ideal for users who want to:


Track Financial Growth: Understand how a company’s income statement figures, like revenue and net income, are growing over time.
Analyze Trends: Gain insights into long-term trends in income statement growth, including expenses, EBITDA, and earnings per share (EPS).
Evaluate Performance: Measure a company’s growth rate across multiple financial metrics to evaluate its financial health and performance over time.
Bulk Data Retrieval: Quickly retrieve growth data for income statements across a large number of companies for comparative analysis or trend forecasting.

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
        "year*",
        "string",
        "2025"
      ],
      [
        "period*",
        "string",
        [
          "Q1",
          "Q2",
          "Q3",
          "Q4",
          "FY"
        ]
      ]
    ]
  }
}
```

## Related API slugs
`etf-holder-bulk`, `rating-bulk`, `price-target-summary-bulk`, `balance-sheet-statement-bulk`, `key-metrics-ttm-bulk`
