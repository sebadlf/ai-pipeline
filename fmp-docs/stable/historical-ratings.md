# Historical Ratings

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-ratings](https://site.financialmodelingprep.com/developer/docs/stable/historical-ratings)

Track changes in financial performance over time with the FMP Historical Ratings API. This API provides access to historical financial ratings for stock symbols in our database, allowing users to view ratings and key financial metric scores for specific dates.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/ratings-historical?symbol=AAPL`

## Description
The FMP Historical Ratings API is ideal for analysts and investors looking to assess how a company’s financial health has evolved over time. Key features include:


Historical Ratings: Retrieve ratings from past dates to track a company's financial trajectory.
Overall Rating: Access an easy-to-understand rating summarizing the company’s financial health on a given date.
Discounted Cash Flow (DCF) Score: Evaluate historical valuation compared to future cash flow potential.
Return on Equity (ROE) Score: Track past performance on generating profit relative to shareholders' equity.
Return on Assets (ROA) Score: View how asset utilization has changed over time.
Debt-to-Equity Score: Examine changes in the company’s capital structure.
Price-to-Earnings (P/E) Score: Monitor historical stock valuation relative to earnings.
Price-to-Book (P/B) Score: Assess how market price has compared to book value in the past.

This API is ideal for conducting trend analysis and understanding how various financial metrics have influenced a company’s rating over time. It includes an overall rating and individual scores for critical financial ratios such as discounted cash flow, return on equity, return on assets, debt-to-equity, price-to-earnings, and price-to-book ratios.

Example Use Case
A portfolio manager can use the Historical Ratings API to analyze how a company’s return on equity and debt-to-equity ratios have evolved over the last five years, helping them evaluate long-term performance trends.

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
        "1"
      ]
    ]
  }
}
```

## Related API slugs
`financial-estimates`, `historical-grades`, `price-target-summary`, `price-target-consensus`, `grades`
