# Company Executives

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/company-executives](https://site.financialmodelingprep.com/developer/docs/stable/company-executives)

Retrieve detailed information on company executives with the FMP Company Executives API. This API provides essential data about key executives, including their name, title, compensation, and other demographic details such as gender and year of birth.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/key-executives?symbol=AAPL`

## Description
The FMP Company Executives API offers a comprehensive view of a company's leadership team, ideal for investors, researchers, and analysts who need to assess the structure and leadership of a company. This API is useful for:


Executive Profiles: Access details like executive names, their roles within the company, and compensation data.
Demographic Data: Get additional demographic insights, including gender and year of birth.
Compensation Analysis: Analyze executive pay, which can be a key indicator of company priorities and leadership value.

This API delivers a clear overview of company leadership, helping users understand who is in charge and how well they are compensated for their role.

Example Use Case
An investor looking to assess the leadership of a company before making a large investment can use the Company Executives API to review the backgrounds and compensation of top executives, providing insight into how leadership may impact company performance.

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
`historical-employee-count`, `executive-compensation`, `profile-symbol`, `peers`, `delisted-companies`
