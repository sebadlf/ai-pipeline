# Company Employee Count

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/employee-count](https://site.financialmodelingprep.com/developer/docs/stable/employee-count)

Retrieve detailed workforce information for companies, including employee count, reporting period, and filing date. The FMP Company Employee Count API also provides direct links to official SEC documents for further verification and in-depth research.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/employee-count?symbol=AAPL`

## Description
The FMP Company Employee Count API offers users access to essential data regarding a company’s workforce size. This API is especially valuable for analysts, investors, and HR professionals who need to understand company operations, staffing trends, and workforce management. Key features include:


Employee Count: Easily retrieve the total number of employees for a company based on the most recent filing data.
Period of Report: Understand the timeframe of the reported employee count by accessing the period of the report.
Filing Date and Form Type: View the filing date and type of document (e.g., 10-K) to understand when and where the workforce data was disclosed.
Direct SEC Links: Access the official SEC source document for transparency and additional details.

This API is ideal for those analyzing company size, productivity, or workforce trends and provides a clear snapshot of company operations through its employee count.

Example Use Case
An equity analyst can use the Company Employee Count API to assess workforce growth at Apple Inc. over the years, comparing it to changes in the company’s revenue and profitability.

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
      ]
    ]
  }
}
```

## Related API slugs
`all-shares-float`, `market-cap`, `profile-cik`, `executive-compensation`, `historical-employee-count`
