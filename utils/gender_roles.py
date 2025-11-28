"""
Gender role utility for JakeySelfBot
Handles role-to-gender mapping and pronoun selection based on user roles
"""
import discord


import logging
from typing import Optional, Dict, Tuple
from config import GENDER_ROLE_MAPPINGS

logger = logging.getLogger(__name__)

# Default gender role mappings if not configured
DEFAULT_GENDER_MAPPINGS = {
    "male": {"pronouns": ("he", "him", "his"), "roles": []},
    "female": {"pronouns": ("she", "her", "hers"), "roles": []},
    "neutral": {"pronouns": ("they", "them", "their"), "roles": []}
}

class GenderRoleManager:
    """Manages gender role mappings and pronoun assignment"""

    def __init__(self, bot_instance=None):
        self.bot = bot_instance
        self.gender_mappings = self._load_gender_mappings()
        # Track if this is the global instance to avoid duplication
        self._is_global_instance = False

    def _load_gender_mappings(self) -> Dict:
        """Load gender role mappings from config or use defaults"""
        try:
            if GENDER_ROLE_MAPPINGS:
                # Parse the GENDER_ROLE_MAPPINGS from config
                # Expected format: "male:123456789,female:987654321,neutral:111222333"
                # Create a fresh copy of default mappings to avoid modifying the original
                mappings = {
                    "male": {"pronouns": ("he", "him", "his"), "roles": []},
                    "female": {"pronouns": ("she", "her", "hers"), "roles": []},
                    "neutral": {"pronouns": ("they", "them", "their"), "roles": []}
                }
                role_pairs = GENDER_ROLE_MAPPINGS.split(',')

                processed_roles = set()  # Track processed role IDs to avoid duplication
                for pair in role_pairs:
                    if ':' in pair:
                        gender, role_id_str = pair.split(':')
                        gender = gender.strip().lower()
                        try:
                            role_id = int(role_id_str.strip())
                            # Avoid duplicate role entries
                            role_key = (gender, role_id)
                            if role_key not in processed_roles and gender in mappings:
                                mappings[gender]["roles"].append(role_id)
                                processed_roles.add(role_key)
                        except ValueError:
                            logger.warning(f"Invalid role ID format: {role_id_str}")

                return mappings
            else:
                # Return a fresh copy of default mappings
                return {
                    "male": {"pronouns": ("he", "him", "his"), "roles": []},
                    "female": {"pronouns": ("she", "her", "hers"), "roles": []},
                    "neutral": {"pronouns": ("they", "them", "their"), "roles": []}
                }
        except Exception as e:
            logger.error(f"Error loading gender mappings: {e}")
            return {
                "male": {"pronouns": ("he", "him", "his"), "roles": []},
                "female": {"pronouns": ("she", "her", "hers"), "roles": []},
                "neutral": {"pronouns": ("they", "them", "their"), "roles": []}
            }

    def get_user_gender(self, user: discord.Member, target_guild_id: Optional[int] = None) -> Optional[str]:
        """
        Determine a user's gender based on their roles in a specific server

        Args:
            user: Discord member object
            target_guild_id: Specific guild ID to check roles in

        Returns:
            Gender string (male, female, neutral) or None if undetermined
        """
        try:
            # If a specific guild is targeted, check roles in that guild
            if target_guild_id:
                guild = discord.utils.get(user.mutual_guilds, id=target_guild_id)
                if guild:
                    member = guild.get_member(user.id)
                    if member:
                        return self._get_gender_from_roles(member)

            # Otherwise check in the guild where the message was sent
            if hasattr(user, 'roles'):
                return self._get_gender_from_roles(user)

            return "neutral"  # Default to neutral if we can't determine
        except Exception as e:
            logger.error(f"Error determining user gender: {e}")
            return "neutral"

    def _get_gender_from_roles(self, member: discord.Member) -> Optional[str]:
        """Get gender based on member's roles"""
        try:
            role_ids = [role.id for role in member.roles]

            # Check each gender mapping for matching roles
            for gender, config in self.gender_mappings.items():
                for role_id in config["roles"]:
                    if role_id in role_ids:
                        return gender

            return "neutral"  # Default to neutral if no roles match
        except Exception as e:
            logger.error(f"Error getting gender from roles: {e}")
            return "neutral"

    def get_pronouns(self, gender: str) -> Tuple[str, str, str]:
        """
        Get pronouns for a given gender

        Args:
            gender: Gender string (male, female, neutral)

        Returns:
            Tuple of (subject, object, possessive) pronouns
        """
        try:
            return self.gender_mappings.get(gender, DEFAULT_GENDER_MAPPINGS["neutral"])["pronouns"]
        except Exception as e:
            logger.error(f"Error getting pronouns for gender {gender}: {e}")
            return ("they", "them", "their")

    def get_gender_role_config(self) -> Dict:
        """Get current gender role configuration"""
        return self.gender_mappings

# Global instance
gender_role_manager = GenderRoleManager()
gender_role_manager._is_global_instance = True

def initialize_gender_role_manager(bot_instance):
    """Initialize the gender role manager with the bot instance"""
    global gender_role_manager
    gender_role_manager = GenderRoleManager(bot_instance)

def get_user_pronouns(user: discord.Member, target_guild_id: Optional[int] = None) -> Tuple[str, str, str]:
    """
    Get appropriate pronouns for a user based on their roles

    Args:
        user: Discord member object
        target_guild_id: Specific guild ID to check roles in

    Returns:
        Tuple of (subject, object, possessive) pronouns
    """
    gender = gender_role_manager.get_user_gender(user, target_guild_id)
    return gender_role_manager.get_pronouns(gender)

def get_gender_role_config() -> Dict:
    """Get current gender role configuration"""
    return gender_role_manager.get_gender_role_config()
