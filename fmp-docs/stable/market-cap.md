# Company Market Cap

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/market-cap](https://site.financialmodelingprep.com/developer/docs/stable/market-cap)

Retrieve the market capitalization for a specific company on any given date using the FMP Company Market Capitalization API. This API provides essential data to assess the size and value of a company in the stock market, helping users gauge its overall market standing.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/market-capitalization?symbol=AAPL`

## Description
The FMP Company Market Capitalization API delivers precise data on a company's market cap for a selected date, making it an indispensable tool for investors, analysts, and financial professionals. Key features include:


Market Capitalization on Specific Dates: Retrieve accurate market cap data for companies, allowing you to track changes over time.
Company Valuation Analysis: Analyze a company's size and value within the stock market based on its market capitalization.
Historical and Real-Time Capabilities: Access both historical and real-time market cap data for better decision-making.

This API is ideal for investors, portfolio managers, and analysts who need a quick way to assess company size and evaluate its standing within the market.

Example Use Case
An investor tracking Apple Inc.'s market performance can use the Company Market Capitalization API to retrieve the company's market cap on specific dates, helping them understand Apple's valuation trends and compare it with competitors.

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
`company-notes`, `historical-employee-count`, `shares-float`, `executive-compensation`, `profile-symbol`
