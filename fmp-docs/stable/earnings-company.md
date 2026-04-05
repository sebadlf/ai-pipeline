# Earnings Report

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/earnings-company](https://site.financialmodelingprep.com/developer/docs/stable/earnings-company)

Retrieve in-depth earnings information with the FMP Earnings Report API. Gain access to key financial data for a specific stock symbol, including earnings report dates, EPS estimates, and revenue projections to help you stay on top of company performance.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/earnings?symbol=AAPL`

## Description
The Earnings Report API provides detailed insights into the earnings announcements of publicly traded companies. It’s designed for investors and analysts who need to monitor earnings reports closely to make informed trading and investment decisions, including:


Earnings Report Timing: Track earnings announcements for specific companies, including whether reports are released after market close (amc) or before market open (bmo).
EPS and Revenue Estimates: Access estimated earnings per share (EPS) and revenue data ahead of earnings announcements to understand market expectations.
Performance Tracking: See how actual earnings compare to estimates once they are released, helping identify trends in company performance.
Market Reaction Insights: Use earnings data to predict potential stock price movements based on whether a company beats or misses earnings expectations.

This API is ideal for those looking to stay updated on company earnings and monitor how these reports may impact stock prices.

Example Use Case
A financial analyst can use the Earnings Report API to track Apple's upcoming earnings report, reviewing EPS and revenue estimates to predict how the stock might react after the earnings are announced.

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
        "limit",
        "number",
        "100"
      ]
    ]
  }
}
```

## Related API slugs
`ipos-disclosure`, `splits-company`, `splits-calendar`, `dividends-calendar`, `ipos-calendar`
