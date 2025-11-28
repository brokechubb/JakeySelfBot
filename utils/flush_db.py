#!/usr/bin/env python3
"""
Script to flush the JakeySelfBot database
"""

from data.database import db
import os
from config import DATABASE_PATH
import logging

# Configure logging
from utils.logging_config import get_logger
logger = get_logger(__name__)

def main():
    logger.warning(f"⚠️  Warning: This will completely erase all data in {DATABASE_PATH}")
    logger.info("This operation cannot be undone.")
    
    # Confirm with user
    response = input("Type 'YES' to confirm database flush: ")
    if response != "YES":
        logger.info("❌ Database flush cancelled.")
        return
    
    try:
        # Show current database size if it exists
        if os.path.exists(DATABASE_PATH):
            file_size = os.path.getsize(DATABASE_PATH)
            logger.info(f"📁 Found database file with size: {file_size} bytes")
        else:
            logger.info("📁 No existing database file found")
        
        # Flush the database
        db.flush_database()
        
        logger.info("✅ Database flushed successfully!")
        logger.info("🆕 New empty database created")
        
    except Exception as e:
        logger.error(f"❌ Error flushing database: {e}")

if __name__ == "__main__":
    main()