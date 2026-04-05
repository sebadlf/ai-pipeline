# Enterprise Values

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/enterprise-values](https://site.financialmodelingprep.com/developer/docs/stable/enterprise-values)

Access a company's enterprise value using the Enterprise Values API. This metric offers a comprehensive view of a company's total market value by combining both its equity (market capitalization) and debt, providing a better understanding of its worth.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/enterprise-values?symbol=AAPL`

## Description
The Enterprise Values API provides key financial data to help assess a company’s value by including:


Market Capitalization: The total value of all outstanding shares based on the current stock price.
Debt & Cash: Includes total debt and subtracts cash and cash equivalents to get a full picture of a company’s financial standing.
Comprehensive Valuation: Enterprise value includes both equity and debt, making it a preferred measure for evaluating potential buyouts, mergers, or acquisitions.

This API is ideal for analysts, investors, and finance professionals who need a complete understanding of a company’s valuation, especially when considering its overall market position.

Example Use Case
A financial analyst uses the Enterprise Values API to assess Apple’s total market value, factoring in debt and subtracting cash reserves, to determine whether it’s a good acquisition target.

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
`key-metrics-ttm`, `income-statement`, `revenue-product-segmentation`, `metrics-ratios`, `key-metrics`
