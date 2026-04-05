# SEC Filings By Form Type

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-by-form-type](https://site.financialmodelingprep.com/developer/docs/stable/search-by-form-type)

Search for specific SEC filings by form type with the FMP SEC Filings By Form Type API. Retrieve filings such as 10-K, 10-Q, 8-K, and others, filtered by the exact type of document you're looking for.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/sec-filings-search/form-type?formType=8-K&from=2024-01-01&to=2024-03-01&page=0&limit=100`

## Description
The FMP SEC Filings By Form Type API allows users to filter and retrieve SEC filings based on the document's form type. Whether you're looking for annual reports (10-K), quarterly earnings (10-Q), or event-related filings (8-K), this API provides a streamlined way to access the exact forms needed for analysis or compliance:


Targeted Filings Search: Search for SEC filings by form type to retrieve specific reports such as 8-K, 10-K, 10-Q, and more.
Direct Links to Documents: Access the full filing and any associated exhibits directly from the SEC, ensuring complete visibility into company disclosures.
Regulatory Compliance Monitoring: Use this API to monitor filings related to compliance events, mergers, acquisitions, financial disclosures, and governance updates.

This API is an essential tool for investors, analysts, and regulatory professionals who need quick access to specific types of filings for compliance, analysis, or investment decisions.

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
        "formType*",
        "string",
        "8-K"
      ],
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
`search-by-cik`, `8k-latest`, `industry-classification-list`, `sec-company-full-profile`, `search-by-name`
