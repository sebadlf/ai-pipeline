# All Shares Float

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/all-shares-float](https://site.financialmodelingprep.com/developer/docs/stable/all-shares-float)

Access comprehensive shares float data for all available companies with the FMP All Shares Float API. Retrieve critical information such as free float, float shares, and outstanding shares to analyze liquidity across a wide range of companies.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/shares-float-all?page=0&limit=1000`

## Description
The FMP All Shares Float API provides valuable data on the liquidity of publicly traded companies by offering insights into shares available for trading. This API is essential for investors, analysts, and financial professionals seeking to understand a company's market activity. Key features include:


Free Float Data: Understand the number of shares available for public trading, excluding closely held shares owned by insiders, employees, or major shareholders.
Float Shares & Outstanding Shares: Retrieve the total number of shares that are both floating on the market and outstanding, helping you analyze a company's total market exposure.
Comparative Liquidity Analysis: With access to free float and outstanding shares across multiple companies, you can compare liquidity, determine market stability, and evaluate investment potential.

This API serves as a critical resource for evaluating the ease with which shares can be bought or sold on the open market, offering a detailed picture of company share availability and market behavior.

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
        "limit",
        "number",
        "1000"
      ],
      [
        "page",
        "number",
        "0"
      ]
    ]
  }
}
```

## Related API slugs
`profile-symbol`, `latest-mergers-acquisitions`, `batch-market-cap`, `peers`, `company-executives`
