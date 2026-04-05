# Financial Estimates

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/financial-estimates](https://site.financialmodelingprep.com/developer/docs/stable/financial-estimates)

Retrieve analyst financial estimates for stock symbols with the FMP Financial Estimates API. Access projected figures like revenue, earnings per share (EPS), and other key financial metrics as forecasted by industry analysts to inform your investment decisions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/analyst-estimates?symbol=AAPL&period=annual&page=0&limit=10`

## Description
The FMP Financial Estimates API is an invaluable resource for investors who want a deeper understanding of a company's projected performance. By collecting forecasts from leading financial analysts, this API provides essential insights into:


Revenue Projections: Get estimates on future company revenue, offering a glimpse into anticipated growth trends.
Earnings Per Share (EPS) Forecasts: Access analyst predictions on a company’s future earnings, which are critical for evaluating profitability.
Consensus Metrics: View consensus estimates from multiple analysts, providing a comprehensive outlook on the market’s expectations.
Investment Planning: Use these estimates to benchmark a company's projected performance, identify potential over- or undervalued stocks, and refine your investment strategies.

The Financial Estimates API is ideal for investors, traders, and financial analysts looking to build more accurate financial models or make informed investment decisions based on market forecasts.

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
        "period*",
        "string",
        [
          "annual",
          "quarter"
        ]
      ],
      [
        "page",
        "number",
        "0"
      ],
      [
        "limit",
        "number",
        "10"
      ]
    ]
  }
}
```

## Related API slugs
`grades-summary`, `ratings-snapshot`, `historical-ratings`, `grades`, `price-target-summary`
