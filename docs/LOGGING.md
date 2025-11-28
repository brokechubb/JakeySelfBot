# Logging Configuration

This document explains how to use the standardized logging configuration for the JakeySelfBot project.

## Overview

The JakeySelfBot project now uses a standardized logging configuration that provides:

1. Colored output for different log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
2. Consistent formatting with timestamps, level names, module names, and line numbers
3. Easy import and use across all modules
4. Compatibility with existing logging calls throughout the codebase
5. Optional file logging for persistent log storage

## Usage

### Setting up logging in main application

In your main application file, call `setup_logging()` to configure the root logger:

```python
from utils.logging_config import setup_logging

# Set up colored logging with INFO level
setup_logging("INFO")

# Or with DEBUG level for more verbose output
setup_logging("DEBUG")

# Enable file logging in addition to console output
setup_logging("INFO", log_to_file=True, log_file_path="logs/jakey_selfbot.log")
```

### Using loggers in modules

In individual modules, use `get_logger()` to create a logger with colored output:

```python
from utils.logging_config import get_logger

# Create a logger for your module
logger = get_logger(__name__)

# Use the logger as usual
logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")
logger.critical("This is a critical message")
```

### Example output

The logging configuration produces colored output like this:

```
06-Sep-2025 07:36:12 PM INFO     bot.client ✓ Client module logger working (test_logging.py:51)
06-Sep-2025 07:36:13 PM INFO     storage.database ✓ Database module logger working (test_logging.py:52)
06-Sep-2025 07:36:13 PM INFO     drop_sniper ✓ Airdrop logger working (test_logging.py:67)
```

Each log level has a distinct color:
- DEBUG: Dark gray background
- INFO: Blue text
- WARNING: Yellow text
- ERROR: Red text
- CRITICAL: Red background

## Files

- `utils/logging_config.py`: Contains the logging configuration implementation
- `utils/__init__.py`: Makes the utils directory a proper Python package

## Log Files

When file logging is enabled, logs are written to the specified file path. The default location is `logs/jakey_selfbot.log` relative to the working directory. The log directory will be created automatically if it doesn't exist.

## Integration

The logging configuration has been integrated into:
- `bot/client.py`: Main bot client module
- `storage/database.py`: Database manager module
- `jakey_airdrop.py`: Airdrop functionality module
- `main.py`: Main application entry point

All modules now use the standardized colored logging configuration.