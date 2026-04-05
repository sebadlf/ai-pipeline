# Delisted Companies

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/delisted-companies](https://site.financialmodelingprep.com/developer/docs/stable/delisted-companies)

Stay informed with the FMP Delisted Companies API. Access a comprehensive list of companies that have been delisted from US exchanges to avoid trading in risky stocks and identify potential financial troubles.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/delisted-companies?page=0&limit=100`

## Description
The FMP Delisted Companies API provides valuable information on companies that have been removed from US stock exchanges. This API is essential for investors who want to:


Avoid Trading in Delisted Stocks: Identify stocks that have been delisted to prevent potential losses from trading in these securities.
Understand Reasons for Delisting: Learn about the various factors that can lead to a company's delisting, such as financial difficulties, failure to comply with exchange regulations, or mergers and acquisitions.
Identify Financial Troubles: Use the delisted companies list as an indicator of potential financial instability or other underlying issues within a company.

This API helps investors make informed decisions by providing timely information on companies that are no longer publicly traded on US exchanges.

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
`latest-mergers-acquisitions`, `company-executives`, `profile-cik`, `employee-count`, `executive-compensation`
