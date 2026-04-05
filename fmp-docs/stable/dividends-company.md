# Dividends Company

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/dividends-company](https://site.financialmodelingprep.com/developer/docs/stable/dividends-company)

Stay informed about upcoming dividend payments with the FMP Dividends Company API. This API provides essential dividend data for individual stock symbols, including record dates, payment dates, declaration dates, and more.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/dividends?symbol=AAPL`

## Description
The FMP Dividends Company API offers a comprehensive view of the dividend information for specific stocks. Designed for dividend-focused investors, this API delivers:


Dividend Schedule Overview: Get access to upcoming dividend details, including record date, payment date, and declaration date, to ensure timely information on dividend payouts.
Dividend Amount: View the dividend and adjusted dividend amounts to stay informed of expected payments.
Yield Data: Track the dividend yield for stocks to better assess the return on investment for dividend-focused portfolios.
Payment Frequency: Understand how often dividends are paid (e.g., quarterly, annually) to align your investment strategy with the stock’s payout schedule.

With detailed dividend information such as the amount, adjusted dividend, yield, and payment frequency, investors can effectively plan around dividend schedules. This API is perfect for dividend investors who need up-to-date information to make informed decisions about their income-generating investments.

Example Use Case
A dividend investor can use the Dividends Company API to monitor Apple’s upcoming dividend payment, ensuring they hold the stock through the record date to receive the payment.

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
`earnings-calendar`, `earnings-company`, `splits-company`, `ipos-disclosure`, `ipos-prospectus`
