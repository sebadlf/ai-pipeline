# Latest Insider Trading

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/latest-insider-trade](https://site.financialmodelingprep.com/developer/docs/stable/latest-insider-trade)

Access the latest insider trading activity using the Latest Insider Trading API. Track which company insiders are buying or selling stocks and analyze their transactions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/insider-trading/latest?page=0&limit=100`

## Description
The FMP Latest Insider Trading API provides up-to-date information on insider trading activities. This API enables users to track recent stock purchases and sales by company insiders, including directors and executives. With details on transaction dates, types, and amounts, this API offers insights into corporate behavior and potential market trends. Key features include:


Recent Insider Transactions: Access the most recent stock purchases or sales by company insiders.
Transaction Details: Retrieve detailed information about the type of transaction, the number of shares transacted, and the price.
Insider Roles: Identify the roles of the individuals involved in the transactions, such as directors or executives.
Comprehensive Data: Access key information such as filing date, transaction date, type of ownership, and links to official filings.

This API is ideal for investors, analysts, and financial researchers who want to track insider trading activity to assess market sentiment or potential investment opportunities.

Example Use Case
A hedge fund manager uses the Latest Insider Trading API to monitor recent stock purchases by company directors. By analyzing a purchase made by Larry Glasscock (director of SPG), they can assess whether the insider's buying activity signals confidence in the company’s future performance and adjust their investment strategy accordingly.

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
        "date",
        "date",
        "2025-09-09"
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
`acquisition-ownership`, `insider-trade-statistics`, `all-transaction-types`, `search-insider-trades`, `search-reporting-name`
