# Crypto Price Tool

The Crypto Price tool provides real-time cryptocurrency price information using the CoinMarketCap API. This tool allows Jakey to provide accurate, current cryptocurrency prices to users.

## Purpose

The Crypto Price tool is designed to provide real-time cryptocurrency price information. This is particularly useful for:

- Checking current crypto prices
- Monitoring specific cryptocurrencies
- Getting price information in different currencies

## Usage

The AI can automatically choose to use the Crypto Price tool when users ask about cryptocurrency prices or when discussing crypto-related topics.

### Parameters

- `symbol` (string, required): The cryptocurrency symbol (e.g., BTC, ETH, SOL)
- `currency` (string, optional): The currency to convert to (default: USD)

### Example Tool Call

```json
{
  "name": "crypto_price",
  "arguments": {
    "symbol": "SOL",
    "currency": "USD"
  }
}
```

## Features

- **Real-time Prices**: Gets current market prices from CoinMarketCap
- **Multi-currency Support**: Can convert to various currencies
- **Rate Limiting**: Built-in rate limiting to prevent API abuse
- **Error Handling**: Graceful handling of network and API errors

## Response Format

The tool returns formatted price information including:
- Cryptocurrency symbol
- Current price
- Currency denomination

### Example Response

```
Current SOL price: $150.25 USD
```

## Supported Cryptocurrencies

The tool supports any cryptocurrency available on CoinMarketCap, including:
- Bitcoin (BTC)
- Ethereum (ETH)
- Solana (SOL)
- Ripple (XRP)
- And thousands more...

## Best Practices

1. Use standard cryptocurrency symbols
2. Specify currency when users request prices in non-USD currencies
3. Handle rate limiting gracefully by informing users when limits are exceeded