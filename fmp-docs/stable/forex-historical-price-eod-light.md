# Historical Forex Light Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/forex-historical-price-eod-light](https://site.financialmodelingprep.com/developer/docs/stable/forex-historical-price-eod-light)

Access historical end-of-day forex prices with the Historical Forex Light Chart API. Track long-term price trends across different currency pairs to enhance your trading and analysis strategies.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/light?symbol=EURUSD`

## Description
The Historical Forex Light Chart API provides end-of-day forex prices for a wide range of currency pairs. This data is invaluable for traders and analysts looking to:


Analyze Long-Term Trends: Review historical price data to identify patterns and trends that could influence future market movements.
Backtest Trading Strategies: Use past data to validate trading strategies by simulating market conditions over extended timeframes.
Compare Forex Pair Performance: Analyze the performance of different forex pairs over time, helping you make more informed trading decisions.

This API is essential for forex traders, analysts, and investors who need access to accurate historical data for market analysis and strategy development.

Example Use Case
A forex trader uses the Historical Forex Light Chart API to review end-of-day prices for the EUR/USD currency pair over the past five years. By analyzing this data, the trader identifies key support and resistance levels, helping refine their trading strategy.

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
        "2025-09-09"
      ],
      [
        "to",
        "date",
        "2025-12-09"
      ]
    ]
  }
}
```

## Related API slugs
`forex-list`, `forex-intraday-1-hour`, `forex-historical-price-eod-full`, `all-forex-quotes`, `forex-intraday-5-min`
