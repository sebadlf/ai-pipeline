# FMP Articles

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/fmp-articles](https://site.financialmodelingprep.com/developer/docs/stable/fmp-articles)

Access the latest articles from Financial Modeling Prep with the FMP Articles API. Get comprehensive updates including headlines, snippets, and publication URLs.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/fmp-articles?page=0&limit=20`

## Description
The FMP Articles API provides access to a curated list of the most recent articles published by Financial Modeling Prep. This endpoint offers:


Headlines: Stay informed with the latest headlines covering a wide range of financial topics.
Snippets: Quickly grasp the key points of each article with concise snippets.
Publication URLs: Access the full articles through provided URLs for in-depth reading.

This API is updated regularly to ensure you have access to the most current content, helping you stay informed about the latest trends, insights, and analyses from Financial Modeling Prep.

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
`press-releases`, `forex-news`, `search-forex-news`, `general-news`, `search-press-releases`
