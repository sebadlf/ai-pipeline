# Income Statement Growth

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/income-statement-growth](https://site.financialmodelingprep.com/developer/docs/stable/income-statement-growth)

Track key financial growth metrics with the Income Statement Growth API. Analyze how revenue, profits, and expenses have evolved over time, offering insights into a company’s financial health and operational efficiency.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/income-statement-growth?symbol=AAPL`

## Description
The Income Statement Growth API provides critical growth data, allowing users to track year-over-year changes in key income statement items, such as:


Revenue Growth: Monitor changes in a company’s total revenue, helping gauge overall business performance.
Profit Growth: Assess fluctuations in gross profit, operating income, and net income, offering insights into profitability trends.
Expense Growth: Analyze growth in operating expenses, cost of revenue, and specific line items like research and development or interest expenses.

This API is a valuable tool for investors, analysts, and financial professionals who want to track a company's financial trends over time.

Example Use Case
A financial analyst can use the Income Statement Growth API to evaluate Apple’s revenue and net income trends over the past few years, identifying whether the company is experiencing consistent growth or declines in profitability.

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
`balance-sheet-statement-growth`, `revenue-product-segmentation`, `key-metrics-ttm`, `as-reported-balance-statements`, `as-reported-income-statements`
