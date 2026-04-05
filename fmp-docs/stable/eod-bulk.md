# Eod Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/eod-bulk](https://site.financialmodelingprep.com/developer/docs/stable/eod-bulk)

The EOD Bulk API allows users to retrieve end-of-day stock price data for multiple symbols in bulk. This API is ideal for financial analysts, traders, and investors who need to assess valuations for a large number of companies.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/eod-bulk?date=2024-10-22`

## Description
The EOD Bulk API provides:


Historical Stock Prices: Access end-of-day stock prices for multiple symbols on a specific date.
Open, High, Low, Close Prices: Retrieve detailed price data, including opening, high, low, and closing prices for each symbol.
Volume and Adjusted Close: Get trading volume and adjusted closing prices to analyze stock performance and trading activity.
Historical Data Analysis: Use historical stock prices to conduct technical analysis, backtesting, and trend forecasting.

This API is designed for users who need to analyze stock prices across a wide range of companies, making it an efficient solution for bulk data retrieval.

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
        "date*",
        "string",
        "2024-10-22"
      ]
    ]
  }
}
```

## Related API slugs
`rating-bulk`, `ratios-ttm-bulk`, `cash-flow-statement-growth-bulk`, `scores-bulk`, `earnings-surprises-bulk`
