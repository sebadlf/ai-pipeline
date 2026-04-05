# Commodities Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/commodities-quote](https://site.financialmodelingprep.com/developer/docs/stable/commodities-quote)

Access real-time price quotes for all commodities traded worldwide with the FMP Global Commodities Quotes API. Track market movements and identify investment opportunities with comprehensive price data.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote?symbol=GCUSD`

## Description
The FMP Global Commodities Quotes API provides a complete list of price quotes for all commodities traded on exchanges around the world. This API is an essential tool for investors and traders who want to:


Monitor Real-Time Prices: Access up-to-the-minute price quotes for all commodities, including current prices, highs, lows, and opening prices.
Track Market Movements: Follow the fluctuations in commodity prices over time to spot trends and make informed decisions.
Identify Investment Opportunities: Use detailed commodity price data to uncover potential investment opportunities in global markets.

This API provides a global view of commodity prices, enabling users to stay informed about market conditions and make data-driven investment decisions.

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
      ]
    ]
  }
}
```

## Related API slugs
`commodities-intraday-5-min`, `all-commodities-quotes`, `commodities-historical-price-eod-light`, `commodities-quote-short`, `commodities-intraday-1-hour`
