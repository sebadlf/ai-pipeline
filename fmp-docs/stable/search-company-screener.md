# Stock Screener

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-company-screener](https://site.financialmodelingprep.com/developer/docs/stable/search-company-screener)

Discover stocks that align with your investment strategy using the FMP Stock Screener API. Filter stocks based on market cap, price, volume, beta, sector, country, and more to identify the best opportunities.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/company-screener`

## Description
The FMP Company Stock Screener API is a versatile tool designed to help investors find stocks that meet their specific investment criteria. This API is essential for:


Customizable Stock Searches: Screen stocks based on a wide range of criteria, including market cap, price, trading volume, beta, sector, and country. Tailor your searches to match your investment goals.
Financial Criteria Filters: Go beyond basic metrics by screening stocks based on financial performance indicators such as profitability, growth, and valuation metrics, ensuring you find stocks that fit your financial strategy.
Investment Opportunities: Use the Stock Screener API to build watchlists, identify new investment opportunities, and perform in-depth portfolio analysis.

Whether you’re a beginner or an experienced investor, this API is a valuable resource for discovering stocks that align with your investment approach.

Example
Building a Watchlist: An investor interested in technology stocks with a market cap of over $10 billion can use the Stock Screener API to filter and create a watchlist of potential investment opportunities. The investor can further refine the list based on other criteria such as beta and trading volume.

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
        "marketCapMoreThan",
        "number",
        "1000000"
      ],
      [
        "marketCapLowerThan",
        "number",
        "1000000000"
      ],
      [
        "sector",
        "string",
        "Technology"
      ],
      [
        "industry",
        "string",
        "Consumer Electronics"
      ],
      [
        "betaMoreThan",
        "number",
        "0.5"
      ],
      [
        "betaLowerThan",
        "number",
        "1.5"
      ],
      [
        "priceMoreThan",
        "number",
        "10"
      ],
      [
        "priceLowerThan",
        "number",
        "200"
      ],
      [
        "dividendMoreThan",
        "number",
        "0.5"
      ],
      [
        "dividendLowerThan",
        "number",
        "2"
      ],
      [
        "volumeMoreThan",
        "number",
        "1000"
      ],
      [
        "volumeLowerThan",
        "number",
        "1000000"
      ],
      [
        "exchange",
        "string",
        "NASDAQ"
      ],
      [
        "country",
        "string",
        "US"
      ],
      [
        "isEtf",
        "boolean",
        "false"
      ],
      [
        "isFund",
        "boolean",
        "false"
      ],
      [
        "isActivelyTrading",
        "boolean",
        "true"
      ],
      [
        "limit",
        "number",
        "1000"
      ],
      [
        "includeAllShareClasses",
        "boolean",
        "false"
      ]
    ]
  }
}
```

## Related API slugs
`search-name`, `search-ISIN`, `search-cusip`, `search-symbol`, `search-exchange-variants`
