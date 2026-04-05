# Search Press Releases

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-press-releases](https://site.financialmodelingprep.com/developer/docs/stable/search-press-releases)

Search for company press releases with the FMP Search Press Releases API. Find specific corporate announcements and updates by entering a stock symbol or company name.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/press-releases?symbols=AAPL`

## Description
The Search Press Releases API allows users to find specific press releases based on a company name or stock symbol, offering quick access to relevant announcements. This API is essential for:


Targeted Searches: Narrow down your search to find exact press releases from a particular company.
Symbol-Based Retrieval: Use stock symbols to pinpoint corporate disclosures, making it ideal for investors and analysts looking for precise data.
Historical and Real-Time Access: Retrieve both current and past press releases, helping with long-term trend analysis.

This API is designed for professionals who need quick, reliable access to specific press releases, saving time and providing accurate data.

Example Use Case
An investor uses the Search Press Releases API to find the most recent earnings report of a specific company before making an investment decision.

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
`crypto-news`, `stock-news`, `forex-news`, `search-forex-news`, `search-stock-news`
