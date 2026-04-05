# Aftermarket Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/aftermarket-quote](https://site.financialmodelingprep.com/developer/docs/stable/aftermarket-quote)

Access real-time aftermarket quotes for stocks with the FMP Aftermarket Quote API. Track bid and ask prices, volume, and other relevant data outside of regular trading hours.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/aftermarket-quote?symbol=AAPL`

## Description
The FMP Aftermarket Quote API provides comprehensive quotes for stocks traded outside of normal market hours. This API is essential for:


Tracking After-Hours Activity: See real-time bid and ask prices, volumes, and other key metrics after the stock market closes.
Strategic Analysis: Use aftermarket quotes to gain insights into market sentiment and stock performance beyond regular trading hours, helping you make better decisions for the next trading session.
Efficient Market Monitoring: Stay updated on price movements and trends that can affect next-day trading strategies.

With the Aftermarket Quote API, investors can efficiently monitor post-market movements, bid-ask spreads, and trading volumes to stay ahead of potential shifts in the market.

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
`quote-change`, `aftermarket-trade`, `full-mutualfund-quotes`, `quote`, `full-forex-quotes`
