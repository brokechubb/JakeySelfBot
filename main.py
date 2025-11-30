# Jakey Self-Bot - Discord AI Assistant
# Copyright (C) 2025 brokechubb
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from config import DISCORD_TOKEN
from bot.client import JakeyBot
from utils.dependency_container import init_dependencies
from utils.logging_config import setup_logging
import traceback
import asyncio
import signal
import sys
import os
import fcntl
import logging

# Set up colored logging with file output
setup_logging("INFO", log_to_file=True, log_file_path="logs/jakey_selfbot.log")

# Get logger for main module
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True

# File lock for ensuring only one instance runs
LOCK_FILE_PATH = "/tmp/jakey.lock"
lock_file = None

def acquire_lock():
    """Acquire a lock file to ensure only one instance runs"""
    global lock_file
    try:
        lock_file = open(LOCK_FILE_PATH, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        return True
    except IOError:
        if lock_file:
            lock_file.close()
        return False

def release_lock():
    """Release the lock file"""
    global lock_file
    if lock_file:
        try:
            os.unlink(LOCK_FILE_PATH)
        except:
            pass
        lock_file.close()

# File lock for ensuring only one instance runs
LOCK_FILE_PATH = "/tmp/jakey.lock"
lock_file = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info("🛑 Received shutdown signal...")
    running = False
    # Release the lock file
    release_lock()
    # The bot will be stopped gracefully in the main loop
    sys.exit(0)

def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Main entry point with improved error handling and reconnection"""
    global running

    # Acquire lock to ensure only one instance runs
    if not acquire_lock():
        logger.warning("⚠️  Another instance of Jakey is already running!")
        sys.exit(1)

    # Set up signal handler to release lock on exit
    def signal_handler_with_lock(signum, frame):
        release_lock()
        signal_handler(signum, frame)

    signal.signal(signal.SIGINT, signal_handler_with_lock)
    signal.signal(signal.SIGTERM, signal_handler_with_lock)

    # Check if DISCORD_TOKEN is available
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN is not set. Please check your .env file.")
        release_lock()
        sys.exit(1)

    # Check MCP Memory Server if enabled
    from config import MCP_MEMORY_ENABLED
    from tools.mcp_memory_client import get_mcp_server_url

    if MCP_MEMORY_ENABLED:
        mcp_server_url = get_mcp_server_url()
        import aiohttp
        async def check_mcp_server():
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get(f"{mcp_server_url}/health") as response:
                        return response.status == 200
            except Exception:
                return False

        # Run the check synchronously
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            mcp_available = loop.run_until_complete(check_mcp_server())
            loop.close()

            if mcp_available:
                logger.info("✅ MCP Memory Server is accessible")
            else:
                logger.warning(f"⚠️  MCP Memory Server not accessible at {mcp_server_url}")
                logger.info("💡 Run './start_mcp_server.sh' to start the MCP server, or set MCP_MEMORY_ENABLED=false")
        except Exception as e:
            logger.warning(f"⚠️  Could not check MCP Memory Server: {e}")

    logger.info("🚀 Starting Jakey Self-Bot...")
    logger.info(f"Token loaded: {len(DISCORD_TOKEN) > 0}")

    # Initialize dependencies
    try:
        deps = init_dependencies(DISCORD_TOKEN)
        bot = JakeyBot(deps)

        # Initialize TipCCManager with bot instance after bot is created
        from utils.tipcc_manager import init_tipcc_manager
        tipcc_manager = init_tipcc_manager(bot)
        bot.tipcc_manager = tipcc_manager
        deps.tipcc_manager = tipcc_manager

        # Initialize Discord tools with bot client
        from tools.tool_manager import tool_manager
        tool_manager.set_discord_tools(bot)

        # Set up message queue initialization flag for bot to use in on_ready
        from config import MESSAGE_QUEUE_ENABLED
        bot._message_queue_enabled = MESSAGE_QUEUE_ENABLED

        logger.info("✅ Dependencies initialized successfully")
    except Exception as e:
        logger.error(f"💀 Failed to initialize dependencies: {e}")
        release_lock()
        sys.exit(1)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Configure asyncio event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    reconnect_delay = 1.0  # Start with 1 second delay

    while running:
        try:
            logger.info(f"🔌 Attempting to connect to Discord...")
            # Run the bot with improved error handling
            loop.run_until_complete(bot.start(DISCORD_TOKEN))
            reconnect_delay = 1.0  # Reset delay on successful connection
            logger.info("✅ Connected to Discord successfully!")

            # Run the bot until it's disconnected
            loop.run_until_complete(bot.connect())

        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
            break
        except Exception as e:
            error_msg = str(e).lower()

            # Handle specific connection errors
            if "cannot write to closing transport" in error_msg:
                logger.warning("⚠️  Discord connection reset detected - this is usually temporary")
                logger.info(f"⏳ Reconnecting in {reconnect_delay:.2f} seconds...")
            elif "4014" in str(e):
                logger.error("💀 Authentication failed - check your DISCORD_TOKEN!")
                break
            elif "4013" in str(e):
                logger.error("💀 Invalid token format - check your DISCORD_TOKEN!")
                break
            else:
                logger.error(f"💀 Discord connection error: {e}")
                logger.info(f"⏳ Reconnecting in {reconnect_delay:.2f} seconds...")

            # Exponential backoff with max delay
            if reconnect_delay < 60.0:  # Increased cap
                reconnect_delay *= 1.5
            else:
                reconnect_delay = 60.0  # Cap at 60 seconds

            # Wait before reconnecting
            loop.run_until_complete(asyncio.sleep(reconnect_delay))

        finally:
            # Clean up on disconnect
            if bot.is_closed():
                logger.info("🔌 Bot connection closed")

    # Clean shutdown
    try:
        loop.run_until_complete(bot.close())
        logger.info("🛑 Bot shutdown complete")
    except Exception as e:
        logger.warning(f"⚠️  Error during shutdown: {e}")
    finally:
        release_lock()
        loop.close()

if __name__ == "__main__":
    main()
