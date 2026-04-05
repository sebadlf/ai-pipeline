# 5-Minute Interval Commodities Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/commodities-intraday-5-min](https://site.financialmodelingprep.com/developer/docs/stable/commodities-intraday-5-min)

Monitor short-term price movements with the FMP 5-Minute Interval Commodities Chart API. This API provides detailed 5-minute interval data, enabling users to track near-term price trends for more strategic trading and investment decisions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/5min?symbol=GCUSD`

## Description
The FMP 5-Minute Interval Commodities Chart API delivers price data at 5-minute intervals, offering a balance between granularity and broader trend analysis. It includes open, high, low, and close prices, as well as trading volume for commodities. This API is ideal for traders and investors who want to track short-term market activity but prefer a slightly broader view than 1-minute data can provide.


Short-Term Trend Analysis: Access 5-minute interval data to monitor price movements and identify short-term trends in commodity markets.
Detailed Pricing Information: Retrieve detailed price data for each 5-minute interval, including open, high, low, and close prices, along with volume.
Strategic Trading: Use the 5-minute interval data to spot patterns and price movements, helping traders refine their strategies and make more informed decisions.

This API is perfect for traders looking to balance real-time trading needs with a slightly longer-term perspective on commodity market movements.

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
`all-commodities-quotes`, `commodities-historical-price-eod-full`, `commodities-intraday-1-hour`, `commodities-intraday-1-min`, `commodities-quote-short`
