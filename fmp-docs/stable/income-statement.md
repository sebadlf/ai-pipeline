# Income Statement

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/income-statement](https://site.financialmodelingprep.com/developer/docs/stable/income-statement)

Access detailed income statement data for publicly traded companies with the Income Statements API. Track profitability, compare competitors, and identify business trends with up-to-date financial data.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/income-statement?symbol=AAPL`

## Description
The FMP Income Statements API provides comprehensive access to income statement data for a wide range of companies. This API is essential for:


Profitability Tracking: Monitor a company's revenue, expenses, and net income over time. The income statement, also known as the profit and loss statement, provides a detailed view of a company's financial performance during a specific period.
Competitive Analysis: Use the API to compare a company's financial performance to its competitors. By analyzing income statements across companies, investors can identify which businesses are leading in profitability and efficiency.
Trend Identification: Detect trends in a company's business by examining changes in revenue, expenses, and net income over multiple periods. This data is crucial for understanding a company's financial health and growth prospects.

Example
Financial Ratio Calculation: An investor can use the Income Statements API to calculate key financial ratios, such as the price-to-earnings ratio (P/E ratio) and gross margin. These ratios help investors assess a company's valuation and profitability, enabling more informed investment decisions.

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
`financial-reports-form-10-k-json`, `enterprise-values`, `financial-reports-form-10-k-xlsx`, `as-reported-balance-statements`, `as-reported-income-statements`
