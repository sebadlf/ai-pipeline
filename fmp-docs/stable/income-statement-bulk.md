# Income Statement Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/income-statement-bulk](https://site.financialmodelingprep.com/developer/docs/stable/income-statement-bulk)

The Bulk Income Statement API allows users to retrieve detailed income statement data in bulk. This API is designed for large-scale data analysis, providing comprehensive insights into a company's financial performance, including revenue, gross profit, expenses, and net income.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/income-statement-bulk?year=2025&period=Q1`

## Description
The Bulk Income Statement API is ideal for users who need to:


Analyze Financial Performance: Access large datasets for deep financial analysis, including multiple income statements from various companies.
Track Revenue and Profit Trends: Quickly retrieve data on revenue, gross profit, operating income, and net income to assess a company's profitability over time.
Evaluate Expenses: Review operating expenses, cost of revenue, and selling, general, and administrative expenses (SG&A) to identify where a company allocates its spending.
Conduct Bulk Research: Ideal for financial analysts, investors, and researchers who need to process income statements across multiple companies for detailed industry or sector comparison.

This API delivers financial data in a standardized format, making it easy to conduct large-scale financial analysis.

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
`profile-bulk`, `eod-bulk`, `key-metrics-ttm-bulk`, `rating-bulk`, `dcf-bulk`
