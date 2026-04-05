# Symbol Changes List

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/symbol-changes-list](https://site.financialmodelingprep.com/developer/docs/stable/symbol-changes-list)

Stay informed about the latest stock symbol changes with the FMP Stock Symbol Changes API. Track changes due to mergers, acquisitions, stock splits, and name changes to ensure accurate trading and analysis.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/symbol-change`

## Description
The FMP Stock Symbol Changes API provides comprehensive data on recent stock symbol changes. This API is essential for:


Accurate Trading: Symbol changes can occur for various reasons, including mergers, acquisitions, stock splits, and company name changes. Staying up-to-date with these changes ensures that your trading activities are accurate and error-free.
Portfolio Management: By tracking symbol changes, you can ensure that your investment portfolio reflects the correct and current stock symbols, helping you avoid any discrepancies in your holdings.
Efficient Stock Tracking: The API makes it easy to find the latest stock symbols, allowing you to quickly locate the stocks you need for trading, research, or analysis.

This API is a valuable tool for traders, investors, and analysts who need to keep track of symbol changes to maintain the accuracy of their financial activities.

Example: Trading Accuracy: A trader might use the Stock Symbol Changes API to update their trading platform with the latest stock symbols after a company undergoes a merger and changes its symbol. This ensures that their trades are executed correctly without any errors due to outdated information

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
        "invalid",
        "string",
        "false"
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
`actively-trading-list`, `cik-list`, `available-exchanges`, `available-sectors`, `financial-symbols-list`
