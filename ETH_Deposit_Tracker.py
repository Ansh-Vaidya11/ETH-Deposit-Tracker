import os
import time
import json
import logging
from web3 import Web3
from dotenv import load_dotenv
import mysql.connector
from eth_abi.abi import decode

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ethereum node RPC URL (replace with your Alchemy or Infura URL)
ETH_RPC_URL = os.getenv('ETH_RPC_URL')

# MySQL Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'port': os.getenv('DB_PORT', '3306')  # Default MySQL port is 3306
}

# Beacon Deposit Contract address
BEACON_DEPOSIT_CONTRACT = '0x00000000219ab540356cBB839Cbe05303d7705Fa'

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))

class DepositTracker:
    def __init__(self):
        try:
            self.db = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.db.cursor()
            self.create_tables()
            self.last_processed_block = self.get_last_processed_block()
        except mysql.connector.Error as err:
            logger.error(f"Error connecting to MySQL database: {err}")
            raise

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Deposits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                blockNumber INT,
                blockTimestamp INT,
                fee VARCHAR(255),
                hash VARCHAR(66),
                pubkey VARCHAR(132),
                status ENUM('valid', 'invalid') DEFAULT 'valid',
                created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX (hash),
                INDEX (blockNumber)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Processed_Blocks (
                block_number INT PRIMARY KEY,
                processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db.commit()

    def get_last_processed_block(self):
        self.cursor.execute('SELECT MAX(block_number) FROM Processed_Blocks')
        result = self.cursor.fetchone()
        if result[0]:
            return result[0]
        else:
            # If no blocks have been processed, start from 100 blocks ago
            latest_block = w3.eth.get_block('latest')['number']
            return latest_block - 100

    def save_processed_block(self, block_number):
        self.cursor.execute('''
            INSERT INTO Processed_Blocks (block_number) 
            VALUES (%s) 
            ON DUPLICATE KEY UPDATE processed_timestamp = CURRENT_TIMESTAMP
        ''', (block_number,))
        self.db.commit()

    def save_deposit(self, deposit):
        self.cursor.execute('''
            INSERT INTO deposits (blockNumber, blockTimestamp, fee, hash, pubkey)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                blockNumber = %s, 
                blockTimestamp = %s, 
                fee = %s, 
                pubkey = %s
        ''', (
            deposit['blockNumber'], deposit['blockTimestamp'], deposit['fee'], deposit['hash'], deposit['pubkey'],
            deposit['blockNumber'], deposit['blockTimestamp'], deposit['fee'], deposit['pubkey']
        ))
        self.db.commit()
        logger.info(f"Saved Deposit: {deposit['hash']}")

    def invalidate_deposit(self, tx_hash):
        self.cursor.execute('''
            UPDATE Deposits 
            SET status = 'invalid' 
            WHERE hash = %s
        ''', (tx_hash,))
        self.db.commit()
        logger.info(f"Invalidated Deposit: {tx_hash}")

    def extract_pubkey(self, input_data):
        try:
            decoded = decode(['bytes', 'bytes', 'bytes', 'bytes32'], bytes.fromhex(input_data[2:]))
            return '0x' + decoded[0].hex()
        except Exception as e:
            logger.error(f"Error decoding pubkey: {e}")
            return None

    def process_block(self, block_number):
        try:
            block = w3.eth.get_block(block_number, full_transactions=True)
            
            for tx in block['transactions']:
                try:
                    if tx['to'] is not None and tx['to'].lower() == BEACON_DEPOSIT_CONTRACT.lower():
                        deposit = {
                            'blockNumber': block_number,
                            'blockTimestamp': block['timestamp'],
                            'fee': str(tx['gas'] * tx['gasPrice']),
                            'hash': tx['hash'].hex(),
                            'pubkey': self.extract_pubkey(tx['input'])
                        }
                        self.save_deposit(deposit)
                except Exception as e:
                    logger.error(f"Error processing transaction {tx.get('hash', 'Unknown')}: {e}")
            
            self.save_processed_block(block_number)
            logger.info(f"Processed and Saved Block {block_number}")
        except Exception as e:
            logger.error(f"Error processing block {block_number}: {e}")

    def handle_reorg(self, new_block_number):
        check_depth = 10
        start_block = max(new_block_number - check_depth, self.last_processed_block)
        
        for block_number in range(start_block, new_block_number + 1):
            try:
                block = w3.eth.get_block(block_number)
                self.cursor.execute('SELECT hash FROM Deposits WHERE blockNumber = %s', (block_number,))
                deposits = self.cursor.fetchall()
                
                for deposit in deposits:
                    tx_hash = deposit[0]
                    try:
                        tx = w3.eth.get_transaction(tx_hash)
                        if tx['blockNumber'] != block_number:
                            logger.warning(f"Reorg detected for transaction {tx_hash}")
                            self.invalidate_deposit(tx_hash)
                    except Exception:
                        logger.warning(f"Transaction {tx_hash} not found, likely due to reorg")
                        self.invalidate_deposit(tx_hash)
                
                self.db.commit()
                self.process_block(block_number)
            except Exception as e:
                logger.error(f"Error handling reorg for block {block_number}: {e}")

    def run(self):
        while True:
            try:
                current_block = w3.eth.get_block('latest')['number']
                
                if current_block > self.last_processed_block:
                    self.handle_reorg(current_block)
                
                while self.last_processed_block < current_block:
                    self.last_processed_block += 1
                    self.process_block(self.last_processed_block)
                
                time.sleep(15)  # Wait for 15 seconds before checking for new blocks
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait for 1 minute before retrying in case of a major error

if __name__ == "__main__":
    try:
        tracker = DepositTracker()
        tracker.run()
    except Exception as e:
        logger.error(f"Failed to initialize or run DepositTracker: {e}")