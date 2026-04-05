# Stock Quote Short

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/quote-short](https://site.financialmodelingprep.com/developer/docs/stable/quote-short)

Get quick snapshots of real-time stock quotes with the FMP Stock Quote Short API. Access key stock data like current price, volume, and price changes for instant market insights.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote-short?symbol=AAPL`

## Description
The FMP Stock Quote Short API provides a concise, real-time snapshot of essential stock information, making it perfect for quick checks and streamlined data retrieval. This API is ideal for:


Quick Stock Monitoring: Get key data such as current stock price, price change, and trading volume with minimal delay.
High-Frequency Trading: Traders looking for rapid updates can use this API to stay ahead of the market in a streamlined format.
Simplified Data Feed: For applications requiring lightweight data, the short format is efficient and easy to integrate.

This API delivers the core metrics you need to make fast, informed trading decisions without unnecessary data points.

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
      ]
    ]
  }
}
```

## Related API slugs
`batch-aftermarket-quote`, `batch-aftermarket-trade`, `aftermarket-trade`, `batch-quote-short`, `full-forex-quotes`
