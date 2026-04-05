# Industry Classification Search

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/industry-classification-search](https://site.financialmodelingprep.com/developer/docs/stable/industry-classification-search)

Search and retrieve industry classification details for companies, including SIC codes, industry titles, and business information, with the FMP Industry Classification Search API.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/industry-classification-search`

## Description
The FMP Industry Classification Search API allows users to search for company information based on their Standard Industrial Classification (SIC) codes. This API provides:


Company Lookup by Industry: Search for companies by industry classifications, retrieving details such as SIC codes, industry titles, and company contact information.
Business Information Access: Get comprehensive company information, including business addresses and phone numbers, making it easier to identify and classify businesses by their industry.
SIC Code Matching: Use this API to match companies with their corresponding industry sectors, enhancing your ability to perform industry-specific research and classification.

This API is valuable for businesses, investors, and researchers who need detailed company information tied to specific industry sectors.

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
        "symbol",
        "string",
        "AAPL"
      ],
      [
        "cik",
        "string",
        "320193"
      ],
      [
        "sicCode",
        "string",
        "7371"
      ]
    ]
  }
}
```

## Related API slugs
`8k-latest`, `company-search-by-symbol`, `search-by-symbol`, `all-industry-classification`, `company-search-by-cik`
