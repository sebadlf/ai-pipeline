# Crypto News

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/crypto-news](https://site.financialmodelingprep.com/developer/docs/stable/crypto-news)

Stay informed with the latest cryptocurrency news using the FMP Crypto News API. Access a curated list of articles from various sources, including headlines, snippets, and publication URLs.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/crypto-latest?page=0&limit=20`

## Description
The Crypto News API provides up-to-date news on cryptocurrencies, including key market events and trends. This API is critical for:


Real-Time Updates: Receive the latest news on major cryptocurrencies like Bitcoin, Ethereum, and more.
Market Sentiment Analysis: Follow news and reports that could influence crypto market sentiment and price movements.
Cryptocurrency Trends: Stay informed about industry developments, new technologies, and regulatory updates.

This API is a must-have for anyone involved in the fast-moving world of cryptocurrency investing and trading.

Example Use Case
A crypto trader uses the Crypto News API to track daily news on Bitcoin and Ethereum, enabling them to stay ahead of market trends.

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
`search-crypto-news`, `stock-news`, `search-stock-news`, `fmp-articles`, `forex-news`
