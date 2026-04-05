# Latest Senate Financial Disclosures

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/senate-latest](https://site.financialmodelingprep.com/developer/docs/stable/senate-latest)

Access the latest financial disclosures from U.S. Senate members with the FMP Latest Senate Financial Disclosures API. Track recent trades, asset ownership, and transaction details for enhanced transparency in government financial activities.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/senate-latest?page=0&limit=100`

## Description
The FMP Latest Senate Financial Disclosures API provides up-to-date information on trades and asset ownership by U.S. Senate members. With this API, users can:


Monitor Senate Member Transactions: Access real-time disclosures detailing trades, sales, and purchases made by U.S. Senate members and their families.
Detailed Transaction Data: Retrieve transaction details, including asset types (stocks, bonds, real estate), transaction dates, amounts, and ownership types.
Stay Informed: Follow recent disclosures to stay informed about financial activity by key political figures.

This API is essential for those who want to track political figures' financial activities and understand their investment behaviors.

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
`house-latest`, `senate-trading`, `house-trading`
