# Cryptocurrency Quote Short

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-quote-short](https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-quote-short)

Access real-time cryptocurrency quotes with the FMP Cryptocurrency Quick Quote API. Get a concise overview of current crypto prices, changes, and trading volume for a wide range of digital assets.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote-short?symbol=BTCUSD`

## Description
The FMP Cryptocurrency Quick Quote API provides users with immediate access to essential cryptocurrency price data. It’s designed for traders, investors, and analysts who need up-to-the-minute information on the crypto market, including:


Real-Time Crypto Prices: Retrieve the latest prices for popular cryptocurrencies like Bitcoin, Ethereum, and more.
Market Changes: View real-time price changes to stay informed of market fluctuations.
Trading Volume: Access data on trading volumes to assess market activity and liquidity for specific cryptocurrencies.

This API offers a quick and effective way to monitor cryptocurrency prices and make informed decisions based on real-time market data.

Example Use Case
A day trader can use the Cryptocurrency Quick Quote API to track the price of Bitcoin and monitor real-time changes in price and volume, helping them make quick trading decisions in volatile markets.

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
      ]
    ]
  }
}
```

## Related API slugs
`cryptocurrency-intraday-5-min`, `cryptocurrency-historical-price-eod-full`, `cryptocurrency-quote`, `cryptocurrency-intraday-1-hour`, `cryptocurrency-list`
