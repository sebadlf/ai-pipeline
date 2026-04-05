# Press Releases

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/press-releases](https://site.financialmodelingprep.com/developer/docs/stable/press-releases)

Access official company press releases with the FMP Press Releases API. Get real-time updates on corporate announcements, earnings reports, mergers, and more.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/news/press-releases-latest?page=0&limit=20`

## Description
The Press Releases API provides real-time access to official company announcements, allowing investors, analysts, and business professionals to stay informed on the latest developments. This API is crucial for:


Company Announcements: Stay informed about earnings reports, product launches, mergers, and more directly from companies.
Strategic Updates: Track leadership changes, business restructuring, and other significant corporate strategies that may affect a company's market standing.
Market Impact Analysis: Analyze how company press releases influence stock prices, company valuations, and market sentiment.

This API ensures that you have access to the most current press releases, helping you make informed decisions based on the latest corporate disclosures.

Example Use Case
A financial analyst uses the Press Releases API to monitor corporate announcements from publicly traded companies, providing critical insights for investment decisions.

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
`search-press-releases`, `crypto-news`, `fmp-articles`, `search-stock-news`, `search-forex-news`
