# 1-Hour Interval Forex Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/forex-intraday-1-hour](https://site.financialmodelingprep.com/developer/docs/stable/forex-intraday-1-hour)

Track forex price movements over the trading day with the 1-Hour Forex Interval Chart API. This tool provides hourly intraday data for currency pairs, giving a detailed view of trends and market shifts.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1hour?symbol=EURUSD`

## Description
The 1-Hour Forex Interval Chart API delivers comprehensive OHLC (open, high, low, close) price and volume data for each 1-hour period. It’s an essential tool for forex traders and analysts who need to:


Monitor Intraday Market Activity: Follow price changes in 1-hour increments throughout the trading day, making it easier to spot trends or reversals.
Analyze Long-Term Intraday Patterns: Use 1-hour data to gain insights into the broader movements of currency pairs over the course of the trading day.
Support Swing Trading Strategies: With hourly updates, this API is perfect for traders who operate in mid-term strategies, reacting to larger market trends.

Whether you're actively trading or conducting market analysis, the 1-Hour Forex Interval Chart API helps provide the necessary data to make informed decisions based on evolving market conditions.

Example Use Case
A forex analyst looking to optimize their swing trading strategy uses the 1-Hour Forex Interval Chart API to track price movements of the USD/JPY pair. By monitoring hourly changes, the analyst identifies price consolidation points and adjusts their trades accordingly.

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
`forex-quote`, `forex-quote-short`, `forex-historical-price-eod-full`, `forex-historical-price-eod-light`, `forex-list`
