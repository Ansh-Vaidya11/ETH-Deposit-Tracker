# Ethereum Deposit Tracker

## Overview

The Ethereum Deposit Tracker is a Python-based application that monitors and tracks deposits made to the Ethereum 2.0 Beacon Chain Deposit Contract. It processes new blocks, extracts deposit information, stores it in a MySQL database, and sends notifications via Telegram.

## Features

- Real-time tracking of Ethereum 2.0 deposits
- MySQL database storage for deposit information
- Telegram bot integration for notifications
- Handling of blockchain reorganizations
- Subscription management for Telegram notifications

## Prerequisites

- Python 3.7+
- MySQL database
- Ethereum node access (via Alchemy or Infura)
- Telegram Bot Token

## Installation

1. Clone the repository:
   ```
   git clone [repository_url]
   cd ethereum-deposit-tracker
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file in the project root and add the following:
   ```
   ETH_RPC_URL=your_ethereum_node_url
   DB_HOST=your_mysql_host
   DB_USER=your_mysql_username
   DB_PASSWORD=your_mysql_password
   DB_NAME=your_database_name
   DB_PORT=your_mysql_port
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

## Usage

Run the main script:
```
python main.py
```

## Telegram Bot Commands

- `/subscribe`: Subscribe to deposit notifications
- `/unsubscribe`: Unsubscribe from deposit notifications
- `/test_notification`: Send a test notification

## Database Schema

### Deposits Table
- `id`: Auto-incrementing primary key
- `blockNumber`: Block number of the deposit
- `blockTimestamp`: Timestamp of the block
- `fee`: Transaction fee
- `hash`: Transaction hash
- `pubkey`: Public key of the depositor
- `status`: 'valid' or 'invalid'
- `created_timestamp`: Timestamp of record creation
- `updated_timestamp`: Timestamp of last update

### Processed_Blocks Table
- `block_number`: Block number (primary key)
- `processed_timestamp`: Timestamp of processing

### Telegram_Subscriptions Table
- `chat_id`: Telegram chat ID (primary key)
- `subscribed_at`: Subscription timestamp

## Main Components

1. `DepositTracker`: Main class handling deposit tracking and processing
2. `setup_telegram_bot()`: Sets up the Telegram bot and command handlers
3. `process_block()`: Processes a single Ethereum block for deposits
4. `handle_reorg()`: Handles blockchain reorganizations
5. `send_notification()`: Sends Telegram notifications for new deposits

## Error Handling and Logging

The application uses Python's logging module to log information, warnings, and errors. Logs are formatted with timestamps and log levels.
