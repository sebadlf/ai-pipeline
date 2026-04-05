# Mutual Fund Disclosures

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/mutual-fund-disclosures](https://site.financialmodelingprep.com/developer/docs/stable/mutual-fund-disclosures)

Access comprehensive disclosure data for mutual funds with the FMP Mutual Fund Disclosures API. Analyze recent filings, balance sheets, and financial reports to gain insights into mutual fund portfolios.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/funds/disclosure?symbol=VWO&year=2023&quarter=4`

## Description
The FMP Mutual Fund Disclosures API provides detailed information on mutual fund holdings and recent filings, allowing investors and financial professionals to:


Track Fund Holdings: Review the most recent disclosures of mutual fund holdings, including asset categories, issuer information, and country of investment. This helps users understand the portfolio composition of various mutual funds.
Analyze Recent Filings: Obtain critical financial reports and filings from mutual funds, including balance data, market value in USD, percentage of total portfolio value, and more. These insights can help with investment analysis and strategy development.
Gain Transparency into Investments: The API provides essential details like CUSIP, ISIN, issuer category, and fair value levels, offering full transparency into mutual fund investments.

For example, an investor can use this API to review the holdings of a mutual fund, such as Realty Income Corp, analyzing the balance, value in USD, and percentage of portfolio allocation to help make informed investment decisions.

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
        "VWO"
      ],
      [
        "year*",
        "string",
        "2023"
      ],
      [
        "quarter*",
        "string",
        "4"
      ],
      [
        "cik",
        "string",
        "0000857489"
      ]
    ]
  }
}
```

## Related API slugs
`holdings`, `information`, `disclosures-dates`, `disclosures-name-search`, `latest-disclosures`
