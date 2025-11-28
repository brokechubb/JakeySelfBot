#!/usr/bin/env python3
"""
Main test runner for Jakey Bot tests
"""

import unittest
import sys
import os

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_all_tests():
    """Run all tests in the tests directory"""
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)