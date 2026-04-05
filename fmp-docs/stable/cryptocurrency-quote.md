# Full Cryptocurrency Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-quote](https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-quote)

Access real-time quotes for all cryptocurrencies with the FMP Full Cryptocurrency Quote API. Obtain comprehensive price data including current, high, low, and open prices.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote?symbol=BTCUSD`

## Description
The Full Cryptocurrency Quote API provides real-time quotes for all cryptocurrencies traded on exchanges worldwide. This endpoint offers detailed information such as:

Current Price: Get the latest price of any cryptocurrency.

High, Low, and Open Prices: Access the highest, lowest, and opening prices for the day.

Investors can use the Full Cryptocurrency Quote API to:


Monitor Real-Time Prices: Stay updated with real-time prices of all cryptocurrencies traded globally.
Track Price Movements: Follow the movement of cryptocurrency prices over time to identify trends and patterns.
Identify Investment Opportunities: Use comprehensive price data to spot potential investment opportunities.
Make Informed Trading Decisions: Base your trading decisions on up-to-date and accurate cryptocurrency price data.

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
        "BTCUSD"
      ]
    ]
  }
}
```

## Related API slugs
`cryptocurrency-intraday-1-min`, `cryptocurrency-historical-price-eod-full`, `cryptocurrency-intraday-5-min`, `cryptocurrency-list`, `cryptocurrency-intraday-1-hour`
