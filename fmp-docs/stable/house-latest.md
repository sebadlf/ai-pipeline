# Latest House Financial Disclosures

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/house-latest](https://site.financialmodelingprep.com/developer/docs/stable/house-latest)

Access real-time financial disclosures from U.S. House members with the FMP Latest House Financial Disclosures API. Track recent trades, asset ownership, and financial holdings for enhanced visibility into political figures' financial activities.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/house-latest?page=0&limit=100`

## Description
The FMP Latest House Financial Disclosures API provides up-to-date information on trades, sales, and financial assets held by members of the U.S. House of Representatives. This API allows users to:


Monitor House Member Transactions: Access recent financial disclosures that detail the transactions and asset ownership of U.S. House members and their families.
Comprehensive Transaction Data: View detailed information, including asset types, transaction amounts, dates, and whether capital gains were reported.
Stay Informed: Gain insights into the investment activities of elected officials and track any changes in their holdings.

This API is ideal for users who seek transparency and accountability in the financial dealings of government representatives.

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
        "100"
      ]
    ]
  }
}
```

## Related API slugs
`senate-latest`, `senate-trading`, `house-trading`
