# Filings Extract With Analytics By Holder

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/filings-extract-with-analytics-by-holder](https://site.financialmodelingprep.com/developer/docs/stable/filings-extract-with-analytics-by-holder)

The Filings Extract With Analytics By Holder API provides an analytical breakdown of institutional filings. This API offers insight into stock movements, strategies, and portfolio changes by major institutional holders, helping you understand their investment behavior and track significant changes in stock ownership.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/institutional-ownership/extract-analytics/holder?symbol=AAPL&year=2023&quarter=3&page=0&limit=10`

## Description
The Filings Extract With Analytics By Holder API allows users to extract detailed analytics from filings by institutional investors. It offers information such as shares held, changes in stock weight and market value, ownership percentages, and other important metrics that provide an analytical view of institutional investment strategies.


Institutional Investor Analysis: Track the behavior of large institutional holders such as Vanguard, including their changes in stock positions and market value.
Portfolio Movement Monitoring: Analyze stock movements and holding period data to see how long institutions have held a stock and when they increased or reduced their positions.
Investment Strategy Insights: Understand investment strategies by looking at changes in weight, market value, and ownership over time.

This API offers granular insights into how institutions manage their portfolios, providing data to investors and analysts for deeper investment analysis.

Example Use Case
An investment analyst can use the Filings Extract With Analytics By Holder API to monitor Vanguard Group's activity in Apple Inc. stocks, seeing how much stock Vanguard holds, any changes in weight or market value, and when the stock was first added to their portfolio.

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
        "year*",
        "string",
        "2023"
      ],
      [
        "quarter*",
        "string",
        "3"
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
`holders-industry-breakdown`, `industry-summary`, `form-13f-filings-dates`, `holder-performance-summary`, `filings-extract`
