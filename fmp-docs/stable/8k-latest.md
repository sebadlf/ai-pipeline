# Latest 8-K SEC Filings

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/8k-latest](https://site.financialmodelingprep.com/developer/docs/stable/8k-latest)

Stay up-to-date with the most recent 8-K filings from publicly traded companies using the FMP Latest 8-K SEC Filings API. Get real-time access to significant company events such as mergers, acquisitions, leadership changes, and other material events that may impact the market.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/sec-filings-8k?from=2024-01-01&to=2024-03-01&page=0&limit=100`

## Description
The FMP Latest 8-K SEC Filings API provides timely updates on essential corporate events that are required to be disclosed to the public. These filings offer critical insights for investors and analysts, including:


Real-Time Filings: Access the latest 8-K filings as they are submitted to the SEC, ensuring you stay informed of key corporate developments.
Material Events: Track significant corporate events such as mergers, acquisitions, bankruptcies, changes in leadership, and more.
Direct Filing Links: Get direct access to SEC filing documents, providing you with complete details and disclosures from the companies.

This API is an invaluable tool for investors, analysts, and professionals who need to stay informed of market-moving corporate events.

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
        "from*",
        "string",
        "2024-01-01"
      ],
      [
        "to*",
        "string",
        "2024-03-01"
      ],
      [
        "page",
        "number",
        "0"
      ],
      [
        "limit",
        "number",
        "100"
      ]
    ]
  }
}
```

## Related API slugs
`all-industry-classification`, `company-search-by-cik`, `search-by-symbol`, `industry-classification-search`, `search-by-name`
