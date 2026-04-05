# As Reported Cashflow Statements

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/as-reported-cashflow-statements](https://site.financialmodelingprep.com/developer/docs/stable/as-reported-cashflow-statements)

View cash flow statements as reported by the company with the As Reported Cash Flow Statements API. Analyze a company's cash flows related to operations, investments, and financing directly from official reports.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/cash-flow-statement-as-reported?symbol=AAPL`

## Description
The As Reported Cash Flow Statements API provides access to unadjusted cash flow data as reported by companies. This includes:


Operational Cash Flows: Examine the cash generated or used in day-to-day business activities.
Investment Cash Flows: Access cash movements related to investments in assets, acquisitions, and securities.
Financing Cash Flows: View cash from equity, debt issuance, and dividend payments.

This API is ideal for users looking for a clear understanding of a company's cash flow management based on official filings.

Example Use Case
A financial analyst can use this API to track Apple's cash flow trends during Q1 2010, helping assess how effectively the company is managing its cash for operations and investments.

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
`key-metrics`, `enterprise-values`, `revenue-geographic-segments`, `metrics-ratios-ttm`, `metrics-ratios`
