# Equity Offering By CIK

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/equity-offering-by-cik](https://site.financialmodelingprep.com/developer/docs/stable/equity-offering-by-cik)

Access detailed information on equity offerings announced by specific companies with the FMP Company Equity Offerings by CIK API. Track offering activity and identify potential investment opportunities.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/fundraising?cik=0001547416`

## Description
The FMP Company Equity Offerings by CIK API provides a comprehensive list of all equity offerings announced by a particular company, identified by its Central Index Key (CIK). This API is essential for:


Identifying Company-Specific Offerings: Quickly find and track equity offerings announced by companies you are interested in by searching with their CIK.
Tracking Offering Activity Over Time: Monitor the equity offering history of specific companies to gain insights into their financing activities and strategic moves.
Spotting Investment Opportunities: Use equity offering data to identify potential investment opportunities, understanding how a company’s offering activity might impact its stock price and market position.

Investors can leverage this API to stay informed about the equity offering activities of the companies they follow, allowing for more informed investment decisions.

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
        "cik*",
        "string",
        "0001547416"
      ]
    ]
  }
}
```

## Related API slugs
`latest-crowdfunding`, `equity-offering-search`, `crowdfunding-by-cik`, `crowdfunding-search`, `latest-equity-offering`
