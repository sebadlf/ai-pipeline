# U.S. House Trades

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/house-trading](https://site.financialmodelingprep.com/developer/docs/stable/house-trading)

Track the financial trades made by U.S. House members and their families with the FMP U.S. House Trades API. Access real-time information on stock sales, purchases, and other investment activities to gain insight into their financial decisions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/house-trades?symbol=AAPL`

## Description
The FMP U.S. House Trades API provides a comprehensive view of the trading activities of U.S. House members and their spouses. This API offers detailed data on trades, including stock sales and purchases, ownership details, and transaction amounts. Users can:


Monitor Trading Activity: Stay informed about the latest stock trades made by U.S. House members and their families.
Understand Financial Moves: Gain insights into the financial decisions of government officials through detailed trade data.
Transparency and Accountability: Use the data to follow the financial actions of U.S. House members, ensuring greater transparency in government.

This API is ideal for political analysts, journalists, and the general public interested in understanding the financial moves of U.S. House representatives.

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
`senate-latest`, `house-latest`, `senate-trading`
