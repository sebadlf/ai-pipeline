# Price Target Summary

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/price-target-summary](https://site.financialmodelingprep.com/developer/docs/stable/price-target-summary)

Gain insights into analysts' expectations for stock prices with the FMP Price Target Summary API. This API provides access to average price targets from analysts across various timeframes, helping investors assess future stock performance based on expert opinions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/price-target-summary?symbol=AAPL`

## Description
The FMP Price Target Summary API allows users to track and analyze analysts' price targets for individual stocks, making it a valuable tool for investors and analysts looking to understand market sentiment. Key features include:


Average Price Targets: Access average price targets from analysts over different periods (last month, last quarter, last year, and all time).
Price Target History: Track how price expectations have evolved over time to gauge changes in analysts' outlooks.
Analyst Coverage: Retrieve the number of analysts providing price targets during specific periods.
Multiple Publishers: View a list of sources and publishers providing price target data, such as Benzinga, MarketWatch, and Barrons.

This API allows you to quickly assess the consensus among financial analysts regarding a stock’s future price movement.

Example Use Case
An investor can use the Price Target Summary API to compare the average price targets for a stock over the past quarter and year to determine if analysts' outlooks have become more bullish or bearish over time.

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
`grades-summary`, `historical-grades`, `grades`, `financial-estimates`, `historical-ratings`
