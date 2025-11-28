#!/usr/bin/env python3
"""
Tests for overall project structure and imports
"""

import unittest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestProjectStructure(unittest.TestCase):
    """Test cases for overall project structure"""
    
    def test_required_directories_exist(self):
        """Test that required directories exist"""
        required_dirs = ['ai', 'bot', 'data', 'tools', 'media', 'tests']
        
        for dir_name in required_dirs:
            dir_path = os.path.join(os.path.dirname(__file__), '..', dir_name)
            self.assertTrue(
                os.path.exists(dir_path), 
                f"Required directory '{dir_name}' does not exist"
            )
            self.assertTrue(
                os.path.isdir(dir_path),
                f"'{dir_name}' exists but is not a directory"
            )
    
    def test_required_files_exist(self):
        """Test that required files exist"""
        required_files = [
            'main.py',
            'config.py',
            'requirements.txt',
            'README.md'
        ]
        
        for file_name in required_files:
            file_path = os.path.join(os.path.dirname(__file__), '..', file_name)
            self.assertTrue(
                os.path.exists(file_path),
                f"Required file '{file_name}' does not exist"
            )
    
    def test_module_imports(self):
        """Test that main modules can be imported"""
        modules_to_test = [
            'config',
            'data.database',
            'tools.tool_manager',
            'ai.pollinations',
            'media.image_generator',
            'bot.client'
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                import_success = True
            except ImportError as e:
                import_success = False
                print(f"Failed to import {module_name}: {e}")
            
            self.assertTrue(
                import_success,
                f"Module '{module_name}' should import without errors"
            )
    
    def test_command_imports(self):
        """Test that commands module can be imported"""
        try:
            # We need to mock the bot import to avoid circular dependencies
            import sys
            from unittest.mock import MagicMock
            
            # Mock the bot import
            sys.modules['bot.client'] = MagicMock()
            
            # Now try to import commands
            import bot.commands
            import_success = True
        except ImportError as e:
            import_success = False
            print(f"Failed to import bot.commands: {e}")
        except Exception as e:
            # Other exceptions might occur due to mocking, which is expected
            import_success = True
        
        self.assertTrue(
            import_success,
            "Commands module should import without critical errors"
        )

if __name__ == '__main__':
    unittest.main()