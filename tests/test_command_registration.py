"""Test that all commands are properly registered"""
import sys
import os
from unittest.mock import Mock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_command_registration():
    """Test that all expected commands are registered"""
    print("Testing command registration...")
    
    try:
        # Create a mock bot instance
        mock_bot = Mock()
        mock_bot.command = Mock(return_value=lambda x: x)  # Decorator that returns the function
        mock_bot.user = Mock()
        
        # Import and call setup_commands
        from bot.commands import setup_commands
        
        # Call setup_commands with our mock bot
        setup_commands(mock_bot)
        
        print("✅ setup_commands executed successfully")
        
        # Check that bot.command was called for each expected command
        expected_commands = [
            'image', 'models', 'ping', 'rigged', 'wen', 
            'friends', 'userinfo', 'clearhistory', 'clearallhistory', 
            'stats', 'remember', 'model', 'help', 'audio'
        ]
        
        # Get the calls to bot.command
        command_calls = [call[0][0] for call in mock_bot.command.call_args_list]
        
        print(f"Registered commands: {command_calls}")
        
        # Check for expected commands
        missing_commands = []
        for command in expected_commands:
            if command not in command_calls:
                missing_commands.append(command)
        
        if missing_commands:
            print(f"❌ Missing registered commands: {missing_commands}")
            return False
        else:
            print("✅ All expected commands registered")
            return True
            
    except Exception as e:
        print(f"❌ Error testing command registration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_command_registration()
    if success:
        print("\n🎉 All commands are properly registered!")
    else:
        print("\n💥 Some commands are not properly registered!")
    sys.exit(0 if success else 1)