import os
import asyncio
import logging
from web3 import Web3
from dotenv import load_dotenv
import mysql.connector
from eth_abi.abi import decode
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))

class DepositTracker:
    def __init__(self):
        try:
            self.db = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.db.cursor()
            self.create_tables()
            self.last_processed_block = self.get_last_processed_block()
            self.application = None
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
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Telegram_Subscriptions (
                chat_id BIGINT PRIMARY KEY,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db.commit()

    async def setup_telegram_bot(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.application.add_handler(CommandHandler("subscribe", self.subscribe))
        self.application.add_handler(CommandHandler("unsubscribe", self.unsubscribe))
        self.application.add_handler(CommandHandler("test_notification", self.test_notification))
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Telegram bot setup completed")

    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        try:
            self.cursor.execute('''
                INSERT INTO Telegram_Subscriptions (chat_id)
                VALUES (%s)
                ON DUPLICATE KEY UPDATE subscribed_at = CURRENT_TIMESTAMP
            ''', (chat_id,))
            self.db.commit()
            await update.message.reply_text("You have successfully subscribed to deposit notifications!")
            logger.info(f"User {chat_id} subscribed to notifications")
        except Exception as e:
            logger.error(f"Error subscribing user: {e}")
            await update.message.reply_text("An error occurred while subscribing. Please try again later.")

    async def unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        try:
            self.cursor.execute('DELETE FROM Telegram_Subscriptions WHERE chat_id = %s', (chat_id,))
            self.db.commit()
            await update.message.reply_text("You have been unsubscribed from deposit notifications.")
            logger.info(f"User {chat_id} unsubscribed from notifications")
        except Exception as e:
            logger.error(f"Error unsubscribing user: {e}")
            await update.message.reply_text("An error occurred while unsubscribing. Please try again later.")

    async def test_notification(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        try:
            await self.application.bot.send_message(chat_id=chat_id, text="This is a test notification!")
            logger.info(f"Test notification sent successfully to chat_id: {chat_id}")
            await update.message.reply_text("Test notification sent successfully!")
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}")
            await update.message.reply_text("Failed to send test notification. Please check the logs.")

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
        asyncio.create_task(self.send_notification(deposit))
        logger.info(f"Created task to send notification for deposit: {deposit['hash']}")

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

    async def send_notification(self, deposit):
        if not self.application:
            logger.error("Telegram application not initialized")
            return

        try:
            message = f"New Deposit Detected!\n\n" \
                      f"Block Number: {deposit['blockNumber']}\n" \
                      f"Transaction Hash: {deposit['hash']}\n" \
                      f"Public Key: {deposit['pubkey'][:10]}...{deposit['pubkey'][-10:]}\n" \
                      f"Fee: {Web3.from_wei(int(deposit['fee']), 'ether'):.6f} ETH"
            
            logger.info(f"Preparing to send notification for deposit: {deposit['hash']}")
            
            self.cursor.execute('SELECT chat_id FROM Telegram_Subscriptions')
            subscribers = self.cursor.fetchall()
            
            if not subscribers:
                logger.warning("No subscribers found for notifications")
                return

            logger.info(f"Found {len(subscribers)} subscribers")

            for (chat_id,) in subscribers:
                try:
                    logger.info(f"Attempting to send notification to chat_id: {chat_id}")
                    await self.application.bot.send_message(chat_id=chat_id, text=message)
                    logger.info(f"Notification sent successfully to chat_id: {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send notification to chat_id {chat_id}: {e}")
            
            logger.info(f"Completed sending Telegram notifications for deposit: {deposit['hash']}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notifications: {e}")

    async def run(self):
        while True:
            try:
                current_block = w3.eth.get_block('latest')['number']
                
                if current_block > self.last_processed_block:
                    self.handle_reorg(current_block)
                
                while self.last_processed_block < current_block:
                    self.last_processed_block += 1
                    self.process_block(self.last_processed_block)
                
                await asyncio.sleep(15)  # Wait for 15 seconds before checking for new blocks
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)  # Wait for 1 minute before retrying in case of a major error

async def main():
    try:
        tracker = DepositTracker()
        await tracker.setup_telegram_bot()
        await tracker.run()
    except Exception as e:
        logger.error(f"Failed to initialize or run DepositTracker: {e}")

if __name__ == "__main__":
    asyncio.run(main())