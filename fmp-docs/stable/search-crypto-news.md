# Search Crypto News

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-crypto-news](https://site.financialmodelingprep.com/developer/docs/stable/search-crypto-news)

Search for cryptocurrency news using the FMP Search Crypto News API. Retrieve news related to specific coins or tokens by entering their name or symbol.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/crypto?symbols=BTCUSD`

## Description
The Search Crypto News API allows users to look up cryptocurrency news by entering a coin name or symbol. This API is helpful for:


Targeted Searches: Quickly find news on specific cryptocurrencies by entering their name or ticker symbol.
Real-Time & Historical News: Retrieve both current and past news on digital assets to track market trends and price drivers.
Symbol-Based Lookups: Find news related to your preferred coins, such as Bitcoin (BTC) or Ethereum (ETH).

This API is ideal for cryptocurrency investors who need fast access to news that could affect the value of their digital assets.

Example Use Case
A crypto investor uses the Search Crypto News API to search for news on Ethereum to understand the recent market movements before making a trade.

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
        "2025-12-10"
      ],
      [
        "page",
        "number",
        "0"
      ],
      [
        "limit",
        "number",
        "20"
      ]
    ]
  }
}
```

## Related API slugs
`search-forex-news`, `forex-news`, `crypto-news`, `search-stock-news`, `search-press-releases`
