# Dividends Calendar

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/dividends-calendar](https://site.financialmodelingprep.com/developer/docs/stable/dividends-calendar)

Stay informed on upcoming dividend events with the Dividend Events Calendar API. Access a comprehensive schedule of dividend-related dates for all stocks, including record dates, payment dates, declaration dates, and dividend yields.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/dividends-calendar`

## Description
The Dividend Events Calendar API provides a market-wide view of upcoming dividend events. Ideal for investors, financial analysts, and portfolio managers, this API enables:


Comprehensive Dividend Calendar: View upcoming record, payment, and declaration dates for dividends across various stocks.
Dividend Yield Tracking: Analyze the dividend yield to assess potential returns for each stock.
Payment Frequency Details: Identify whether dividends are paid quarterly, annually, or at other intervals to plan future investments.
Efficient Market Monitoring: Keep track of dividend events across the entire market to spot opportunities and trends.

This API makes it easy for investors to stay ahead of dividend events and optimize their income strategies.

Example Use Case
A portfolio manager can use the Dividend Events Calendar API to keep track of upcoming dividend payments for all stocks in their portfolio, ensuring they don't miss important dividend events or payouts.

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
`ipos-disclosure`, `splits-calendar`, `dividends-company`, `earnings-calendar`, `splits-company`
