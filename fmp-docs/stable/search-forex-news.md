# Search Forex News

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-forex-news](https://site.financialmodelingprep.com/developer/docs/stable/search-forex-news)

Search for foreign exchange news using the FMP Search Forex News API. Find targeted news on specific currency pairs by entering their symbols for focused updates.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/forex?symbols=EURUSD`

## Description
The Search Forex News API allows users to look up forex news by entering a currency pair, such as EUR/USD or GBP/USD. This API is perfect for:


Targeted News Search: Easily find news about specific currency pairs to track the latest developments in the forex market.
Historical News Access: Look up both current and historical forex news to analyze long-term trends and market movements.
Symbol-Based Retrieval: Enter specific currency pair symbols to retrieve relevant news for informed decision-making.

This API is ideal for forex traders who need quick access to news related to specific currency pairs.

Example Use Case
A currency trader uses the Search Forex News API to search for the latest news on EUR/USD, helping them understand recent price fluctuations before entering a trade.

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
        "EURUSD"
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
`crypto-news`, `forex-news`, `press-releases`, `search-stock-news`, `fmp-articles`
