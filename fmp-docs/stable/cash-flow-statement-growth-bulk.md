# Cash Flow Statement Growth Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cash-flow-statement-growth-bulk](https://site.financialmodelingprep.com/developer/docs/stable/cash-flow-statement-growth-bulk)

The Cash Flow Statement Growth Bulk API allows you to retrieve bulk growth data for cash flow statements, enabling you to track changes in cash flows over time. This API is ideal for analyzing the cash flow growth trends of multiple companies simultaneously.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/cash-flow-statement-growth-bulk?year=2025&period=Q1`

## Description
This API helps you:


Track Growth Trends: Monitor changes in key cash flow metrics such as operating cash flow, capital expenditures, and free cash flow over time.
Compare Company Performance: Quickly analyze the growth in cash flow activities for several companies, making it easier to identify high-growth firms or companies with declining cash flow.
Understand Financial Health: Evaluate how companies are managing their cash flow, whether it’s through improved operations or changes in investment and financing activities.

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
`etf-holder-bulk`, `ratios-ttm-bulk`, `income-statement-growth-bulk`, `upgrades-downgrades-consensus-bulk`, `cash-flow-statement-bulk`
