# Global Exchange Market Hours

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/exchange-market-hours](https://site.financialmodelingprep.com/developer/docs/stable/exchange-market-hours)

Retrieve trading hours for specific stock exchanges using the Global Exchange Market Hours API. Find out the opening and closing times of global exchanges to plan your trading strategies effectively.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/exchange-market-hours?exchange=NASDAQ`

## Description
The FMP Global Exchange Market Hours API provides essential information about the opening and closing hours of various stock exchanges around the world. This API helps users track when exchanges like NASDAQ, NYSE, and others are open for trading, along with information about the time zone and whether the market is currently open. Key features include:


Trading Hours by Exchange: Access the opening and closing times for specific stock exchanges worldwide.
Real-Time Market Status: Find out if the market is currently open or closed for trading.
Time Zone Support: View exchange market hours in the local time zone of each exchange for accurate planning.
Global Exchange Coverage: Get information on major stock exchanges, including NASDAQ, NYSE, and others.

This API is ideal for traders, analysts, and investors who need to stay informed about market hours to manage their trading strategies across different regions.

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
        "exchange*",
        "string",
        "NASDAQ"
      ]
    ]
  }
}
```

## Related API slugs
`all-exchange-market-hours`
