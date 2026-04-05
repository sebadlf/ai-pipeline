# Company Notes

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/company-notes](https://site.financialmodelingprep.com/developer/docs/stable/company-notes)

Retrieve detailed information about company-issued notes with the FMP Company Notes API. Access essential data such as CIK number, stock symbol, note title, and the exchange where the notes are listed.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/company-notes?symbol=AAPL`

## Description
The FMP Company Notes API provides crucial information on notes issued by publicly traded companies. This API is particularly valuable for investors, analysts, and financial professionals tracking corporate debt instruments. Key features include:


CIK and Stock Symbol Lookup: Identify notes by the company’s Central Index Key (CIK) and stock symbol.
Note Title and Terms: Get detailed titles of company-issued notes, including specific terms like interest rates and maturity dates.
Exchange Information: Learn where these notes are traded, helping you track their market activity on exchanges such as NASDAQ and NYSE.

The Company Notes API is an essential tool for monitoring corporate debt instruments and understanding a company’s financial commitments.

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
`delisted-companies`, `historical-employee-count`, `executive-compensation-benchmark`, `profile-cik`, `batch-market-cap`
