# Historical Cryptocurrency Light Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-historical-price-eod-light](https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-historical-price-eod-light)

Access historical end-of-day prices for a variety of cryptocurrencies with the Historical Cryptocurrency Price Snapshot API. Track trends in price and trading volume over time to better understand market behavior.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/light?symbol=BTCUSD`

## Description
The Historical Cryptocurrency Price Snapshot API provides crucial insights into the performance of cryptocurrencies over time by offering:


End-of-Day Prices: Retrieve historical end-of-day prices for cryptocurrencies, allowing you to analyze long-term market trends and patterns.
Trading Volume Data: Access volume data to evaluate market activity during specific time frames.
Price Trend Analysis: Use this data to review how a cryptocurrency's value has changed, assisting in making informed investment decisions.

This API is essential for traders, analysts, and investors looking to perform technical analysis or monitor how the market has evolved over time.

Example Use Case
An analyst can use the Historical Cryptocurrency Price Snapshot API to backtest trading strategies by reviewing past price movements and identifying patterns that could influence future price action.

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
`cryptocurrency-intraday-1-min`, `cryptocurrency-quote`, `cryptocurrency-intraday-1-hour`, `cryptocurrency-quote-short`, `cryptocurrency-intraday-5-min`
