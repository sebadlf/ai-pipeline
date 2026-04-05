# Cash Flow Statement Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cash-flow-statement-bulk](https://site.financialmodelingprep.com/developer/docs/stable/cash-flow-statement-bulk)

The Cash Flow Statement Bulk API provides access to detailed cash flow reports for a wide range of companies. This API enables users to retrieve bulk cash flow statement data, helping to analyze companies’ operating, investing, and financing activities over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/cash-flow-statement-bulk?year=2025&period=Q1`

## Description
This API is essential for:


Tracking Cash Movements: Understand how a company generates and uses cash in its operations, investments, and financing activities.
Free Cash Flow Analysis: Analyze free cash flow to assess a company's ability to generate cash after accounting for capital expenditures.
Comparative Analysis: Access data for multiple companies at once to compare their cash flow trends, helping to identify companies with strong or weak cash flow management.

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
`peers-bulk`, `income-statement-bulk`, `profile-bulk`, `key-metrics-ttm-bulk`, `earnings-surprises-bulk`
