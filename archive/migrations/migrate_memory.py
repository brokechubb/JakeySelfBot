#!/usr/bin/env python3
"""
Memory System Migration Script

This script migrates the JakeySelfBot to use the new unified memory backend system.
It provides a safe migration path that maintains backward compatibility.
"""

import sys
import os
import asyncio
import logging
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryMigrationManager:
    """Manages the migration to unified memory backend"""

    def __init__(self):
        self.unified_backend = None
        self.legacy_sqlite = None
        self.legacy_mcp = None
        self.migration_stats = {
            "total_memories": 0,
            "migrated_memories": 0,
            "errors": 0,
            "skipped": 0
        }

    async def initialize(self):
        """Initialize memory backends"""
        try:
            # Try to import unified backend
            from memory.unified_backend import UnifiedMemoryBackend
            self.unified_backend = UnifiedMemoryBackend()
            logger.info("✅ Unified memory backend initialized")
        except ImportError as e:
            logger.error(f"❌ Failed to import unified memory backend: {e}")
            return False

        # Initialize legacy systems for comparison
        try:
            from data.database import db
            from tools.mcp_memory_client import MCPMemoryClient
            from config import MCP_MEMORY_ENABLED

            self.legacy_sqlite = db

            if MCP_MEMORY_ENABLED:
                self.legacy_mcp = MCPMemoryClient()
                logger.info("✅ Legacy MCP memory client initialized")
            else:
                logger.info("ℹ️  MCP memory disabled, skipping legacy MCP client")

        except Exception as e:
            logger.warning(f"⚠️  Failed to initialize legacy systems: {e}")

        return True

    async def verify_system_health(self) -> bool:
        """Verify all memory systems are healthy"""
        logger.info("🔍 Verifying system health...")

        if not self.unified_backend:
            logger.error("❌ Unified backend not available")
            return False

        # Check unified backend health
        try:
            health = await self.unified_backend.health_check()
            healthy_count = sum(health.values())
            total_count = len(health)

            logger.info(f"📊 Unified backend health: {healthy_count}/{total_count} backends healthy")

            if healthy_count == 0:
                logger.error("❌ No healthy backends in unified system")
                return False

        except Exception as e:
            logger.error(f"❌ Unified backend health check failed: {e}")
            return False

        return True

    async def perform_data_migration(self, dry_run: bool = True) -> bool:
        """Migrate existing data to unified backend"""
        logger.info(f"🚀 Starting data migration (dry_run={dry_run})...")

        if not self.unified_backend:
            logger.error("❌ Unified backend not available")
            return False

        # Get all users from SQLite
        try:
            users = await self._get_all_users()
            logger.info(f"👥 Found {len(users)} users to migrate")

            for user_id in users:
                await self._migrate_user_memories(user_id, dry_run)

        except Exception as e:
            logger.error(f"❌ Data migration failed: {e}")
            return False

        # Log migration statistics
        stats = self.migration_stats
        logger.info("📊 Migration Statistics:")
        logger.info(f"   Total memories: {stats['total_memories']}")
        logger.info(f"   Migrated: {stats['migrated_memories']}")
        logger.info(f"   Errors: {stats['errors']}")
        logger.info(f"   Skipped: {stats['skipped']}")

        success_rate = (stats['migrated_memories'] / stats['total_memories'] * 100) if stats['total_memories'] > 0 else 0
        logger.info(f"   Success rate: {success_rate:.1f}%")

        return stats['errors'] == 0

    async def _get_all_users(self) -> list:
        """Get all users who have memories"""
        try:
            # Query SQLite for users with memories
            import sqlite3
            from config import DATABASE_PATH

            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute("SELECT DISTINCT user_id FROM memories")
            users = [row[0] for row in cursor.fetchall()]

            conn.close()
            return users

        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []

    async def _migrate_user_memories(self, user_id: str, dry_run: bool):
        """Migrate memories for a specific user"""
        try:
            # Get memories from legacy SQLite system
            sqlite_memories = await self.legacy_sqlite.aget_memories(user_id)
            self.migration_stats['total_memories'] += len(sqlite_memories)

            logger.debug(f"📋 Migrating {len(sqlite_memories)} memories for user {user_id}")

            for key, value in sqlite_memories.items():
                try:
                    # Check if memory already exists in unified system
                    existing = await self.unified_backend.retrieve(user_id, key)

                    if existing:
                        logger.debug(f"⏭️  Memory {key} already exists, skipping")
                        self.migration_stats['skipped'] += 1
                        continue

                    # Migrate the memory
                    if not dry_run:
                        success = await self.unified_backend.store(user_id, key, value)
                        if success:
                            logger.debug(f"✅ Migrated memory {key}")
                            self.migration_stats['migrated_memories'] += 1
                        else:
                            logger.warning(f"❌ Failed to migrate memory {key}")
                            self.migration_stats['errors'] += 1
                    else:
                        # Dry run - just count
                        self.migration_stats['migrated_memories'] += 1
                        logger.debug(f"📝 Would migrate memory {key}")

                except Exception as e:
                    logger.error(f"❌ Error migrating memory {key} for user {user_id}: {e}")
                    self.migration_stats['errors'] += 1

        except Exception as e:
            logger.error(f"❌ Failed to migrate memories for user {user_id}: {e}")
            self.migration_stats['errors'] += 1

    async def enable_production_mode(self) -> bool:
        """Enable the unified memory backend for production use"""
        logger.info("🔄 Enabling unified memory backend for production...")

        # This would update configuration or create a flag
        # For now, we'll just verify the system is ready

        if not await self.verify_system_health():
            logger.error("❌ System health check failed - not enabling production mode")
            return False

        # Create a production flag file
        flag_file = os.path.join(os.path.dirname(__file__), '..', '.memory_migration_complete')
        try:
            with open(flag_file, 'w') as f:
                f.write("Unified memory backend enabled for production\n")
                f.write(f"Timestamp: {asyncio.get_event_loop().time()}\n")
            logger.info("✅ Production mode enabled - unified memory backend is now active")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create production flag: {e}")
            return False

    async def rollback_migration(self) -> bool:
        """Rollback to legacy memory system"""
        logger.warning("🔄 Rolling back to legacy memory system...")

        # Remove production flag
        flag_file = os.path.join(os.path.dirname(__file__), '..', '.memory_migration_complete')
        try:
            if os.path.exists(flag_file):
                os.remove(flag_file)
            logger.info("✅ Migration rolled back - legacy memory system restored")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to rollback migration: {e}")
            return False

