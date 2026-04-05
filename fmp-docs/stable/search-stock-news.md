# Search Stock News

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-stock-news](https://site.financialmodelingprep.com/developer/docs/stable/search-stock-news)

Search for stock-related news using the FMP Search Stock News API. Find specific stock news by entering a ticker symbol or company name to track the latest developments.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/stock?symbols=AAPL`

## Description
The Search Stock News API helps users find stock-related news by entering a specific company name or stock symbol. This tool is ideal for:


Targeted News Searches: Narrow down your search to find news about specific companies or stocks.
Symbol-Based Lookup: Quickly retrieve news by entering the relevant ticker symbol for a stock.
Comprehensive News Retrieval: Access both current and historical news reports to gain a full picture of stock movements over time.

This API is tailored for investors and analysts who require fast, reliable access to news affecting specific stocks.

Example Use Case
A trader uses the Search Stock News API to look up recent news articles about a stock they are considering buying, helping them make an informed decision.

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
        "AAPL"
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
`press-releases`, `crypto-news`, `forex-news`, `search-press-releases`, `search-forex-news`
