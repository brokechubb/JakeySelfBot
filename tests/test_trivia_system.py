#!/usr/bin/env python3
"""
Trivia Database Test Script
Tests the trivia database functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.trivia_database import TriviaDatabase
from utils.logging_config import get_logger

logger = get_logger(__name__)


async def test_trivia_database():
    """Test basic trivia database functionality"""
    logger.info("Starting trivia database tests...")
    
    # Create database instance
    db = TriviaDatabase()
    
    try:
        # Test 1: Add category
        logger.info("Test 1: Adding category...")
        category_id = await db.add_category(
            name="Test Category",
            display_name="Test Category",
            description="A test category for trivia"
        )
        logger.info(f"✓ Category added with ID: {category_id}")
        
        # Test 2: Add question
        logger.info("Test 2: Adding question...")
        question_id = await db.add_question(
            category_name="Test Category",
            question_text="What is 2 + 2?",
            answer_text="4",
            difficulty=1,
            source="test"
        )
        logger.info(f"✓ Question added with ID: {question_id}")
        
        # Test 3: Find answer
        logger.info("Test 3: Finding answer...")
        answer = await db.find_answer("Test Category", "What is 2 + 2?")
        logger.info(f"✓ Found answer: {answer}")
        
        # Test 4: Get category stats
        logger.info("Test 4: Getting category statistics...")
        stats = await db.get_category_stats("Test Category")
        logger.info(f"✓ Category stats: {stats}")
        
        # Test 5: Get all categories
        logger.info("Test 5: Getting all categories...")
        categories = await db.get_all_categories()
        logger.info(f"✓ Found {len(categories)} categories")
        
        # Test 6: Database overview
        logger.info("Test 6: Getting database overview...")
        overview = await db.get_database_stats()
        logger.info(f"✓ Database overview: {overview}")
        
        logger.info("✅ All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    finally:
        db.close()


async def test_trivia_manager():
    """Test trivia manager functionality"""
    logger.info("Starting trivia manager tests...")
    
    try:
        # Import trivia manager
        from utils.trivia_manager import TriviaManager
        
        # Create manager instance
        manager = TriviaManager()
        await manager.initialize()
        
        # Test finding answer
        answer = await manager.find_trivia_answer(
            "Entertainment: Music", 
            "Who sang 'Bohemian Rhapsody'?"
        )
        logger.info(f"✓ Manager found answer: {answer}")
        
        # Test category listing
        categories = await manager.list_available_categories()
        logger.info(f"✓ Manager found {len(categories)} categories")
        
        # Test database overview
        overview = await manager.get_database_overview()
        logger.info(f"✓ Database health: {overview.get('health_status', 'unknown')}")
        
        await manager.close()
        logger.info("✅ Manager tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Manager test failed: {e}")
        return False


async def main():
    """Main test function"""
    logger.info("=" * 50)
    logger.info("TRIVIA DATABASE SYSTEM TESTS")
    logger.info("=" * 50)
    
    # Test basic database functionality
    db_test_passed = await test_trivia_database()
    
    # Test trivia manager functionality
    manager_test_passed = await test_trivia_manager()
    
    # Summary
    logger.info("=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Database Tests: {'✅ PASSED' if db_test_passed else '❌ FAILED'}")
    logger.info(f"Manager Tests: {'✅ PASSED' if manager_test_passed else '❌ FAILED'}")
    
    if db_test_passed and manager_test_passed:
        logger.info("🎉 All tests passed! Trivia system is ready.")
        return 0
    else:
        logger.error("💥 Some tests failed. Check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)