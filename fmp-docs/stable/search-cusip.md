# CUSIP

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-cusip](https://site.financialmodelingprep.com/developer/docs/stable/search-cusip)

Easily search and retrieve financial securities information by CUSIP number using the FMP CUSIP API. Find key details such as company name, stock symbol, and market capitalization associated with the CUSIP.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/search-cusip?cusip=037833100`

## Description
The FMP CUSIP API allows users to quickly retrieve comprehensive financial information linked to a specific CUSIP number (Committee on Uniform Securities Identification Procedures). This nine-character alphanumeric code uniquely identifies financial securities, making it an essential tool for investors, traders, and analysts.

Key features of the CUSIP API include:


Accurate Identification: Find stock symbols and company names associated with specific CUSIP numbers, ensuring precise identification of securities.
Comprehensive Data: Retrieve relevant financial details, including market capitalization, alongside CUSIP and stock symbol information.
Versatility: The API supports various types of securities, including stocks, bonds, and mutual funds, offering a broad range of search capabilities across multiple financial markets.

This API is a valuable resource for financial professionals who need to identify and analyze securities efficiently by their CUSIP.

Example: A trader can use the CUSIP API to instantly locate the CUSIP number and market capitalization for Apple Inc. by simply searching for the stock symbol “AAPL,” streamlining the research process before executing a trade.

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
        "cusip*",
        "string",
        "037833100"
      ]
    ]
  }
}
```

## Related API slugs
`search-ISIN`, `search-name`, `search-symbol`, `search-exchange-variants`, `search-CIK`
