# 1-Hour Interval Commodities Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/commodities-intraday-1-hour](https://site.financialmodelingprep.com/developer/docs/stable/commodities-intraday-1-hour)

Monitor hourly price movements and trends with the FMP 1-Hour Interval Commodities Chart API. This API provides hourly data, offering a detailed look at price fluctuations throughout the trading day to support mid-term trading strategies and market analysis.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1hour?symbol=GCUSD`

## Description
The FMP 1-Hour Interval Commodities Chart API provides access to 1-hour interval pricing data for commodities, including open, high, low, and close prices, along with trading volume. This data is ideal for traders and analysts who need to track hourly trends, offering a balance between short-term and daily price analysis. By focusing on hourly intervals, users can capture significant intraday movements while avoiding the noise of minute-level fluctuations.


Hourly Trend Monitoring: Track price movements and trends for commodities with hourly updates, providing a clearer picture of market direction throughout the day.
Detailed Pricing Information: Retrieve open, high, low, and close prices for each hour, along with trading volume, to understand market activity during specific time frames.
Mid-Term Strategy Support: Use the hourly data to spot intraday trends, helping traders make more informed decisions and refine mid-term strategies.

This API is a valuable tool for traders, investors, and analysts looking to monitor price trends over the course of the trading day, providing actionable insights for strategic trades.

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
        "GCUSD"
      ],
      [
        "from",
        "date",
        "2024-01-01"
      ],
      [
        "to",
        "date",
        "2024-03-01"
      ]
    ]
  }
}
```

## Related API slugs
`commodities-historical-price-eod-light`, `commodities-quote`, `commodities-intraday-5-min`, `commodities-list`, `commodities-historical-price-eod-full`
