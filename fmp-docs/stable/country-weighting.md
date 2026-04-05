# ETF & Fund Country Allocation

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/country-weighting](https://site.financialmodelingprep.com/developer/docs/stable/country-weighting)

Gain insight into how ETFs and mutual funds distribute assets across different countries with the FMP ETF & Fund Country Allocation API. This tool provides detailed information on the percentage of assets allocated to various regions, helping you make informed investment decisions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/etf/country-weightings?symbol=SPY`

## Description
The FMP ETF & Fund Country Allocation API delivers a detailed breakdown of how ETFs and mutual funds allocate their assets by country. This data is essential for investors aiming to:


Assess Geographic Exposure: Understand how assets are distributed globally, offering insights into the geographic risk and opportunities associated with different funds.
Identify Country-Specific Investment Opportunities: Evaluate funds with significant exposure to countries that show strong economic growth potential, like the United States, China, or emerging markets.
Diversify Your Portfolio: Use country allocation data to balance your investments across international markets, reducing concentration risk in any single region.

For example, if you're looking to invest in a fund that heavily allocates its assets to the United States, you can use this API to find ETFs or mutual funds with a high percentage of their holdings in the U.S. Alternatively, if you want to diversify into international markets, this API will help you locate funds with significant exposure to foreign economies.

Example Use Case
An investor seeking to minimize risk by diversifying internationally might use the ETF & Fund Country Allocation API to identify funds with strong exposure to emerging markets or regions like Asia or Europe.

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
        "SPY"
      ]
    ]
  }
}
```

## Related API slugs
`holdings`, `mutual-fund-disclosures`, `information`, `sector-weighting`, `disclosures-dates`
