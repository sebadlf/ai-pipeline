# Historical Market Cap

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-market-cap](https://site.financialmodelingprep.com/developer/docs/stable/historical-market-cap)

Access historical market capitalization data for a company using the FMP Historical Market Capitalization API. This API helps track the changes in market value over time, enabling long-term assessments of a company's growth or decline.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-market-capitalization?symbol=AAPL`

## Description
The FMP Historical Market Capitalization API allows users to retrieve past market cap data for any company listed in the database. Key features include:


Track Long-Term Performance: Retrieve historical market cap data to analyze how a company's value has evolved over time.
Identify Trends: Use historical data to spot trends, whether it's consistent growth, decline, or periods of volatility.
Informed Investment Decisions: Investors can use this data to evaluate a company's long-term performance and make more informed investment choices.

This API is ideal for analysts, portfolio managers, and investors looking to assess a company’s growth trajectory or historical performance in the market.

Example Use Case
An investor looking to evaluate Apple's historical performance can use the Historical Market Capitalization API to retrieve past market cap data. This helps them understand how Apple's valuation has changed over time, identifying periods of growth or decline and comparing it with overall market conditions.

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
        "100"
      ],
      [
        "from",
        "date",
        "2025-09-09"
      ],
      [
        "to",
        "date",
        "2025-12-09"
      ]
    ]
  }
}
```

## Related API slugs
`company-executives`, `company-notes`, `employee-count`, `shares-float`, `delisted-companies`
