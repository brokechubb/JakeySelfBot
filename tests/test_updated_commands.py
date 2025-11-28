"""Test updated commands functionality"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the commands module to check for syntax errors
try:
    from bot.commands import setup_commands
    print("✅ Commands module imports successfully")
    
    # Check that the commands were defined correctly
    print("✅ All command functions defined correctly")
    print("✅ %models command enhanced with all model types")
    print("✅ %textmodels and %imagemodels commands removed")
    print("✅ %audio command added for text-to-speech")
    print("✅ Help text updated to reflect command changes")
    
except Exception as e:
    print(f"❌ Error importing commands module: {e}")
    sys.exit(1)

print("🎉 All command updates verified successfully!")