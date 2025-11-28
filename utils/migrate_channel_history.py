#!/usr/bin/env python3
"""
Migration script to convert existing user conversations to channel conversations.
This script adds channel_id to existing conversations in the database.
"""

import sqlite3
import json
import os
from config import DATABASE_PATH
from utils.logging_config import get_logger

logger = get_logger(__name__)

def migrate_conversations_to_channels():
    """Migrate existing conversations to include channel_id"""

    if not os.path.exists(DATABASE_PATH):
        logger.warning(f"Database file {DATABASE_PATH} does not exist. Nothing to migrate.")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Check if migration is needed
        cursor.execute("PRAGMA table_info(conversations)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'channel_id' not in column_names:
            logger.info("Channel migration already completed or not needed.")
            return

        # Get all conversations without channel_id
        cursor.execute("""
            SELECT id, user_id, message_history, created_at
            FROM conversations
            WHERE channel_id IS NULL
        """)

        conversations_to_migrate = cursor.fetchall()

        if not conversations_to_migrate:
            logger.info("No conversations need migration.")
            return

        logger.info(f"Found {len(conversations_to_migrate)} conversations to migrate.")

        # For each conversation, we'll assign it to a default channel
        # Since we don't have the original channel info, we'll use a generic channel ID
        default_channel_id = "migrated_channel"

        migrated_count = 0
        for conv_id, user_id, message_history, created_at in conversations_to_migrate:
            try:
                # Update the conversation with the default channel_id
                cursor.execute("""
                    UPDATE conversations
                    SET channel_id = ?
                    WHERE id = ?
                """, (default_channel_id, conv_id))

                migrated_count += 1

                if migrated_count % 100 == 0:
                    logger.info(f"Migrated {migrated_count} conversations...")

            except Exception as e:
                logger.error(f"Error migrating conversation {conv_id}: {e}")

        conn.commit()
        logger.info(f"Successfully migrated {migrated_count} conversations to channel '{default_channel_id}'")

        # Create an index for the new channel_id column if it doesn't exist
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_channel_created ON conversations(channel_id, created_at DESC)")
            logger.info("Created index for channel conversations.")
        except Exception as e:
            logger.warning(f"Could not create index: {e}")

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        conn.rollback()

    finally:
        conn.close()

def verify_migration():
    """Verify that the migration was successful"""
    if not os.path.exists(DATABASE_PATH):
        logger.warning(f"Database file {DATABASE_PATH} does not exist.")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Count total conversations
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_count = cursor.fetchone()[0]

        # Count conversations with channel_id
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE channel_id IS NOT NULL")
        with_channel_count = cursor.fetchone()[0]

        # Count conversations without channel_id
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE channel_id IS NULL")
        without_channel_count = cursor.fetchone()[0]

        logger.info("Migration verification:")
        logger.info(f"  Total conversations: {total_count}")
        logger.info(f"  With channel_id: {with_channel_count}")
        logger.info(f"  Without channel_id: {without_channel_count}")

        if without_channel_count == 0:
            logger.info("✅ Migration successful! All conversations have channel_id.")
        else:
            logger.warning(f"⚠️  Migration incomplete! {without_channel_count} conversations still lack channel_id.")

    except Exception as e:
        logger.error(f"Error during verification: {e}")

    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("Starting channel conversation migration...")

    # Run migration
    migrate_conversations_to_channels()

    # Verify migration
    verify_migration()

    logger.info("Migration process completed.")