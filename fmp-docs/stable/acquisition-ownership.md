# Acquisition Ownership

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/acquisition-ownership](https://site.financialmodelingprep.com/developer/docs/stable/acquisition-ownership)

Track changes in stock ownership during acquisitions using the Acquisition Ownership API. This API provides detailed information on how mergers, takeovers, or beneficial ownership changes impact the stock ownership structure of a company.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/acquisition-of-beneficial-ownership?symbol=AAPL`

## Description
The FMP Acquisition Ownership API provides comprehensive data on changes in stock ownership during acquisitions, mergers, or other significant corporate events. It offers insight into how control and ownership are transferred or shared between entities, helping analysts and investors understand the impact of these changes on corporate governance and shareholder influence. Key features include:


Ownership Changes: Track changes in beneficial ownership, including shared or sole voting and dispositive powers.
Acquisition and Merger Data: View details about mergers, takeovers, or acquisitions that affect the ownership of company stock.
Detailed Reporting Information: Access data about the reporting entities, including their CIK, name, and percentage of ownership.
Filing Dates and SEC Links: Get links to official SEC filings and important dates related to acquisitions or ownership changes.

This API is ideal for investors, financial analysts, and researchers who need to track how ownership structures shift during corporate acquisitions or mergers.

Example Use Case
An institutional investor uses the Acquisition Ownership API to monitor the impact of a recent merger involving Apple (AAPL). By examining the beneficial ownership change reported by National Indemnity Company, which now holds 755 million shares, the investor can assess how this affects voting power and control within the company.

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
        "symbol*",
        "string",
        "AAPL"
      ],
      [
        "limit",
        "number",
        "2000"
      ]
    ]
  }
}
```

## Related API slugs
`search-insider-trades`, `insider-trade-statistics`, `all-transaction-types`, `latest-insider-trade`, `search-reporting-name`
