# Senate Trading Activity

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/senate-trading](https://site.financialmodelingprep.com/developer/docs/stable/senate-trading)

Monitor the trading activity of US Senators with the FMP Senate Trading Activity API. Access detailed information on trades made by Senators, including trade dates, assets, amounts, and potential conflicts of interest.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/senate-trades?symbol=AAPL`

## Description
The FMP Senate Trading Activity API provides comprehensive data on the trading activities of US Senators, as required by the STOCK Act of 2012. This API is essential for:


Transparency & Accountability: Access a detailed list of trades made by US Senators, including the date, asset, amount traded, and price per share. This transparency helps ensure accountability and provides insights into the financial activities of elected officials.
Conflict of Interest Identification: Use the data to identify potential conflicts of interest by analyzing trades made by Senators in companies or sectors where they may have legislative influence. This information is crucial for investors who want to ensure ethical investment practices.
Informed Investment Decisions: Investors can track the trading activities of Senators to gain insights into market trends or to flag any trades that might indicate a significant market move. Knowing when and what Senators are trading can provide a unique perspective on market sentiment.

This API is a powerful tool for investors, analysts, and anyone interested in monitoring the financial activities of US Senators and ensuring transparency in government.

Example Use Case
Ethical Investing: An investor focused on ethical investing might use the Senate Trading Activity API to avoid investing in companies where Senators have made trades, especially if those trades could be seen as conflicts of interest. By doing so, the investor aligns their portfolio with ethical standards.

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
`senate-latest`, `house-latest`, `house-trading`
