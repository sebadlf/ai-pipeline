# SEC Filings Company Search By Symbol

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/company-search-by-symbol](https://site.financialmodelingprep.com/developer/docs/stable/company-search-by-symbol)

Find company information and regulatory filings using a stock symbol with the FMP SEC Filings Company Search By Symbol API. Quickly access essential company details based on stock ticker symbols.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/sec-filings-company-search/symbol?symbol=AAPL`

## Description
The FMP SEC Filings Company Search By Symbol API allows users to search for a company's SEC filings by simply entering its stock symbol. This API provides valuable information such as:


Stock Symbol-Based Search: Enter a company’s ticker symbol to find official SEC filings and corporate details.
Detailed Company Information: Retrieve the company’s name, CIK number, industry classification (SIC code), and business address.
Filing Access: Access crucial SEC filings, enabling comprehensive regulatory research and corporate event tracking.

This API is perfect for investors, financial analysts, and compliance professionals who need to quickly pull company-specific SEC filings and information using a stock symbol.

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
`sec-company-full-profile`, `financials-latest`, `company-search-by-cik`, `all-industry-classification`, `search-by-form-type`
