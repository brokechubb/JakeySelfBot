"""
Integration of Advanced Anti-Repetition System

This module provides seamless integration of the advanced anti-repetition system
into the existing bot client with minimal disruption to current functionality.
"""
from typing import Tuple

from ai.advanced_anti_repetition import advanced_anti_repetition
from utils.logging_config import setup_logging

logger = setup_logging(__name__)


class AntiRepetitionIntegrator:
    """
    Integrates advanced anti-repetition capabilities into the existing bot.
    Provides backward compatibility while adding sophisticated features.
    """

    def __init__(self):
        self.legacy_mode = False  # Can be toggled for fallback

    def should_enhance_response(self, user_id: str, content: str) -> Tuple[bool, str]:
        """
        Modern replacement for _is_repetitive_response.
        Returns (should_enhance, enhancement_reason).
        """
        if self.legacy_mode:
            # Fallback to legacy system if needed
            return self._legacy_check(user_id, content)

        should_enhance, reason, suggestions = advanced_anti_repetition.should_enhance_response(
            user_id, content
        )

        if should_enhance:
            logger.debug(f"Response enhancement suggested for user {user_id}: {reason}")

        return should_enhance, reason

    def get_enhanced_system_prompt(self, user_id: str, base_prompt: str) -> str:
        """
        Get contextually enhanced system prompt for invisible guidance.
        This replaces the heavy-handed anti-repetition rules.
        """
        if self.legacy_mode:
            return base_prompt

        return advanced_anti_repetition.enhance_system_prompt_context(user_id, base_prompt)

    def record_response(self, user_id: str, content: str):
        """
        Record response for anti-repetition learning.
        Lightweight operation with automatic optimization.
        """
        if self.legacy_mode:
            # Legacy recording would go here
            return

        advanced_anti_repetition.record_response(user_id, content)

    def _legacy_check(self, user_id: str, content: str) -> Tuple[bool, str]:
        """
        Fallback method using the legacy system if needed.
        This maintains backward compatibility.
        """
        # Import legacy system only if needed to avoid circular imports
        try:
            from ai.response_uniqueness import response_uniqueness
            return response_uniqueness.is_repetitive_response(user_id, content)
        except ImportError:
            logger.warning("Legacy anti-repetition system not available")
            return False, ""

    def get_user_analytics(self, user_id: str) -> dict:
        """
        Get analytics about user interaction patterns.
        Useful for monitoring and optimization.
        """
        if self.legacy_mode:
            return {"legacy_mode": True}

        return advanced_anti_repetition.get_user_insights(user_id)

    def toggle_legacy_mode(self, enabled: bool):
        """
        Toggle between advanced and legacy anti-repetition systems.
        Useful for testing and fallback scenarios.
        """
        self.legacy_mode = enabled
        mode = "legacy" if enabled else "advanced"
        logger.info(f"Anti-repetition mode switched to: {mode}")


# Global integrator instance
anti_repetition_integrator = AntiRepetitionIntegrator()