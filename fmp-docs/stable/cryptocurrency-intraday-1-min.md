# 1-Minute Interval Cryptocurrency Data

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-intraday-1-min](https://site.financialmodelingprep.com/developer/docs/stable/cryptocurrency-intraday-1-min)

Get real-time, 1-minute interval price data for cryptocurrencies with the 1-Minute Cryptocurrency Intraday Data API. Monitor short-term price fluctuations and trading volume to stay updated on market movements.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1min?symbol=BTCUSD`

## Description
The 1-Minute Cryptocurrency Intraday Data API offers precise, real-time updates on cryptocurrency price movements, including:


1-Minute Price Intervals: Retrieve data on cryptocurrency prices at 1-minute intervals, including open, high, low, close (OHLC) values.
Real-Time Volume Information: Access detailed trading volume data for every minute, enabling quick insights into market activity.
Track Short-Term Price Movements: Analyze short-term trends in cryptocurrency prices to capitalize on market opportunities or identify trends early.

This API is vital for day traders, analysts, and algorithmic traders who need fast, actionable data to track the fast-moving cryptocurrency markets.

Example Use Case
A day trader can use the 1-Minute Cryptocurrency Intraday Data API to monitor real-time price movements and volume spikes, making quick decisions based on emerging market trends or breakouts.

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
`cryptocurrency-quote`, `cryptocurrency-quote-short`, `all-cryptocurrency-quotes`, `cryptocurrency-historical-price-eod-light`, `cryptocurrency-intraday-5-min`
