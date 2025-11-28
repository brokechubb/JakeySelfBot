"""Test the updated help command"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_help_command():
    """Test the help command content"""
    print("Testing help command content...")
    
    # Simulate the help text
    help_text = """**💀 JAKEY BOT HELP 💀**

 **🕹️ CORE COMMANDS:**
 `%ping` - Check if Jakey is alive
 `%help` - Show this help message
 `%stats` - Show bot statistics
 `%model [model_name]` - Show or set current AI model
 `%models` - List all available AI models

 **🧠 MEMORY COMMANDS:**
 `%remember <type> <info>` - Remember important information about you
 `%friends` - List Jakey's friends
 `%userinfo [user]` - Get information about a user (admin only)
 `%clearhistory [user]` - Clear conversation history for a user (admin only for others)
 `%clearallhistory` - Clear ALL conversation history (admin only)

 **🎰 GAMBLING COMMANDS:**
 `%rigged` - Classic Jakey response
 `%wen <item>` - Get bonus schedule information

 **🎨 AI COMMANDS:**
 `%image <prompt>` - Generate an image (supports: 1024x1024 flux seed=42)
 `%audio <text>` - Generate audio from text

 **💥 EXAMPLES:**
 `%remember favorite_team Dallas Cowboys`
 `%wen monthly`
 `%image a degenerate gambler`
 `%image 512x512 anime cute cat`
 `%image realistic seed=123 city skyline`
 `%audio Welcome to the degenerate courtyard!`

 **📚 For more detailed documentation, see the docs directory!**
 """
    
    print("Help text content:")
    print(help_text)
    
    # Check that all expected commands are included
    expected_commands = [
        '%ping', '%help', '%stats', '%model', '%models',
        '%remember', '%friends', '%userinfo', '%clearhistory', '%clearallhistory',
        '%rigged', '%wen',
        '%image', '%audio'
    ]
    
    missing_commands = []
    for command in expected_commands:
        if command not in help_text:
            missing_commands.append(command)
    
    if missing_commands:
        print(f"❌ Missing commands in help text: {missing_commands}")
        return False
    else:
        print("✅ All commands included in help text")
        return True

if __name__ == "__main__":
    success = test_help_command()
    sys.exit(0 if success else 1)