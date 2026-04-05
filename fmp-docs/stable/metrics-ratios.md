# Financial Ratios

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios](https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios)

Analyze a company's financial performance using the Financial Ratios API. This API provides detailed profitability, liquidity, and efficiency ratios, enabling users to assess a company's operational and financial health across various metrics.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/ratios?symbol=AAPL`

## Description
The Financial Ratios API delivers key ratios that help investors, analysts, and researchers evaluate a company's performance. These ratios include profitability indicators like gross profit margin and net profit margin, liquidity metrics such as current ratio and quick ratio, and efficiency measurements like asset turnover and inventory turnover. This API offers a comprehensive view of a company's financial health and operational efficiency.


Profitability Ratios: Gain insight into a company's ability to generate profit, with metrics like net profit margin and return on equity.
Liquidity Ratios: Understand how well a company can meet its short-term obligations using ratios like current ratio and quick ratio.
Efficiency Ratios: Assess how effectively a company utilizes its assets with metrics such as asset turnover and inventory turnover.
Debt Ratios: Evaluate a company's leverage and debt management through ratios like debt-to-equity and interest coverage ratios.

This API is an essential tool for investors and analysts looking to analyze financial ratios and make informed decisions based on a company's financial performance.

Example Use Case
A portfolio manager can use the Financial Ratios API to compare liquidity ratios between companies in the same industry, helping them identify firms with stronger financial stability and more efficient operations.

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
`cashflow-statement`, `financial-reports-form-10-k-json`, `financial-statement-growth`, `revenue-geographic-segments`, `as-reported-balance-statements`
