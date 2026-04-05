# All Cryptocurrencies Quotes

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/all-cryptocurrency-quotes](https://site.financialmodelingprep.com/developer/docs/stable/all-cryptocurrency-quotes)

Access live price data for a wide range of cryptocurrencies with the FMP Real-Time Cryptocurrency Batch Quotes API. Get real-time updates on prices, market changes, and trading volumes for digital assets in a single request.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-crypto-quotes`

## Description
The FMP Real-Time Cryptocurrency Batch Quotes API is designed for investors, traders, and financial analysts who need to track multiple cryptocurrency prices simultaneously. This API provides:


Real-Time Cryptocurrency Prices: Retrieve current prices for a broad range of digital assets in a single batch request.
Market Movement Tracking: Keep up with price changes to stay ahead of trends in the fast-paced crypto market.
Volume Data: Access trading volume information to gauge liquidity and market activity.

This API is ideal for users who need quick, real-time access to prices and trading volumes for a variety of cryptocurrencies in one convenient response.

Example Use Case
A portfolio manager can use the Real-Time Cryptocurrency Batch Quotes API to monitor the prices and market activity of multiple cryptocurrencies in real-time, allowing them to make quick and informed decisions across their digital asset portfolio.

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
        "short",
        "boolean",
        "true"
      ]
    ]
  }
}
```

## Related API slugs
`cryptocurrency-quote-short`, `cryptocurrency-intraday-1-min`, `cryptocurrency-intraday-1-hour`, `cryptocurrency-quote`, `cryptocurrency-intraday-5-min`
