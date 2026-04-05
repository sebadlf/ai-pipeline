# Cashflow Statement Growth

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cashflow-statement-growth](https://site.financialmodelingprep.com/developer/docs/stable/cashflow-statement-growth)

Measure the growth rate of a company’s cash flow with the FMP Cashflow Statement Growth API. Determine how quickly a company’s cash flow is increasing or decreasing over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/cash-flow-statement-growth?symbol=AAPL`

## Description
The FMP Cashflow Statement Growth API provides key insights into the cash flow growth rate of a company, an essential metric for assessing a company's financial health. This API is crucial for:


Financial Performance Evaluation: Analyze the rate at which a company’s cash flow is growing. A positive growth rate indicates that the company is generating more cash than it is using, which can signal strong financial health and operational efficiency.
Investment Decision-Making: Use cash flow growth data to identify companies with strong cash flow generation capabilities. Companies with consistent positive cash flow growth are often more stable and may represent good investment opportunities.
Risk Assessment: A negative cash flow growth rate can be a red flag, indicating that a company is using more cash than it is generating. This information can be used to evaluate the risk associated with investing in or continuing to hold a company’s stock.

Example
Investor Analysis: An investor might use the Cashflow Growth API to assess a manufacturing company’s financial health by examining its cash flow growth over the past five years. If the company shows consistent positive growth, the investor may decide to increase their investment in the company.

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
`owner-earnings`, `revenue-geographic-segments`, `enterprise-values`, `metrics-ratios-ttm`, `balance-sheet-statement`
