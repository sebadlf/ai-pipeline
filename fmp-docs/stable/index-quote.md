# Index Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/index-quote](https://site.financialmodelingprep.com/developer/docs/stable/index-quote)

Access real-time stock index quotes with the Stock Index Quote API. Stay updated with the latest price changes, daily highs and lows, volume, and other key metrics for major stock indices around the world.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote?symbol=^GSPC`

## Description
The Stock Index Quote API provides real-time data on the performance of stock indices, offering a comprehensive view of current market conditions. This API is essential for:


Tracking Market Performance: Monitor the real-time movements of key stock indices, like the S&P 500 or NASDAQ, to stay informed about overall market trends.
Portfolio Management: Use index data to evaluate the health of your investments relative to the broader market.
Global Market Insights: Access index data across various markets and exchanges, allowing for a global market view.
Day Trading: Keep track of daily price movements, highs, lows, and volumes for real-time decision-making.

Example Use Case

A trader could use the Stock Index Quote API to track the S&P 500’s daily performance in real-time, enabling them to make informed trading decisions based on market trends and volume.

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
`index-intraday-1-min`, `dow-jones`, `historical-dow-jones`, `nasdaq`, `index-historical-price-eod-full`
