# As Reported Financial Statements

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/as-reported-financial-statements](https://site.financialmodelingprep.com/developer/docs/stable/as-reported-financial-statements)

Retrieve comprehensive financial statements as reported by companies with FMP As Reported Financial Statements API. Access complete data across income, balance sheet, and cash flow statements in their original form for detailed analysis.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/financial-statement-full-as-reported?symbol=AAPL`

## Description
The As Reported Financial Statements API provides users with original, unadjusted financial statements directly from company filings. This API is ideal for:


Detailed Financial Audits: Access income, balance sheet, and cash flow statements exactly as companies report them, ensuring compliance and accuracy.
Investment Analysis: Analyze reported figures to assess a company’s financial performance over time and compare them to industry peers.
Historical Data Tracking: Retrieve historical financials to track trends, identify growth opportunities, or spot potential red flags.
Compliance and Reporting: Leverage raw data for audits, compliance, or regulatory filings, ensuring your records match the company’s public disclosures.

This API allows investors, auditors, and analysts to dive deep into the original financial data filed by public companies for greater accuracy and insights.

Example Use Case
An auditor can use the As Reported Financial Statements API to retrieve Apple's historical financials, including balance sheet, income, and cash flow data, exactly as reported to the SEC. This raw data can help verify the accuracy of an investment analysis or ensure compliance with financial reporting standards.

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
`key-metrics-ttm`, `metrics-ratios-ttm`, `income-statement-growth`, `balance-sheet-statement`, `income-statement`
