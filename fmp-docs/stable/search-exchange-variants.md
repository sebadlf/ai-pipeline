# Exchange Variants

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-exchange-variants](https://site.financialmodelingprep.com/developer/docs/stable/search-exchange-variants)

Search across multiple public exchanges to find where a given stock symbol is listed using the FMP Exchange Variants API. This allows users to quickly identify all the exchanges where a security is actively traded.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/search-exchange-variants?symbol=AAPL`

## Description
The FMP Exchange Variants API is a powerful tool that provides essential data on where a particular stock is listed across different global exchanges. This API is critical for:


Multi-Exchange Search: Easily find all public exchanges where a specific stock is listed, ensuring you have a complete understanding of a company's trading activity worldwide.
Detailed Stock Information: The API returns not only the exchanges where a stock is listed but also includes key financial data such as price, market cap, volume, and beta, allowing for a thorough analysis of the stock.
Broad Market Coverage: With support for major international exchanges, users can access data from global markets, making it easier to track securities listed in different regions.

This API is a valuable resource for investors, traders, and analysts who need a global view of where securities are traded.

Example: A trader looking for Apple Inc. (AAPL) can use the Exchange Variants API to retrieve a list of exchanges where Apple’s stock is traded, along with crucial financial data like market cap, price range, and average trading volume.

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
`search-CIK`, `search-cusip`, `search-symbol`, `search-company-screener`, `search-ISIN`
