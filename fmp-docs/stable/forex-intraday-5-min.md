# 5-Minute Interval Forex Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/forex-intraday-5-min](https://site.financialmodelingprep.com/developer/docs/stable/forex-intraday-5-min)

Track short-term forex trends with the 5-Minute Forex Interval Chart API. Access detailed 5-minute intraday data to monitor currency pair price movements and market conditions in near real-time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/5min?symbol=EURUSD`

## Description
The 5-Minute Forex Interval Chart API offers critical price data at 5-minute intervals, making it ideal for traders and analysts focused on short-term trends. With open, high, low, close (OHLC) prices and volume data for each 5-minute period, this API supports:


Intraday Trading Strategies: Perfect for traders looking to capture price trends and make informed decisions within short timeframes.
Monitoring Currency Pair Volatility: Follow price movements closely during key market sessions to capitalize on fluctuations in exchange rates.
Near-Term Trend Analysis: Use this API for technical analysis and to spot patterns or breakouts that occur over 5-minute periods.

This API is a valuable tool for forex traders aiming to understand and react to market conditions quickly, as well as for analysts seeking to track short-term currency pair movements.

Example Use Case
A forex trader monitoring the EUR/USD pair uses the 5-Minute Forex Interval Chart API to analyze price fluctuations during volatile periods. By tracking 5-minute intervals, the trader makes informed decisions on when to enter or exit trades.

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
        "EURUSD"
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
`forex-quote`, `forex-historical-price-eod-full`, `all-forex-quotes`, `forex-intraday-1-hour`, `forex-intraday-1-min`
