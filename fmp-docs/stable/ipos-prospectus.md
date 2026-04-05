# IPOs Prospectus

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/ipos-prospectus](https://site.financialmodelingprep.com/developer/docs/stable/ipos-prospectus)

Access comprehensive information on IPO prospectuses with the FMP IPO Prospectus API. Get key financial details, such as public offering prices, discounts, commissions, proceeds before expenses, and more. This API also provides links to official SEC prospectuses, helping investors stay informed on companies entering the public market.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/ipos-prospectus`

## Description
The FMP IPO Prospectus API offers detailed insights into IPO filings, providing essential information to investors, analysts, and regulatory professionals. With this API, users can access:


Public Offering Prices: View the price per share and total amount raised through the IPO.
Discounts and Commissions: Understand the fees and commissions deducted from the gross proceeds of the IPO.
Proceeds Before Expenses: See the net proceeds the company expects to raise after expenses.
Filing and IPO Dates: Track when companies file their prospectuses and their scheduled IPO dates.
CIK and Form Type: Get key regulatory details, including the CIK number and the form type (e.g., 424B4).
Direct SEC Links: Access the full IPO prospectus filed with the SEC for complete details on the offering.

This API is an invaluable tool for anyone looking to analyze IPO financial details before making investment decisions.

Example Use Case
An investment advisor can use the IPO Prospectus API to review a company’s IPO financials and prospectus filings, helping them evaluate whether to recommend the IPO to clients based on the offering's structure.

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
`splits-company`, `dividends-company`, `dividends-calendar`, `earnings-company`, `ipos-calendar`
