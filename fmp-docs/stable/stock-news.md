# Stock News

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/stock-news](https://site.financialmodelingprep.com/developer/docs/stable/stock-news)

Stay informed with the latest stock market news using the FMP Stock News Feed API. Access headlines, snippets, publication URLs, and ticker symbols for the most recent articles from a variety of sources.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/stock-latest?page=0&limit=20`

## Description
The Stock News API offers up-to-date information on stock market events, keeping traders, investors, and financial professionals informed about:


Breaking Market News: Access the latest headlines that may impact stock prices and market movements.
Company-Specific News: Stay updated on news related to individual stocks, including earnings reports, product announcements, and mergers.
Market Trends and Analysis: Follow broader market trends and sentiment to make better investment decisions.

This API is designed to provide timely news that helps professionals track stock market developments and make informed decisions.

Example Use Case
A portfolio manager uses the Stock News API to track real-time updates on the stock markets, ensuring they are aware of any news that may affect the performance of the equities in their portfolio.

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
`search-stock-news`, `general-news`, `search-crypto-news`, `crypto-news`, `forex-news`
