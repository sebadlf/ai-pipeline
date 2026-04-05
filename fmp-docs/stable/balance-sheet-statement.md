# Balance Sheet Statement

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement](https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement)

Access detailed balance sheet statements for publicly traded companies with the Balance Sheet Data API. Analyze assets, liabilities, and shareholder equity to gain insights into a company's financial health.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/balance-sheet-statement?symbol=AAPL`

## Description
The Balance Sheet Data API allows investors, analysts, and financial professionals to retrieve detailed balance sheet information for companies. This API is essential for:


Comprehensive Financial Analysis: View key data on assets, liabilities, and shareholder equity, allowing for a detailed assessment of a company's financial structure and solvency.
Evaluating Company Health: Determine a company's liquidity and leverage through short-term and long-term assets, liabilities, and shareholder equity positions.
Supporting Investment Decisions: Use the balance sheet to compare companies within the same industry or sector, ensuring you make informed investment decisions based on a company's financial stability.

This API provides real-time and historical balance sheet data, offering a snapshot of a company's financial health over different periods. Whether you're analyzing a company's financial performance or conducting due diligence, this data helps you evaluate critical financial metrics with ease.

Example Use Case
An investor analyzing a potential stock purchase uses the Balance Sheet Data API to evaluate the company's assets and liabilities. They review how much cash the company has on hand, its debt obligations, and total equity to ensure the company is financially stable.

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
`as-reported-balance-statements`, `cashflow-statement-growth`, `key-metrics-ttm`, `balance-sheet-statement-growth`, `financial-statement-growth`
