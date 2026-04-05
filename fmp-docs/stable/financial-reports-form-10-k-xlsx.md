# Financial Reports Form 10-K XLSX

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/financial-reports-form-10-k-xlsx](https://site.financialmodelingprep.com/developer/docs/stable/financial-reports-form-10-k-xlsx)

Download detailed 10-K reports in XLSX format with the Financial Reports Form 10-K XLSX API. Effortlessly access and analyze annual financial data for companies in a spreadsheet-friendly format.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/financial-reports-xlsx?symbol=AAPL&year=2022&period=FY`

## Description
The Financial Reports Form 10-K XLSX API provides users with the ability to download 10-K financial reports in a format that can be opened in Excel. This allows for:


Detailed Financial Analysis: View comprehensive financial data, including income statements, balance sheets, and cash flow statements, with Excel’s built-in analysis tools.
Flexible Data Usage: Customize and manipulate the data for further analysis, enabling users to run financial models or track trends.
Efficient Reporting: Create financial summaries, pivot tables, and other visualizations based on the data from 10-K reports.
Historical Data Access: Download reports from previous fiscal years for detailed historical comparisons.

This API makes it simple to work with financial data in a spreadsheet, streamlining analysis and reporting workflows.

Example Use Case
A financial analyst can download Apple’s 2022 10-K report in XLSX format, making it easier to import the data into their financial models and analyze trends over the fiscal year.

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
        "year*",
        "number",
        "2022"
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
`key-metrics`, `cashflow-statement-growth`, `as-reported-income-statements`, `as-reported-financial-statements`, `balance-sheet-statement-growth`
