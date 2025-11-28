"""
Test module for gender role guild restriction functionality
"""
import unittest
import os
import sys
from unittest.mock import Mock, MagicMock, patch

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestGenderRoleGuildRestriction(unittest.TestCase):
    """Test cases for gender role guild restriction"""

    def test_guild_restriction_with_correct_guild(self):
        """Test that gender roles work when in the correct guild"""
        with patch.dict(os.environ, {
            "GENDER_ROLE_MAPPINGS": "male:123456789,female:987654321,neutral:111222333",
            "GENDER_ROLES_GUILD_ID": "999999999999999999"
        }):
            import importlib
            import config
            importlib.reload(config)
            
            import utils.gender_roles
            importlib.reload(utils.gender_roles)
            
            # Create a mock member with a male role
            mock_member = Mock()
            mock_role = Mock()
            mock_role.id = 123456789
            mock_member.roles = [mock_role]
            
            # Test getting gender - the manager itself doesn't enforce guild restriction
            # (That's handled in bot/client.py)
            gender = utils.gender_roles.gender_role_manager.get_user_gender(mock_member)
            self.assertEqual(gender, "male")

    def test_no_guild_restriction_when_not_configured(self):
        """Test that gender roles work globally when no guild restriction is set"""
        with patch.dict(os.environ, {
            "GENDER_ROLE_MAPPINGS": "male:123456789,female:987654321,neutral:111222333",
            "GENDER_ROLES_GUILD_ID": ""
        }):
            import importlib
            import config
            importlib.reload(config)
            
            import utils.gender_roles
            importlib.reload(utils.gender_roles)
            
            # Create a mock member with a male role
            mock_member = Mock()
            mock_role = Mock()
            mock_role.id = 123456789
            mock_member.roles = [mock_role]
            
            gender = utils.gender_roles.gender_role_manager.get_user_gender(mock_member)
            self.assertEqual(gender, "male")


if __name__ == '__main__':
    unittest.main()