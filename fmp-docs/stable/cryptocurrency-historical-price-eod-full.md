# Historical Cryptocurrency Full Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-historical-price-eod-full](https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-historical-price-eod-full)

Access comprehensive end-of-day (EOD) price data for cryptocurrencies with the Full Historical Cryptocurrency Data API. Analyze long-term price trends, market movements, and trading volumes to inform strategic decisions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/full?symbol=BTCUSD`

## Description
The Full Historical Cryptocurrency Data API provides extensive historical data, including:


End-of-Day (EOD) Prices: Retrieve daily open, high, low, close (OHLC) price data for cryptocurrencies.
Comprehensive Market Data: Access trading volumes, price changes, and VWAP (Volume Weighted Average Price) to gain insights into market behavior.
Analyze Long-Term Trends: Review historical price data to track long-term trends, volatility, and market cycles, enabling better decision-making for investors and analysts.

This API is essential for long-term investors, analysts, and institutions seeking to evaluate market movements, identify trends, and support strategic planning.

Example Use Case
A long-term cryptocurrency investor could use the Full Historical Cryptocurrency Data API to analyze Bitcoin’s market performance over the past year, identifying key resistance levels and potential buying opportunities based on historical price trends.

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
`cryptocurrency-intraday-5-min`, `cryptocurrency-historical-price-eod-light`, `cryptocurrency-quote`, `cryptocurrency-intraday-1-min`, `cryptocurrency-quote-short`
