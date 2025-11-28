"""
Test module for gender role functionality
"""
import unittest
import os
import sys
from unittest.mock import Mock, MagicMock, patch

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestGenderRoleManager(unittest.TestCase):
    """Test cases for GenderRoleManager"""

    def test_load_gender_mappings(self):
        """Test loading gender mappings from environment variable"""
        with patch.dict(os.environ, {"GENDER_ROLE_MAPPINGS": "male:123456789,female:987654321,neutral:111222333"}):
            # Reload config
            import importlib
            import config
            importlib.reload(config)
            
            # Reload gender_roles module to pick up new config
            import utils.gender_roles
            importlib.reload(utils.gender_roles)
            
            manager = utils.gender_roles.GenderRoleManager()
            mappings = manager.get_gender_role_config()

            self.assertIn("male", mappings)
            self.assertIn("female", mappings)
            self.assertIn("neutral", mappings)

            male_roles = mappings["male"]["roles"]
            female_roles = mappings["female"]["roles"]
            neutral_roles = mappings["neutral"]["roles"]

            # Role IDs are stored as integers in the manager
            self.assertIn(123456789, male_roles)
            self.assertIn(987654321, female_roles)
            self.assertIn(111222333, neutral_roles)

    def test_get_pronouns(self):
        """Test getting pronouns for different genders"""
        # Test with default mappings (no environment variable)
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config
            importlib.reload(config)
            
            import utils.gender_roles
            importlib.reload(utils.gender_roles)
            
            manager = utils.gender_roles.GenderRoleManager()

            # Test male pronouns
            male_pronouns = manager.get_pronouns("male")
            self.assertEqual(male_pronouns, ("he", "him", "his"))

            # Test female pronouns
            female_pronouns = manager.get_pronouns("female")
            self.assertEqual(female_pronouns, ("she", "her", "hers"))

            # Test neutral pronouns
            neutral_pronouns = manager.get_pronouns("neutral")
            self.assertEqual(neutral_pronouns, ("they", "them", "their"))

            # Test invalid gender (should default to neutral)
            invalid_pronouns = manager.get_pronouns("invalid")
            self.assertEqual(invalid_pronouns, ("they", "them", "their"))

    def test_default_mappings(self):
        """Test default gender mappings when environment variable is not set"""
        # Test with empty GENDER_ROLE_MAPPINGS
        with patch.dict(os.environ, {"GENDER_ROLE_MAPPINGS": ""}):
            import importlib
            import config
            importlib.reload(config)
            
            import utils.gender_roles
            importlib.reload(utils.gender_roles)
            
            manager = utils.gender_roles.GenderRoleManager()
            mappings = manager.get_gender_role_config()

            # Should have default mappings with empty roles
            self.assertIn("male", mappings)
            self.assertIn("female", mappings)
            self.assertIn("neutral", mappings)

            # Roles should be empty lists
            self.assertEqual(mappings["male"]["roles"], [])
            self.assertEqual(mappings["female"]["roles"], [])
            self.assertEqual(mappings["neutral"]["roles"], [])


class TestGetUserPronouns(unittest.TestCase):
    """Test cases for get_user_pronouns function"""

    def test_get_user_pronouns_with_mock_member(self):
        """Test get_user_pronouns with a mock Discord member"""
        with patch.dict(os.environ, {"GENDER_ROLE_MAPPINGS": "male:123456789,female:987654321"}):
            import importlib
            import config
            importlib.reload(config)
            
            import utils.gender_roles
            importlib.reload(utils.gender_roles)
            
            # Create a mock member with a specific role
            mock_member = Mock()
            mock_role = Mock()
            mock_role.id = 123456789
            mock_member.roles = [mock_role]
            mock_member.id = 111111111

            # Test pronoun assignment using the direct function
            pronouns = utils.gender_roles.get_user_pronouns(mock_member)
            self.assertEqual(pronouns, ("he", "him", "his"))  # Should be male pronouns


if __name__ == '__main__':
    unittest.main()