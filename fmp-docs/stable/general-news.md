# General News

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/general-news](https://site.financialmodelingprep.com/developer/docs/stable/general-news)

Access the latest general news articles from a variety of sources with the FMP General News API. Obtain headlines, snippets, and publication URLs for comprehensive news coverage.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/general-latest?page=0&limit=20`

## Description
The FMP General News API provides access to the latest general news articles from a wide range of sources. This endpoint includes:


Headlines: Stay informed with the latest headlines on current events.
Snippets: Get brief summaries of the articles to quickly understand the key points.
Publication URLs: Access full articles through provided URLs for detailed information.

This API is updated daily to ensure you have the most current news. Simply provide the date range you are interested in, and the endpoint will return a list of all general news articles published during that period.

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
`search-stock-news`, `search-crypto-news`, `fmp-articles`, `press-releases`, `stock-news`
