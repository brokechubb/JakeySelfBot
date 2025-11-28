"""Test that help command content is correctly updated"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_help_content():
    """Test that help command content includes all commands"""
    print("Testing help command content...")
    
    # Read the commands file
    with open('/home/chubb/bots/JakeySelfBot/bot/commands.py', 'r') as f:
        content = f.read()
    
    # Check that the help command contains all expected commands
    if 'help_command' in content:
        print("✅ help_command function found")
    else:
        print("❌ help_command function not found")
        return False
    
    # Check for key commands in help text
    expected_in_help = [
        '`%ping`',
        '`%help`', 
        '`%stats`',
        '`%model',
        '`%models`',
        '`%remember',
        '`%friends`',
        '`%userinfo',
        '`%clearhistory',
        '`%clearallhistory`',
        '`%rigged`',
        '`%wen',
        '`%image',
        '`%audio'
    ]
    
    missing_from_help = []
    for item in expected_in_help:
        if item not in content:
            missing_from_help.append(item)
    
    if missing_from_help:
        print(f"❌ Missing from help content: {missing_from_help}")
        return False
    else:
        print("✅ All commands included in help content")
        return True

if __name__ == "__main__":
    success = test_help_content()
    if success:
        print("\n🎉 Help command content is correctly updated!")
    else:
        print("\n💥 Help command content is missing items!")
    sys.exit(0 if success else 1)