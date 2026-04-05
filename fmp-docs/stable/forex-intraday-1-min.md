# 1-Minute Interval Forex Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/forex-intraday-1-min](https://site.financialmodelingprep.com/developer/docs/stable/forex-intraday-1-min)

Access real-time 1-minute intraday forex data with the 1-Minute Forex Interval Chart API. Track short-term price movements for precise, up-to-the-minute insights on currency pair fluctuations.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1min?symbol=EURUSD`

## Description
The 1-Minute Forex Interval Chart API provides high-frequency intraday data, offering a detailed view of currency pair price changes every minute. With real-time open, high, low, close (OHLC) prices and volume data, this API is ideal for:


Scalping and Day Trading: Traders focused on quick entry and exit points can leverage minute-by-minute data for highly dynamic market conditions.
High-Frequency Monitoring: Closely monitor short-term forex price movements to seize opportunities or manage risk during volatile market sessions.
Short-Term Strategy Execution: Apply rapid trading strategies and technical analysis to capture fleeting trends and minimize risk.

By using this API, traders can make timely and informed decisions in fast-moving forex markets, making it essential for high-frequency traders and those employing short-term strategies.

Example Use Case
A day trader uses the 1-Minute Forex Interval Chart API to track price movements in the EUR/USD currency pair. By monitoring each minute’s open, high, low, and close prices, the trader executes a scalping strategy and optimizes profit opportunities within a single trading session.

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
`forex-historical-price-eod-full`, `forex-historical-price-eod-light`, `forex-intraday-1-hour`, `forex-intraday-5-min`, `all-forex-quotes`
