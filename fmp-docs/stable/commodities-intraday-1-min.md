# 1-Minute Interval Commodities Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/commodities-intraday-1-min](https://site.financialmodelingprep.com/developer/docs/stable/commodities-intraday-1-min)

Track real-time, short-term price movements for commodities with the FMP 1-Minute Interval Commodities Chart API. This API provides detailed 1-minute interval data, enabling precise monitoring of intraday market changes.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1min?symbol=GCUSD`

## Description
The FMP 1-Minute Interval Commodities Chart API delivers minute-by-minute price data for commodities, including open, high, low, and close prices, as well as trading volume. This API is ideal for day traders, analysts, and market participants who require highly granular data to monitor real-time price fluctuations and respond to market trends with speed and accuracy.


Real-Time Intraday Data: Access up-to-the-minute price data for commodities, making it easier to track short-term price movements.
Detailed Price Information: View open, high, low, and close prices, along with trading volume, for precise analysis of market trends.
Fast Decision-Making: The 1-minute interval data supports fast decision-making for intraday trading, allowing users to act on market opportunities as they arise.

This API is a valuable resource for active traders and investors who need to stay on top of real-time price changes in the fast-moving commodities market.

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
        "2024-01-01"
      ],
      [
        "to",
        "date",
        "2024-03-01"
      ]
    ]
  }
}
```

## Related API slugs
`commodities-intraday-1-hour`, `commodities-historical-price-eod-light`, `commodities-quote`, `commodities-list`, `commodities-historical-price-eod-full`
