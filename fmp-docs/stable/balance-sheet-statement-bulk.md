# Balance Sheet Statement Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement-bulk](https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement-bulk)

The Bulk Balance Sheet Statement API provides comprehensive access to balance sheet data across multiple companies. It enables users to analyze financial positions by retrieving key figures such as total assets, liabilities, and equity. Ideal for comparing the financial health and stability of different companies on a large scale.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/balance-sheet-statement-bulk?year=2025&period=Q1`

## Description
This API is a powerful tool for:


Financial Analysis: Retrieve balance sheet data to evaluate assets, liabilities, and equity, and assess the financial health of multiple companies.
Bulk Data Retrieval: Get detailed financial positions for a wide range of companies in a single request, allowing for comparative analysis and portfolio evaluation.
Corporate Health Assessment: Analyze metrics such as total debt, cash and cash equivalents, net receivables, and shareholder equity to determine the strength of a company’s balance sheet.
Historical Tracking: Use balance sheet data to track a company’s financial position over time, identifying trends and changes in its financial standing.

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
`cash-flow-statement-growth-bulk`, `upgrades-downgrades-consensus-bulk`, `rating-bulk`, `key-metrics-ttm-bulk`, `income-statement-bulk`
