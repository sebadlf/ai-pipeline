# Balance Sheet Statement Growth

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement-growth](https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement-growth)

Analyze the growth of key balance sheet items over time with the Balance Sheet Statement Growth API. Track changes in assets, liabilities, and equity to understand the financial evolution of a company.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/balance-sheet-statement-growth?symbol=AAPL`

## Description
The Balance Sheet Statement Growth API provides year-over-year growth metrics for key balance sheet components. This API is ideal for:


Asset Growth Analysis: Track changes in assets, such as cash, inventory, and long-term investments, to assess how a company’s resources are expanding or contracting.
Liability Growth Monitoring: Understand how short-term and long-term liabilities are evolving, including payables and debt.
Equity Growth Tracking: Monitor shifts in shareholder equity, retained earnings, and total equity, offering insights into a company’s financial health.

This API helps financial analysts and investors evaluate a company's stability and growth by examining the evolution of its balance sheet items.

Example Use Case
An investor can use the Balance Sheet Statement Growth API to analyze how Apple’s cash reserves and debt levels have changed over the past year, helping them assess the company’s liquidity and financial health.

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
`revenue-product-segmentation`, `owner-earnings`, `income-statement`, `financial-statement-growth`, `balance-sheet-statement`
