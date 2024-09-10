# Ethereum Deposit Tracker


## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Setup and Installation](#setup-and-installation)
4. [Usage](#usage)
5. [Features](#features)
6. [Code Structure](#code-structure)
7. [Error Handling](#error-handling)
8. [Logging](#logging)


## Overview

The Ethereum Deposit Tracker is a Python-based application that monitors and tracks deposits made to the Ethereum 2.0 Beacon Chain Deposit Contract. It processes new blocks, extracts deposit information, stores it in a MySQL database, and sends notifications via Telegram.


## Prerequisites

- Python 3.7+
- MySQL database
- Ethereum node access (via Alchemy or Infura)
- Telegram Bot Token
- Required Python packages: 
  - web3
  - python-dotenv
  - mysql-connector-python
  - eth-abi
  - python-telegram-bot


## Setup and Installation

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

4. Set up the MySQL database:
   The application will automatically create the necessary tables when run for the first time.


## Usage

Run the main script:
```
python main.py
```


## Features

1. **Real-time Ethereum Block Monitoring**: Continuously checks for new blocks on the Ethereum blockchain.

2. **Deposit Detection**: Identifies transactions made to the Beacon Chain Deposit Contract.

3. **Data Extraction**: Extracts relevant information from deposit transactions, including block number, timestamp, fee, transaction hash, and public key.

4. **Database Storage**: Stores deposit information in a MySQL database for persistence and querying.

5. **Telegram Bot Integration**: 
   - Sends notifications about new deposits to subscribed users.
   - Supports commands:
     - `/subscribe`: Subscribe to deposit notifications
     - `/unsubscribe`: Unsubscribe from deposit notifications
     - `/test_notification`: Send a test notification

6. **Blockchain Reorganization Handling**: Detects and handles blockchain reorganizations to maintain data accuracy.

7. **Error Handling and Logging**: Comprehensive error handling and logging for debugging and monitoring.


## Code Structure

- `DepositTracker` class: Main class handling the core functionality.
  - `create_tables()`: Sets up the necessary database tables.
  - `setup_telegram_bot()`: Initializes the Telegram bot and sets up command handlers.
  - `process_block()`: Processes a single Ethereum block for deposits.
  - `handle_reorg()`: Handles blockchain reorganizations.
  - `send_notification()`: Sends Telegram notifications for new deposits.
  - `run()`: Main loop for continuous block processing.


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

- Database connection errors are caught and logged.
- Transaction processing errors are caught and logged, allowing the system to continue processing other transactions.
- Blockchain reorganization handling helps maintain data integrity.
- The application uses Python's logging module to log information, warnings, and errors. Logs are formatted with timestamps and log levels, aiding in debugging and monitoring.

The application uses Python's logging module to log information, warnings, and errors. Logs are formatted with timestamps and log levels.
