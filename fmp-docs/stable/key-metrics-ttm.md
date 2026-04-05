# Key Metrics TTM

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/key-metrics-ttm](https://site.financialmodelingprep.com/developer/docs/stable/key-metrics-ttm)

Retrieve a comprehensive set of trailing twelve-month (TTM) key performance metrics with the TTM Key Metrics API. Access data related to a company's profitability, capital efficiency, and liquidity, allowing for detailed analysis of its financial health over the past year.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/key-metrics-ttm?symbol=AAPL`

## Description
The TTM Key Metrics API provides valuable insights into a company's recent performance, capturing data over the trailing twelve-month period. This API is ideal for:


Profitability Assessment: Understand a company's ability to generate profit, with metrics such as return on assets (ROA) and earnings yield.
Liquidity and Solvency Analysis: Evaluate how efficiently a company manages its short-term obligations with ratios like the current ratio and cash conversion cycle.
Capital Efficiency: Assess how well a company is using its capital with metrics like return on invested capital (ROIC) and return on equity (ROE).
Operational Performance: Get insights into the operational efficiency of a company through operating cycle and days of inventory outstanding (DIO).

This API helps investors, analysts, and portfolio managers track financial performance trends and assess companies' efficiency in generating returns.

Example Use Case
An analyst can use the TTM Key Metrics API to compare the free cash flow yield of several companies within the same industry, helping them make better-informed investment decisions.

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
      ]
    ]
  }
}
```

## Related API slugs
`cashflow-statement`, `revenue-geographic-segments`, `balance-sheet-statement-growth`, `key-metrics`, `financial-reports-form-10-k-xlsx`
