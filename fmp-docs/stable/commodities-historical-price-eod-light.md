# Light Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/commodities-historical-price-eod-light](https://site.financialmodelingprep.com/developer/docs/stable/commodities-historical-price-eod-light)

Access historical end-of-day prices for various commodities with the FMP Historical Commodities Price API. Analyze past price movements, trading volume, and trends to support informed decision-making.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/light?symbol=GCUSD`

## Description
The FMP Historical Commodities Price API offers users access to end-of-day pricing data for a wide range of commodities. This API is designed for investors, traders, and analysts who need to perform historical analysis on commodities markets, track price trends, and make informed predictions based on past data.


End-of-Day Pricing: Retrieve accurate historical prices for commodities, including key metrics like trading volume, to analyze market performance over time.
Comprehensive Historical Data: Access a detailed record of price changes for commodities over any chosen period.
Trading Volume Insights: Evaluate the trading activity for each commodity with volume data included alongside price information.

This API is ideal for financial professionals looking to analyze historical commodity data for research, risk management, or strategic trading purposes.

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
        "GCUSD"
      ],
      [
        "from",
        "date",
        "2025-09-09"
      ],
      [
        "to",
        "date",
        "2025-12-09"
      ]
    ]
  }
}
```

## Related API slugs
`commodities-quote`, `commodities-quote-short`, `commodities-intraday-1-hour`, `commodities-intraday-1-min`, `commodities-historical-price-eod-full`
