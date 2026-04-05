# Industry Classification List

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/industry-classification-list](https://site.financialmodelingprep.com/developer/docs/stable/industry-classification-list)

Retrieve a comprehensive list of industry classifications, including Standard Industrial Classification (SIC) codes and industry titles with the FMP Industry Classification List API.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/standard-industrial-classification-list`

## Description
The FMP Industry Classification List API provides a complete directory of SIC codes and corresponding industry titles. This API is essential for:


Industry Research: Access an organized list of industries with SIC codes, allowing users to categorize companies based on their industry sector.
Company Classification: Retrieve SIC codes for industries ranging from manufacturing to services, helping users classify and analyze companies by their primary business activities.
Standardized Data: Ensure consistency when researching or classifying companies, as this API provides standardized SIC codes and official industry titles.

This API is ideal for analysts, researchers, and businesses looking to categorize companies based on industry standards.

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
        "industryTitle",
        "string",
        "SERVICES"
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
`search-by-name`, `8k-latest`, `search-by-cik`, `company-search-by-cik`, `all-industry-classification`
