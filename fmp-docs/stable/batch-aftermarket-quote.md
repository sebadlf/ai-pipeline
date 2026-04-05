# Batch Aftermarket Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/batch-aftermarket-quote](https://site.financialmodelingprep.com/developer/docs/stable/batch-aftermarket-quote)

Retrieve real-time aftermarket quotes for multiple stocks with the FMP Batch Aftermarket Quote API. Access bid and ask prices, volume, and other relevant data for several companies during post-market trading.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-aftermarket-quote?symbols=AAPL`

## Description
The FMP Batch Aftermarket Quote API allows you to efficiently track aftermarket trading activity for multiple stocks at once. This API is ideal for:


Monitoring Multiple Stocks: Get bid and ask prices, volume, and other key aftermarket data for several stocks simultaneously, providing a comprehensive view of post-market movements.
Post-Market Strategy: Use batch data to analyze stock performance and develop strategies based on aftermarket trends that can affect the next trading session.
Streamlined Data Access: Track the aftermarket trading environment across your portfolio or watchlist in one single request.

The Batch Aftermarket Quote API helps investors make quicker, more informed decisions by providing real-time data on several stocks after normal market hours.

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
        "symbols*",
        "string",
        "AAPL"
      ]
    ]
  }
}
```

## Related API slugs
`batch-quote`, `quote`, `full-forex-quotes`, `quote-short`, `aftermarket-trade`
