# Financial Tools

Jakey includes several financial tools for retrieving price information and performing calculations.

## Stock Price Tool

The Stock Price tool provides real-time stock market price information using the yfinance library.

### Purpose

- Retrieve current stock prices
- Monitor specific stocks
- Provide investment-related information

### Parameters

- `symbol` (string, required): The stock symbol (e.g., AAPL, GOOGL, TSLA)

### Example Tool Call

```json
{
  "name": "stock_price",
  "arguments": {
    "symbol": "AAPL"
  }
}
```

### Example Response

```
Current AAPL price: $175.50
```

## Calculate Tool

The Calculate tool performs mathematical calculations.

### Purpose

- Perform basic mathematical operations
- Calculate gambling odds
- Handle financial calculations

### Parameters

- `expression` (string, required): The mathematical expression to evaluate

### Example Tool Call

```json
{
  "name": "calculate",
  "arguments": {
    "expression": "100 * 2.5"
  }
}
```

### Example Response

```
Result: 250.0
```

## Bonus Schedule Tool

The Bonus Schedule tool provides information about gambling site bonus schedules.

### Purpose

- Provide bonus timing information
- Answer user questions about bonuses
- Keep users informed about upcoming bonuses

### Parameters

- `site` (string, required): The gambling site. Options: "stake", "shuffle"
- `frequency` (string, required): The bonus frequency. Options: "weekly", "monthly"

### Example Tool Call

```json
{
  "name": "get_bonus_schedule",
  "arguments": {
    "site": "stake",
    "frequency": "weekly"
  }
}
```

### Example Response

```
Stake weekly bonus: Saturday 12:30 GMT
```

## Features

- **Real-time Data**: Stock and crypto prices are retrieved in real-time
- **Mathematical Operations**: Supports basic arithmetic operations
- **Scheduled Information**: Accurate bonus schedule information
- **Rate Limiting**: All tools include rate limiting to prevent abuse

## Best Practices

1. Use appropriate tools for the type of financial information needed
2. Handle calculation errors gracefully
3. Provide clear, formatted responses
4. Respect rate limits and inform users when limits are exceeded