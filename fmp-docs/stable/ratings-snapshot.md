# Ratings Snapshot

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/ratings-snapshot](https://site.financialmodelingprep.com/developer/docs/stable/ratings-snapshot)

Quickly assess the financial health and performance of companies with the FMP Ratings Snapshot API. This API provides a comprehensive snapshot of financial ratings for stock symbols in our database, based on various key financial ratios.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/ratings-snapshot?symbol=AAPL`

## Description
The FMP Ratings Snapshot API allows users to evaluate a company's financial performance across multiple dimensions by delivering:


Overall Rating: Get a summary score that reflects the company's financial standing.
Discounted Cash Flow (DCF) Score: Understand the company’s valuation compared to its future cash flow potential.
Return on Equity (ROE) Score: Measure how efficiently a company is generating profit relative to shareholders' equity.
Return on Assets (ROA) Score: Gauge how effectively a company uses its assets to generate earnings.
Debt-to-Equity Score: Analyze the company’s capital structure and risk by comparing its debt to equity.
Price-to-Earnings (P/E) Score: Assess the company’s stock price relative to its earnings to understand its valuation.
Price-to-Book (P/B) Score: Compare the company’s market price to its book value to evaluate potential investment opportunities.

This API offers an overall rating, along with scores for critical metrics such as discounted cash flow, return on equity, return on assets, debt-to-equity, price-to-earnings, and price-to-book ratios. It is perfect for investors, financial analysts, and researchers who need a fast, comprehensive view of a company’s financial health based on key metrics.

Example Use Case
An equity analyst can use the Ratings Snapshot API to compare multiple companies' financial health based on return on equity, debt levels, and valuation ratios, helping them make more informed investment recommendations.

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
`historical-grades`, `financial-estimates`, `price-target-consensus`, `grades`, `grades-summary`
