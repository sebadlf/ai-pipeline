# Financial Statement Growth

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/financial-statement-growth](https://site.financialmodelingprep.com/developer/docs/stable/financial-statement-growth)

Analyze the growth of key financial statement items across income, balance sheet, and cash flow statements with the Financial Statement Growth API. Track changes over time to understand trends in financial performance.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/financial-growth?symbol=AAPL`

## Description
The Financial Statement Growth API provides an overview of year-over-year growth in key financial metrics from income statements, balance sheets, and cash flow statements. It’s designed for analysts and investors who want to:


Assess Revenue Trends: See how a company's revenue has grown or contracted over time, highlighting overall business health.
Evaluate Profitability Growth: Track growth in net income, operating income, and EBIT to gauge profitability.
Monitor Asset & Debt Changes: Understand the growth or reduction in assets and liabilities, providing insights into financial management.
Examine Cash Flow Changes: View growth in operating cash flow and free cash flow to analyze liquidity and capital efficiency.

This API helps in identifying long-term trends across financial statements, providing a comprehensive picture of a company's financial growth.

Example Use Case
An investor can use the Financial Statement Growth API to analyze Apple’s revenue, net income, and free cash flow growth over the past few years, helping them assess the company’s performance trends.

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
        "symbol*",
        "string",
        "AAPL"
      ],
      [
        "limit",
        "number",
        "5"
      ],
      [
        "period",
        "string",
        [
          "Q1",
          "Q2",
          "Q3",
          "Q4",
          "FY",
          "annual",
          "quarter"
        ]
      ]
    ]
  }
}
```

## Related API slugs
`financial-reports-form-10-k-xlsx`, `balance-sheet-statement-growth`, `metrics-ratios-ttm`, `key-metrics-ttm`, `as-reported-balance-statements`
