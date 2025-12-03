#!/usr/bin/env python3
"""
Trivia Database Seeding Script
Populates the trivia database with common categories and questions from external sources.
"""

import asyncio
import logging
import sys
from pathlib import Path
from urllib.parse import quote, unquote

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.trivia_database import TriviaDatabase
from utils.logging_config import get_logger

logger = get_logger(__name__)


class TriviaSeeder:
    """Trivia database seeder with external source integration"""

    def __init__(self):
        self.db = TriviaDatabase()
        self.github_base_url = "https://raw.githubusercontent.com/QuartzWarrior/OTDB-Source/main"
        
        # Predefined categories to seed (based on actual GitHub files)
        self.categories_to_seed = [
            "Entertainment: Music",
            "Entertainment: Japanese Anime & Manga", 
            "Entertainment: Video Games",
            "Entertainment: Cartoon & Animations",
            "Entertainment: Film",
            "Entertainment: Television",
            "Entertainment: Books",
            "Science & Nature",
            "Science: Computers",
            "Geography",
            "History",
            "General Knowledge",
            "Art",
            "Animals",
            "Celebrities",
            "Mythology",
            "Politics"
        ]

    async def seed_database(self):
        """Main seeding function"""
        logger.info("Starting trivia database seeding...")
        
        try:
            # Ensure categories exist
            await self._ensure_categories()
            
            # Seed questions from external sources
            total_imported = 0
            for category in self.categories_to_seed:
                logger.info(f"Seeding category: {category}")
                imported = await self._seed_category_from_external(category)
                total_imported += imported
                
            logger.info(f"Database seeding completed. Total questions imported: {total_imported}")
            
            # Show database statistics
            await self._show_database_stats()
            
        except Exception as e:
            logger.error(f"Error during database seeding: {e}")
            raise

    async def _ensure_categories(self):
        """Ensure all required categories exist in the database"""
        logger.info("Creating categories...")
        
        for category_name in self.categories_to_seed:
            category_id = await self.db.add_category(
                name=category_name,
                display_name=category_name,
                description=f"Trivia questions for {category_name}"
            )
            if category_id:
                logger.info(f"✓ Created category: {category_name}")
            else:
                logger.info(f"✓ Category already exists: {category_name}")

    async def _seed_category_from_external(self, category_name: str) -> int:
        """Seed a specific category from external GitHub source"""
        import aiohttp
        from urllib.parse import quote, unquote
        
        try:
            async with aiohttp.ClientSession() as session:
                # Try to fetch CSV from GitHub
                url = f"{self.github_base_url}/{quote(category_name)}.csv"
                
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            questions = self._parse_csv_content(content)
                            
                            if questions:
                                # Import to database
                                import_data = []
                                for q in questions:
                                    import_data.append({
                                        'category': category_name,
                                        'question': q['question'],
                                        'answer': q['answer'],
                                        'source': 'github_seed',
                                        'difficulty': 1
                                    })
                                
                                imported_count = await self.db.bulk_import_questions(import_data)
                                
                                # Also cache the questions for trivia manager
                                await self.db.cache_category_questions(category_name, questions, ttl_hours=24)
                                
                                logger.info(f"✓ Imported {imported_count} questions for {category_name} (cached)")
                                return imported_count
                            else:
                                logger.warning(f"✗ No questions found for {category_name}")
                                return 0
                        else:
                            logger.warning(f"✗ Failed to fetch {category_name}: HTTP {resp.status}")
                            return 0
                            
                except asyncio.TimeoutError:
                    logger.warning(f"✗ Timeout fetching {category_name}")
                    return 0
                except Exception as e:
                    logger.warning(f"✗ Error fetching {category_name}: {e}")
                    return 0
                    
        except Exception as e:
            logger.error(f"✗ Error seeding category {category_name}: {e}")
            return 0

    def _parse_csv_content(self, content: str):
        """Parse CSV content into question-answer pairs"""
        questions = []
        
        try:
            lines = content.strip().splitlines()
            for line in lines:
                if ',' in line:
                    # Split only on first comma to handle answers with commas
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        question = unquote(parts[0].strip())
                        answer = unquote(parts[1].strip())
                        
                        if question and answer:
                            questions.append({
                                'question': question,
                                'answer': answer
                            })
        except Exception as e:
            logger.error(f"Error parsing CSV content: {e}")
        
        return questions

    async def _show_database_stats(self):
        """Display database statistics after seeding"""
        try:
            stats = await self.db.get_database_stats()
            categories = await self.db.get_all_categories()
            
            logger.info("=" * 50)
            logger.info("DATABASE SEEDING SUMMARY")
            logger.info("=" * 50)
            logger.info(f"Total Categories: {stats.get('total_categories', 0)}")
            logger.info(f"Total Questions: {stats.get('total_questions', 0)}")
            logger.info(f"Total Attempts: {stats.get('total_attempts', 0)}")
            
            logger.info("\nCategories by question count:")
            for cat in categories[:10]:  # Show top 10
                logger.info(f"  • {cat['display_name']}: {cat['question_count']} questions")
            
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"Error showing database stats: {e}")


async def main():
    """Main entry point"""
    seeder = TriviaSeeder()
    
    try:
        await seeder.seed_database()
        logger.info("Trivia database seeding completed")
        return 0
    except KeyboardInterrupt:
        logger.info("Seeding interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)