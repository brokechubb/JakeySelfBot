import logging
import os
from logging import Formatter, StreamHandler, FileHandler, getLogger
from logging.handlers import RotatingFileHandler
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

class ColourFormatter(Formatter):
    """Custom formatter with colored output for different log levels."""

    LEVEL_COLOURS = [
        (DEBUG, "\x1b[40;1m"),
        (INFO, "\x1b[34;1m"),
        (WARNING, "\x1b[33;1m"),
        (ERROR, "\x1b[31m"),
        (CRITICAL, "\x1b[41m"),
    ]

    FORMATS = {
        level: Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m "
            f"\x1b[35m%(name)s\x1b[0m %(message)s "
            f"\x1b[30;1m(%(filename)s:%(lineno)d)\x1b[0m",
            "%H:%M:%S",  # Shortened time format
        )
        for level, colour in LEVEL_COLOURS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno, self.FORMATS[DEBUG])
        return formatter.format(record)

class PM2CompatibleFormatter(Formatter):
    """Simple formatter for PM2 compatibility without colors."""

    def __init__(self):
        super().__init__(
            "%(asctime)s %(levelname)-8s %(name)s %(message)s (%(filename)s:%(lineno)d)",
            "%Y-%m-%d %H:%M:%S"
        )

class FileFormatter(Formatter):
    """Simple formatter for file output without colors."""

    def __init__(self):
        super().__init__(
            "%(asctime)s %(levelname)-8s %(name)s %(message)s (%(filename)s:%(lineno)d)",
            "%Y-%m-%d %H:%M:%S"
        )

class SystemdFormatter(Formatter):
    """Formatter optimized for systemd journal output."""

    def __init__(self):
        super().__init__(
            "%(levelname)s %(name)s %(message)s (%(filename)s:%(lineno)d)"
        )

def setup_logging(level="INFO", log_to_file=False, log_file_path="logs/jakey_selfbot.log", max_file_size=10*1024*1024, backup_count=5):
    """
    Set up logging for the application, with PM2 compatibility and optional file logging.

    Args:
        level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file (bool): Whether to log to a file in addition to console
        log_file_path (str): Path to the log file (if log_to_file is True)
        max_file_size (int): Maximum size of log file before rotation (default 10MB)
        backup_count (int): Number of backup files to keep

    Returns:
        logging.Logger: Configured logger instance
    """
    # Check if running under PM2
    is_pm2 = os.environ.get('PM2_HOME') is not None or os.environ.get('PM2_JSON_PROCESSING') is not None

    # Check if running under systemd
    is_systemd = os.environ.get('JOURNAL_STREAM') is not None or os.environ.get('INVOCATION_ID') is not None

    # Create handlers list
    handlers = []

    # Always add console handler
    console_handler = StreamHandler()

    # Use appropriate formatter based on environment
    if is_pm2:
        console_handler.setFormatter(PM2CompatibleFormatter())
    elif is_systemd:
        console_handler.setFormatter(SystemdFormatter())
    else:
        console_handler.setFormatter(ColourFormatter())

    handlers.append(console_handler)

    # Add file handler if requested
    if log_to_file:
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file_path) if os.path.dirname(log_file_path) else "logs"
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except OSError as e:
                # If we can't create the directory, log to the current directory
                log_dir = "."
                log_file_path = os.path.basename(log_file_path)

        # Use rotating file handler to prevent log files from growing too large
        try:
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=max_file_size,
                backupCount=backup_count
            )
            file_handler.setFormatter(FileFormatter())
            handlers.append(file_handler)
        except Exception as e:
            # If we can't create a file handler, continue with console only
            print(f"Warning: Could not set up file logging: {e}")

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=True  # Override any existing configuration
    )

    return logging.getLogger()

def get_logger(name=None):
    """
    Get a logger with appropriate formatting for the environment.

    Args:
        name (str): Logger name (typically __name__ from the calling module)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = getLogger(name)

    # Check if running under PM2
    is_pm2 = os.environ.get('PM2_HOME') is not None or os.environ.get('PM2_JSON_PROCESSING') is not None

    # If no handlers are present, inherit from root logger
    # This prevents duplicate handlers while maintaining proper logging hierarchy
    if not logger.handlers:
        # Let the logger inherit from the root logger's configuration
        pass

    return logger
