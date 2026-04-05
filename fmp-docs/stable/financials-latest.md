# Latest SEC Filings

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/financials-latest](https://site.financialmodelingprep.com/developer/docs/stable/financials-latest)

Stay updated with the most recent SEC filings from publicly traded companies using the FMP Latest SEC Filings API. Access essential regulatory documents, including financial statements, annual reports, 8-K, 10-K, and 10-Q forms.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/sec-filings-financials?from=2024-01-01&to=2024-03-01&page=0&limit=100`

## Description
The FMP Latest SEC Filings API provides real-time access to the latest SEC filings submitted by public companies. This API is essential for investors, analysts, and compliance professionals who need to stay informed about corporate financial disclosures and material events. Key features include:


Comprehensive Filing Access: Retrieve recent filings such as 8-K, 10-K, 10-Q, and other essential documents required by the SEC.
Real-Time Updates: Ensure you have the latest filings as they are accepted by the SEC, helping you stay informed about any material developments in the companies you follow.
Direct Filing Links: Quickly access full SEC filing documents for in-depth review and analysis of company disclosures.

This API is an invaluable resource for staying up-to-date with regulatory filings and understanding the financial and operational health of public companies.

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
`search-by-name`, `all-industry-classification`, `search-by-cik`, `company-search-by-symbol`, `industry-classification-search`
