# Dividend Adjusted Price Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted)

Analyze stock performance with dividend adjustments using the FMP Dividend-Adjusted Price Chart API. Access end-of-day price and volume data that accounts for dividend payouts, offering a more comprehensive view of stock trends over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/dividend-adjusted?symbol=AAPL`

## Description
The FMP Dividend-Adjusted Price Chart API delivers EOD (end-of-day) price data that is adjusted for dividends, helping traders, analysts, and investors understand stock performance while factoring in dividend payments. This ensures a more accurate analysis of stock value changes, particularly for companies with regular dividend payouts. Features include:


Dividend-Adjusted Prices: Access historical stock prices—open, high, low, and close—that have been adjusted for dividend payouts, reflecting the true stock value.
Volume Data: Retrieve daily trading volume to assess market activity alongside price movements.
Accurate Performance Analysis: Use dividend-adjusted data to evaluate a stock’s performance over time with the impact of dividends factored in.
Enhanced Historical Insights: Ideal for long-term investors who want a clearer picture of stock growth and performance, while including the effect of dividends.

This API is a valuable tool for understanding total returns, making it easier to gauge a stock’s historical performance by incorporating dividend impacts.

Example Use Case
An investor tracking the historical growth of Apple stock can use the Dividend-Adjusted Price Chart API to account for the effect of dividend payouts when analyzing stock price changes over time.

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
`historical-price-eod-full`, `intraday-1-min`, `historical-price-eod-light`, `intraday-30-min`, `intraday-4-hour`
