# Forex News

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/forex-news](https://site.financialmodelingprep.com/developer/docs/stable/forex-news)

Stay updated with the latest forex news articles from various sources using the FMP Forex News API. Access headlines, snippets, and publication URLs for comprehensive market insights.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/forex-latest?page=0&limit=20`

## Description
The Forex News API provides up-to-date reports on currency markets, ensuring you stay informed about:


Currency Market Movements: Get real-time updates on the forex market, including major events and macro-economic trends that influence currency pairs.
Currency Pair Analysis: Stay informed on specific currency pair movements, such as EUR/USD, GBP/USD, or JPY/CHF, to better understand market conditions.
Market Sentiment Updates: Follow forex-related news to gauge investor sentiment and market dynamics in the foreign exchange sector.

This API is essential for traders, analysts, and financial professionals who need to stay on top of the ever-changing forex markets.

Example Use Case
A forex trader uses the Forex News API to track the latest news on currency pairs, helping them make quick and informed trading decisions.

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
`search-stock-news`, `general-news`, `press-releases`, `search-press-releases`, `fmp-articles`
