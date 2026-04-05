# Financial Ratios TTM

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios-ttm](https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios-ttm)

Gain access to trailing twelve-month (TTM) financial ratios with the TTM Ratios API. This API provides key performance metrics over the past year, including profitability, liquidity, and efficiency ratios.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/ratios-ttm?symbol=AAPL`

## Description
The TTM Ratios API offers a comprehensive view of a company's financial performance, making it an essential tool for investors, analysts, and decision-makers. This API is ideal for:


Profitability Analysis: Understand how efficiently a company generates profit using metrics like gross profit margin, net profit margin, and EBITDA margin.
Liquidity Assessment: Evaluate a company’s ability to meet short-term obligations with ratios such as the current ratio and quick ratio.
Efficiency Insight: Examine how well a company manages its assets and liabilities with key efficiency ratios like asset turnover and inventory turnover.
Leverage Evaluation: Assess a company’s debt levels and leverage through metrics like the debt-to-equity ratio and financial leverage ratio.

This API provides insights into a company's performance across key areas, helping users make more informed decisions by analyzing trends over the past twelve months.

Example Use Case
An investor uses the TTM Ratios API to analyze Apple’s liquidity and profitability ratios, helping them decide whether to invest in the company based on its trailing twelve-month financial performance.

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
`cashflow-statement`, `income-statement`, `as-reported-financial-statements`, `financial-reports-form-10-k-json`, `metrics-ratios`
