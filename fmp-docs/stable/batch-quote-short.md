# Stock Batch Quote Short

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/batch-quote-short](https://site.financialmodelingprep.com/developer/docs/stable/batch-quote-short)

Access real-time, short-form quotes for multiple stocks with the FMP Stock Batch Quote Short API. Get a quick snapshot of key stock data such as current price, change, and volume for several companies in one streamlined request.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-quote-short?symbols=AAPL`

## Description
The FMP Stock Batch Quote Short API is designed for users who need quick, high-level data for multiple stocks in one go. This API is ideal for:


Quick Price Monitoring: Get a snapshot of current prices, changes, and volume for several stocks at once, helping you keep tabs on market trends.
Portfolio Efficiency: Track essential stock data for multiple holdings in a single request, perfect for portfolio managers or traders who need rapid updates.
Streamlined Data Retrieval: Skip the detailed data and focus on the basics—price, change, and volume—giving you the key insights quickly and efficiently.

This API provides a fast and efficient way to monitor key stock information for multiple companies, all in one simple request.

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
        "symbols*",
        "string",
        "AAPL"
      ]
    ]
  }
}
```

## Related API slugs
`full-cryptocurrency-quotes`, `batch-aftermarket-quote`, `batch-aftermarket-trade`, `full-index-quotes`, `quote`
