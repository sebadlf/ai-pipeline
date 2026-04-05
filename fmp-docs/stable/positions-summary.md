# Positions Summary

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/positions-summary](https://site.financialmodelingprep.com/developer/docs/stable/positions-summary)

The Positions Summary API provides a comprehensive snapshot of institutional holdings for a specific stock symbol. It tracks key metrics like the number of investors holding the stock, changes in the number of shares, total investment value, and ownership percentages over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/institutional-ownership/symbol-positions-summary?symbol=AAPL&year=2023&quarter=3`

## Description
The Positions Summary API enables users to analyze institutional positions in a particular stock by providing data such as the number of investors holding the stock, the number of shares held, the total amount invested, and changes in these metrics over a given time period. It is ideal for:


Tracking Institutional Investment Trends: Monitor how institutional investors are changing their positions in a stock over time.
Ownership Insights: Understand what percentage of a company is owned by institutional investors and how this changes.
Call & Put Analysis: Get insights into the put/call ratio and track options activity for institutional positions.

This API is ideal for understanding institutional activity in the market and gaining insights into the behavior of major investors. It is essential for investors, analysts, and portfolio managers who want to keep a close eye on institutional movements in specific stocks.

Example Use Case
A hedge fund manager can use the Positions Summary API to track institutional ownership trends in Apple (AAPL), monitoring how many institutions are increasing or reducing their positions, and assessing overall market sentiment.

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
      ]
    ]
  }
}
```

## Related API slugs
`filings-extract`, `form-13f-filings-dates`, `holders-industry-breakdown`, `latest-filings`, `holder-performance-summary`
