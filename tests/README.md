# Jakey Bot Tests

This directory contains test scripts for various components of the Jakey bot.

## Test Structure

- `test_runner.py` - Main test runner that executes all tests
- `test_database.py` - Tests for database functionality
- `test_tools.py` - Tests for tool functionality
- `test_commands.py` - Tests for command functionality
- `test_ai.py` - Tests for AI integration
- `test_config.py` - Tests for configuration loading

## Running Tests

To run all tests:

```bash
cd /path/to/JakeySelfBot
python -m tests.test_runner
```

To run individual test files:

```bash
python -m tests.test_database
python -m tests.test_tools
```

## Test Dependencies

Tests require the same dependencies as the main application plus:
- `unittest` (standard library)
- `mock` (for mocking external APIs)

## Test Categories

### Unit Tests
- Test individual functions and methods
- Mock external dependencies
- Focus on specific functionality

### Integration Tests
- Test interactions between components
- Test database operations
- Test API integrations

### Command Tests
- Test command parsing and execution
- Test error handling
- Test user feedback

## Writing New Tests

1. Create a new test file following the naming convention `test_*.py`
2. Import the necessary modules and components
3. Create test classes that inherit from `unittest.TestCase`
4. Write test methods that start with `test_`
5. Add the new test to `test_runner.py`