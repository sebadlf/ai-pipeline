# Company Profile Data

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol](https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol)

Access detailed company profile data with the FMP Company Profile Data API. This API provides key financial and operational information for a specific stock symbol, including the company's market capitalization, stock price, industry, and much more.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/profile?symbol=AAPL`

## Description
The FMP Company Profile Data API offers comprehensive insights into a company's financial status and operational details. This API is ideal for analysts, traders, and investors who need an in-depth look at a company’s core financial metrics and business information. Key features include:


Stock Price and Market Cap: Get the latest stock price and market capitalization for the requested symbol.
Company Details: Access information like company name, description, CEO, and industry classification
Financial Metrics: Track important financial metrics like dividend yield, stock beta, and trading range to assess performance and volatility.
Global Identifiers: Retrieve global financial identifiers such as CIK, ISIN, and CUSIP to ensure accurate tracking across platforms.
Contact Information: Obtain contact details like the company’s address, phone number, and website for direct reference.
IPO Data: Learn about the company's IPO date, sector, and whether it’s actively trading.

Example Use Case
An investor researching potential tech investments can use the Company Profile Data API to review the current financial health of Apple Inc., assess its performance, and explore key metrics like its stock range and market cap to inform buying or selling decisions.

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
`employee-count`, `all-shares-float`, `market-cap`, `executive-compensation-benchmark`, `company-executives`
