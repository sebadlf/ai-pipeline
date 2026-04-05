# Company Profile Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/profile-bulk](https://site.financialmodelingprep.com/developer/docs/stable/profile-bulk)

The FMP Profile Bulk API allows users to retrieve comprehensive company profile data in bulk. Access essential information, such as company details, stock price, market cap, sector, industry, and more for multiple companies in a single request.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/profile-bulk?part=0`

## Description
The FMP Profile Bulk API provides detailed profiles of companies across global stock exchanges. This API is ideal for users who need to:


Retrieve Comprehensive Data: Access company profiles that include stock prices, market capitalization, industry classification, and more.
Bulk Data Requests: Get company details for multiple organizations in one API call, making data collection more efficient.
Analyze Company Information: Use this data to gain insights into company operations, leadership, financials, and industry sectors.

This API is highly beneficial for financial analysts, data scientists, and anyone needing extensive company profile data for various organizations.

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
        "part*",
        "string",
        "0"
      ]
    ]
  }
}
```

## Related API slugs
`peers-bulk`, `eod-bulk`, `dcf-bulk`, `rating-bulk`, `income-statement-growth-bulk`
