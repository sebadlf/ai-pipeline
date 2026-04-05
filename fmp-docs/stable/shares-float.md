# Company Share Float & Liquidity

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/shares-float](https://site.financialmodelingprep.com/developer/docs/stable/shares-float)

Understand the liquidity and volatility of a stock with the FMP Company Share Float and Liquidity API. Access the total number of publicly traded shares for any company to make informed investment decisions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/shares-float?symbol=AAPL`

## Description
The FMP Company Share Float and Liquidity API provides essential data on the number of publicly traded shares for a given company, also known as the company’s float. This endpoint helps investors:


Evaluate Stock Liquidity: Identify the number of shares available for trading, which directly impacts the liquidity of the stock.
Assess Volatility: Understand how the size of a company’s float can influence stock price volatility, with smaller floats generally leading to higher volatility.
Make Informed Decisions: Use float data to identify companies with large or small floats, helping to assess the potential risk and reward of investing in those companies.

For example, companies with a large float tend to have more liquid stocks and less price volatility, while companies with a small float may experience higher price fluctuations due to lower liquidity.

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
      ]
    ]
  }
}
```

## Related API slugs
`market-cap`, `company-notes`, `all-shares-float`, `historical-market-cap`, `executive-compensation`
