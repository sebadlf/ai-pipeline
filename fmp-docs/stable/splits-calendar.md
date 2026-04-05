# Stock Splits Calendar

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/splits-calendar](https://site.financialmodelingprep.com/developer/docs/stable/splits-calendar)

Stay informed about upcoming stock splits with the FMP Stock Splits Calendar API. This API provides essential data on upcoming stock splits across multiple companies, including the split date and ratio, helping you track changes in share structures before they occur.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/splits-calendar`

## Description
The FMP Stock Splits Calendar API offers timely information for investors and analysts who want to stay ahead of stock split events. This API provides:


Upcoming Split Dates: Know when future stock splits are scheduled, allowing you to plan your investments around these events.
Split Ratios: Access detailed split ratios, which show how many new shares (numerator) are issued for each old share (denominator).
Market Insight: Use this data to evaluate how upcoming splits might impact stock prices, liquidity, and shareholder value.

This API helps users monitor stock split announcements across the market, ensuring they have the information needed to make informed investment decisions.

Example Use Case
A portfolio manager can use the Stock Splits Calendar API to stay updated on upcoming stock splits, such as a 1-for-100 split scheduled for GBK.ST on February 29, 2024, to adjust their strategies accordingly.

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
`splits-company`, `earnings-calendar`, `ipos-calendar`, `ipos-disclosure`, `ipos-prospectus`
