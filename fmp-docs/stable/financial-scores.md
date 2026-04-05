# Financial Scores

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/financial-scores](https://site.financialmodelingprep.com/developer/docs/stable/financial-scores)

Assess a company's financial strength using the Financial Health Scores API. This API provides key metrics such as the Altman Z-Score and Piotroski Score, giving users insights into a company’s overall financial health and stability.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/financial-scores?symbol=AAPL`

## Description
The Financial Health Scores API offers a detailed evaluation of a company's financial stability by calculating various scores and metrics. This API is ideal for:


Bankruptcy Risk Analysis: Use the Altman Z-Score to assess the likelihood of a company facing financial distress.
Profitability and Efficiency Evaluation: The Piotroski Score helps determine a company’s financial strength by measuring profitability and operational efficiency.
Working Capital Management: Track changes in working capital to understand how a company manages its short-term assets and liabilities.
Leverage and Capital Structure: Assess the relationship between a company’s total liabilities and market capitalization to evaluate its financial leverage.

This API is a powerful tool for investors and analysts who need to evaluate the financial strength of a company to make informed decisions.

Example Use Case
A financial analyst uses the Financial Health Scores API to check Apple’s Altman Z-Score and Piotroski Score before recommending it as a stable investment to clients.

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
`enterprise-values`, `income-statement`, `revenue-product-segmentation`, `key-metrics-ttm`, `financial-statement-growth`
