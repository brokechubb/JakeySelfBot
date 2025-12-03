#!/bin/bash

# Test script for automatic memory extraction system

echo "🧠 Testing Jakey's Automatic Memory System"
echo "=========================================="

# Make sure Python can find our modules
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Check if required modules are available
echo "1. Checking memory backend availability..."
python3 -c "
try:
    from memory import memory_backend
    if memory_backend:
        print('✅ Memory backend available')
    else:
        print('❌ Memory backend not available')
except Exception as e:
    print(f'❌ Memory backend error: {e}')
"

echo ""
echo "2. Testing memory extraction..."
python3 test_auto_memory.py

echo ""
echo "3. Checking configuration..."
python3 -c "
from config import (
    AUTO_MEMORY_EXTRACTION_ENABLED,
    AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD,
    AUTO_MEMORY_CLEANUP_ENABLED,
    AUTO_MEMORY_MAX_AGE_DAYS
)
print(f'✅ Auto memory extraction: {\"enabled\" if AUTO_MEMORY_EXTRACTION_ENABLED else \"disabled\"}')
print(f'✅ Confidence threshold: {AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD}')
print(f'✅ Cleanup enabled: {\"enabled\" if AUTO_MEMORY_CLEANUP_ENABLED else \"disabled\"}')
print(f'✅ Max memory age: {AUTO_MEMORY_MAX_AGE_DAYS} days')
"

echo ""
echo "✅ Memory system test complete!"
echo ""
echo "To enable auto memory extraction, add to your .env file:"
echo "AUTO_MEMORY_EXtraction_ENABLED=true"
echo "AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD=0.4"
echo "AUTO_MEMORY_CLEANUP_ENABLED=true"
echo "AUTO_MEMORY_MAX_AGE_DAYS=365"