# As Reported Income Statements

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/as-reported-income-statements](https://site.financialmodelingprep.com/developer/docs/stable/as-reported-income-statements)

Retrieve income statements as they were reported by the company with the As Reported Income Statements API. Access raw financial data directly from official company filings, including revenue, expenses, and net income.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/income-statement-as-reported?symbol=AAPL`

## Description
The As Reported Income Statements API provides a clear and direct view of a company's financial performance as reported in their official financial statements. This API is useful for:


Direct Financial Insights: Access income statement data as reported by the company, without adjustments.
Comprehensive Expense Tracking: See detailed breakdowns of revenue, cost of goods sold, and operating expenses.
In-Depth Analysis: Use the raw data to perform your own calculations and build models based on official figures.

This API allows investors and analysts to rely on the most accurate, company-provided financial information for evaluating profitability and operational efficiency.

Example Use Case
A financial analyst can use the As Reported Income Statements API to access Apple’s quarterly income statements, allowing them to compare operating income and net profit for different fiscal periods without any adjustments.

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
          "annual",
          "quarter"
        ]
      ]
    ]
  }
}
```

## Related API slugs
`financial-reports-form-10-k-json`, `as-reported-cashflow-statements`, `metrics-ratios-ttm`, `income-statement`, `income-statement-growth`
