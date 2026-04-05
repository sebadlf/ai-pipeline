# Index Short Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/index-quote-short](https://site.financialmodelingprep.com/developer/docs/stable/index-quote-short)

Access concise stock index quotes with the Stock Index Short Quote API. This API provides a snapshot of the current price, change, and volume for stock indexes, making it ideal for users who need a quick overview of market movements.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote-short?symbol=^GSPC`

## Description
The Stock Index Short Quote API delivers simplified, real-time index data, offering essential metrics such as price, change, and volume. This API is a valuable tool for traders, investors, and analysts who need a quick overview of an index's current standing without unnecessary details. Key features include:


Real-Time Index Data: Get current price, change, and volume for stock indexes.
Simplified Data: Designed for users who need only the essential figures, providing a clear and efficient market snapshot.
Wide Market Coverage: Retrieve short quotes for a wide range of global indexes.

This API is perfect for traders and analysts who want to stay updated on index performance at a glance, enabling them to react quickly to market shifts.

Example Use Case
A trader monitoring the S&P 500 throughout the trading day can use the Stock Index Short Quote API to quickly access real-time price changes, helping them make decisions on whether to buy or sell without delving into more complex data.

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
        "^GSPC"
      ]
    ]
  }
}
```

## Related API slugs
`index-intraday-5-min`, `historical-nasdaq`, `historical-dow-jones`, `historical-sp-500`, `indexes-list`