async def main():
    """Main migration function"""
    print("🧠 JakeySelfBot Memory System Migration")
    print("=" * 50)

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Migrate to unified memory backend")
    parser.add_argument("--verify", action="store_true", help="Only verify system health")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run migration")
    parser.add_argument("--migrate", action="store_true", help="Perform actual data migration")
    parser.add_argument("--enable-prod", action="store_true", help="Enable production mode")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")

    args = parser.parse_args()

    # Initialize migration manager
    manager = MemoryMigrationManager()

    if not await manager.initialize():
        print("❌ Failed to initialize migration manager")
        return 1

    # Execute requested operation
    if args.verify:
        print("🔍 Verifying system health...")
        success = await manager.verify_system_health()
        print(f"✅ Health check: {'PASSED' if success else 'FAILED'}")

    elif args.dry_run:
        print("📝 Performing dry run migration...")
        success = await manager.perform_data_migration(dry_run=True)
        print(f"✅ Dry run: {'PASSED' if success else 'FAILED'}")

    elif args.migrate:
        print("🚀 Performing data migration...")
        success = await manager.perform_data_migration(dry_run=False)
        print(f"✅ Migration: {'PASSED' if success else 'FAILED'}")

    elif args.enable_prod:
        print("🔄 Enabling production mode...")
        success = await manager.enable_production_mode()
        print(f"✅ Production mode: {'ENABLED' if success else 'FAILED'}")

    elif args.rollback:
        print("🔄 Rolling back migration...")
        success = await manager.rollback_migration()
        print(f"✅ Rollback: {'SUCCESSFUL' if success else 'FAILED'}")

    else:
        print("Usage: python migrate_memory.py [options]")
        print("Options:")
        print("  --verify       Verify system health")
        print("  --dry-run      Perform dry run migration")
        print("  --migrate      Perform actual data migration")
        print("  --enable-prod  Enable production mode")
        print("  --rollback     Rollback migration")
        return 1

    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)