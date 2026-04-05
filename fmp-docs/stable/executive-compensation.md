# Executive Compensation

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/executive-compensation](https://site.financialmodelingprep.com/developer/docs/stable/executive-compensation)

Retrieve comprehensive compensation data for company executives with the FMP Executive Compensation API. This API provides detailed information on salaries, stock awards, total compensation, and other relevant financial data, including filing details and links to official documents.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/governance-executive-compensation?symbol=AAPL`

## Description
The FMP Executive Compensation API is designed to give investors, analysts, and researchers a complete overview of executive compensation for publicly traded companies. This API is beneficial for:


Executive Salary & Benefits: Retrieve data on annual salaries, stock awards, bonuses, and incentive plans.
Comprehensive Compensation Breakdown: Access detailed reports on total compensation, including base pay and additional awards or incentives.
Filing Information: Includes key filing dates and direct links to SEC filings for deeper analysis of compensation packages.

This API provides valuable insights into how company executives are compensated, helping users understand leadership incentives and assess company governance.

Example Use Case
A compensation analyst can use the Executive Compensation API to compare CEO pay across different companies, analyzing how various forms of compensation—such as salary, stock awards, and performance incentives—impact executive behavior and company performance.

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
      ]
    ]
  }
}
```

## Related API slugs
`company-executives`, `batch-market-cap`, `all-shares-float`, `employee-count`, `company-notes`
