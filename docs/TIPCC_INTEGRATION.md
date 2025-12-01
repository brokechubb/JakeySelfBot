# tip.cc Integration for Jakey Bot

## Overview

This document describes the comprehensive tip.cc integration implemented for Jakey bot, providing cryptocurrency tipping functionality with enhanced tracking and analysis capabilities.

## Enhanced Features

### 1. System Prompt Integration

Enhanced system prompt includes comprehensive tip.cc documentation with:

- Command syntax and usage patterns
- Tipping mechanics and options
- Special targeting options (roles, voice channels)
- Transaction parsing and balance tracking

### 2. Balance and Transaction Tracking

Enhanced database integration for comprehensive tracking:

#### Balance Monitoring

- **Real-time balance updates**: Automatic tracking of all cryptocurrency balances
- **USD value conversion**: Real-time conversion to USD values
- **Multi-currency support**: All supported tip.cc cryptocurrencies
- **Balance history**: Historical tracking of balance changes

#### Transaction Logging

- **Detailed transaction history**: Complete record of all tips, airdrops, deposits, withdrawals
- **Timestamp tracking**: Accurate timing of all transactions
- **Value tracking**: USD equivalent values for all transactions
- **Category classification**: Automatic categorization of transaction types

### 3. Command Integration

#### `%bal` / `%bals`

- **Function**: Check current tip.cc balances
- **Features**:
    - Real-time balance display
    - USD value conversion
    - Interactive button for detailed breakdown
    - Multi-currency support

#### `%transactions [limit]`

- **Function**: Show recent transaction history
- **Parameters**: Optional limit (default: 10)
- **Features**:
    - Detailed transaction records
    - Timestamp and value tracking
    - USD equivalent values
    - Category classification

#### `%tipstats`

- **Function**: Show comprehensive tip statistics
- **Features**:
    - Tips sent and received tracking
    - Airdrop winnings analysis
    - Net profit/loss calculation
    - Transaction volume statistics

### 4. Admin Commands

#### `%tip <recipient> <amount> <currency> [message]` (Admin Only)

- **Function**: Send tips to users
- **Parameters**:
    - `recipient`: User mention or ID
    - `amount`: Tip amount (supports $, numbers, decimals)
    - `currency`: Currency code (DOGE, USD, BTC, etc.)
    - `message`: Optional tip message
- **Features**: Proper command formatting and validation

#### `%airdrop <amount> <currency> <duration>` (Admin Only)

- **Function**: Create airdrops
- **Parameters**:
    - `amount`: Airdrop amount
    - `currency`: Currency code
    - `duration`: Duration (1m, 5m, 10m, etc.)
- **Features**: Automatic formatting and validation

## Command Examples

### Balance Checking

```
%bal          # Check all balances
%bals         # Alias for balance check
```

### Transaction History

```
%transactions        # Show last 10 transactions
%transactions 25     # Show last 25 transactions
```

### Statistics

```
%tipstats    # Show comprehensive tip statistics
```

### Admin Commands

```
%tip @user 100 DOGE                 # Tip 100 DOGE to user
%tip @user 5 USD Thanks for help    # Tip 5 USD with message
%airdrop 1000 DOGE 5m               # Create 1000 DOGE airdrop for 5 minutes
```

## Database Integration

### Tip Transaction Tracking

The bot maintains a comprehensive `tipcc_transactions` table with:

- **Transaction ID**: Unique identifier
- **Type**: tip, airdrop, deposit, withdrawal
- **Amount**: Transaction amount
- **Currency**: Cryptocurrency code
- **USD Value**: USD equivalent value
- **Timestamp**: Transaction time
- **Sender/Recipient**: User references
- **Description**: Transaction details

## Usage in Jakey

Jakey now provides:

1. **Real-time balance monitoring**: Current balances updated automatically
2. **Historical tracking**: Complete transaction history
3. **Statistical analysis**: Profit/loss calculations and trend analysis
4. **Multi-currency support**: All tip.cc supported currencies
5. **USD conversion**: Real-time USD value tracking

## Limitations

- Balance and transaction tracking requires active monitoring of tip.cc bot messages
- Some transaction types may not be automatically parsed
- Admin commands require proper authorization

## Future Enhancements

- Direct API integration (if tip.cc provides public API)
- Real-time notifications for balance changes
- Advanced analytics and trend analysis
- Export capabilities for transaction history

## Error Handling

- Graceful handling of API failures
- Fallback mechanisms for parsing issues
- User-friendly error messages
- Automatic retry logic for failed operations
  `
