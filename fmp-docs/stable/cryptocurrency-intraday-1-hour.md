# 1-Hour Interval Cryptocurrency Data

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-intraday-1-hour](https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-intraday-1-hour)

Access detailed 1-hour intraday price data for cryptocurrencies with the 1-Hour Interval Cryptocurrency Data API. Track hourly price movements to gain insights into market trends and make informed trading decisions throughout the day.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1hour?symbol=BTCUSD`

## Description
The 1-Hour Interval Cryptocurrency Data API provides key hourly updates on cryptocurrency prices, offering users a granular view of market fluctuations:


Hourly Price Updates: Receive cryptocurrency price data, including open, high, low, and close (OHLC) prices, as well as trading volumes, updated every hour.
Comprehensive Market Monitoring: Use hourly data to monitor market trends, track price momentum, and identify potential trading opportunities.
Effective for Trend Analysis: Leverage hourly intervals to observe intraday price patterns, helping you make better decisions for day trading, swing trading, or long-term analysis.

This API is ideal for traders and investors who want a closer look at how prices evolve over the course of a trading day, enabling them to act swiftly in fast-paced markets.

Example Use Case
A swing trader uses the 1-Hour Interval Cryptocurrency Data API to monitor the price of Ethereum. By analyzing hourly trends, the trader can spot potential breakouts or pullbacks and adjust their positions accordingly.

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
        "BTCUSD"
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
`cryptocurrency-intraday-1-min`, `cryptocurrency-intraday-5-min`, `cryptocurrency-historical-price-eod-light`, `cryptocurrency-quote-short`, `cryptocurrency-quote`
