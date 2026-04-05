# Exponential Moving Average

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/exponential-moving-average](https://site.financialmodelingprep.com/developer/docs/stable/exponential-moving-average)



## Endpoint URLs
- `https://financialmodelingprep.com/stable/technical-indicators/ema?symbol=AAPL&periodLength=10&timeframe=1day`

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
      ],
      [
        "periodLength*",
        "number",
        "10"
      ],
      [
        "timeframe*",
        "string",
        [
          "1min",
          "5min",
          "15min",
          "30min",
          "1hour",
          "4hour",
          "1day"
        ]
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
