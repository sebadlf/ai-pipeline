# Balance Sheet Statement Growth Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement-growth-bulk](https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement-growth-bulk)

The Balance Sheet Growth Bulk API allows users to retrieve growth data across multiple companies’ balance sheets, enabling detailed analysis of how financial positions have changed over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/balance-sheet-statement-growth-bulk?year=2025&period=Q1`

## Description
This API is designed for:


Trend Analysis: Track the growth or decline of financial metrics such as cash and short-term investments, receivables, total liabilities, and equity.
Comparative Insights: Analyze changes in financial positions across multiple companies over different periods to spot trends, risks, and opportunities.
Long-Term Financial Health Assessment: Assess how a company’s balance sheet has evolved, providing deeper insights into its long-term financial stability.

This API is essential for tracking the development of assets, liabilities, and equity, providing insights into a company’s financial trajectory.

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
`eod-bulk`, `price-target-summary-bulk`, `profile-bulk`, `ratios-ttm-bulk`, `balance-sheet-statement-bulk`
