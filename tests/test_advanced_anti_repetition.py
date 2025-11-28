"""
Advanced Anti-Repetition System Tests

Test suite for the new efficient and invisible anti-repetition system.
"""
import time
import unittest
from ai.advanced_anti_repetition import advanced_anti_repetition
from ai.anti_repetition_integrator import anti_repetition_integrator


class TestAdvancedAntiRepetition(unittest.TestCase):
    """Test the advanced anti-repetition system."""

    def setUp(self):
        """Set up test environment."""
        # Clear test data
        advanced_anti_repetition.user_signatures.clear()
        advanced_anti_repetition.conversation_contexts.clear()
        advanced_anti_repetition.user_patterns.clear()
        advanced_anti_repetition.signature_cache.clear()

    def test_signature_creation(self):
        """Test response signature creation and caching."""
        content = "Hello world, this is a test response."
        signature1 = advanced_anti_repetition._create_signature(content)
        signature2 = advanced_anti_repetition._create_signature(content)

        # Same content should produce same signature
        self.assertEqual(signature1.content_hash, signature2.content_hash)

        # Should be cached
        self.assertIn(signature1.content_hash, advanced_anti_repetition.signature_cache)

    def test_exact_duplicate_detection(self):
        """Test exact duplicate detection."""
        user_id = "test_user_123"
        content = "This is a unique response."

        # First response should not be flagged
        should_enhance, reason, _ = advanced_anti_repetition.should_enhance_response(user_id, content)
        self.assertFalse(should_enhance)

        # Record the response
        advanced_anti_repetition.record_response(user_id, content)

        # Second identical response should be flagged
        should_enhance, reason, _ = advanced_anti_repetition.should_enhance_response(user_id, content)
        self.assertTrue(should_enhance)
        self.assertIn("exact content repetition", reason.lower())

    def test_semantic_similarity_detection(self):
        """Test semantic similarity detection."""
        user_id = "test_user_456"
        response1 = "The weather is really nice today."
        response2 = "Weather is quite nice today."

        # Record first response
        advanced_anti_repetition.record_response(user_id, response1)

        # Similar response should be flagged
        should_enhance, reason, _ = advanced_anti_repetition.should_enhance_response(user_id, response2)
        self.assertTrue(should_enhance)
        self.assertIn("semantic similarity", reason.lower())

    def test_conversation_context_tracking(self):
        """Test conversation context tracking."""
        user_id = "test_user_789"
        content = "I love this amazing product, it's great!"

        # Record response
        advanced_anti_repetition.record_response(user_id, content)

        # Check context was updated
        context = advanced_anti_repetition.conversation_contexts.get(user_id)
        self.assertIsNotNone(context)
        self.assertEqual(context.sentiment, "positive")
        self.assertGreater(context.complexity, 0)

    def test_adaptive_thresholds(self):
        """Test adaptive threshold calculation."""
        user_id = "test_user_adaptive"

        # Initial threshold should be base value
        threshold = advanced_anti_repetition._get_adaptive_threshold(user_id)
        self.assertEqual(threshold, advanced_anti_repetition.base_similarity_threshold)

        # Simulate frequent interactions
        patterns = advanced_anti_repetition.user_patterns[user_id]
        patterns['interaction_frequency'] = 0.2
        patterns['preferred_vocabulary'].update(['complex', 'sophisticated', 'elaborate'] * 20)

        # Threshold should increase
        threshold = advanced_anti_repetition._get_adaptive_threshold(user_id)
        self.assertGreater(threshold, advanced_anti_repetition.base_similarity_threshold)

    def test_system_prompt_enhancement(self):
        """Test system prompt enhancement."""
        user_id = "test_user_prompt"
        base_prompt = "You are a helpful assistant."

        # No context should return base prompt
        enhanced = advanced_anti_repetition.enhance_system_prompt_context(user_id, base_prompt)
        self.assertEqual(enhanced, base_prompt)

        # Add some interaction history
        advanced_anti_repetition.record_response(user_id, "This is a response about technology and innovation.")
        advanced_anti_repetition.record_response(user_id, "Another response about machine learning and AI.")

        # Should enhance prompt
        enhanced = advanced_anti_repetition.enhance_system_prompt_context(user_id, base_prompt)
        self.assertNotEqual(enhanced, base_prompt)
        self.assertIn("Internal Guidance", enhanced)

    def test_performance_optimization(self):
        """Test performance optimizations."""
        user_id = "perf_test_user"

        # Add many responses to test cleanup
        for i in range(20):
            content = f"This is response number {i} with unique content."
            advanced_anti_repetition.record_response(user_id, content)

        # Check that cleanup maintains reasonable size
        signatures = advanced_anti_repetition.user_signatures[user_id]
        self.assertLessEqual(len(signatures), 7)  # maxlen is 7

    def test_user_insights(self):
        """Test user insights generation."""
        user_id = "insights_test_user"

        # Add varied responses
        responses = [
            "I love this product!",
            "The technology is amazing.",
            "Machine learning fascinates me.",
            "This innovation is incredible."
        ]

        for response in responses:
            advanced_anti_repetition.record_response(user_id, response)

        insights = advanced_anti_repetition.get_user_insights(user_id)

        self.assertEqual(insights['total_responses'], 4)
        self.assertGreater(insights['vocabulary_diversity'], 5)
        self.assertEqual(insights['current_sentiment'], 'positive')
        self.assertGreater(insights['conversation_complexity'], 0)

    def test_short_response_skip(self):
        """Test that very short responses are skipped."""
        user_id = "short_test_user"
        short_content = "Ok"

        # Short response should not be flagged
        should_enhance, reason, _ = advanced_anti_repetition.should_enhance_response(user_id, short_content)
        self.assertFalse(should_enhance)

    def test_conceptual_repetition(self):
        """Test conceptual repetition detection."""
        user_id = "concept_test_user"

        # Record responses about the same topic
        responses = [
            "The weather is sunny and warm today.",
            "Today's weather is bright and sunny.",
            "It's a sunny day with pleasant weather."
        ]

        for response in responses:
            advanced_anti_repetition.record_response(user_id, response)

        # Similar conceptual response should be flagged
        test_response = "The weather is sunny and bright."
        should_enhance, reason, _ = advanced_anti_repetition.should_enhance_response(user_id, test_response)
        self.assertTrue(should_enhance)
        self.assertIn("conceptual repetition", reason.lower())


class TestAntiRepetitionIntegrator(unittest.TestCase):
    """Test the anti-repetition integrator."""

    def setUp(self):
        """Set up test environment."""
        anti_repetition_integrator.legacy_mode = False

    def test_integration_should_enhance(self):
        """Test integrator's should_enhance method."""
        user_id = "integration_test_user"
        content = "This is a test response."

        # First response should not need enhancement
        should_enhance, reason = anti_repetition_integrator.should_enhance_response(user_id, content)
        self.assertFalse(should_enhance)

        # Record response
        anti_repetition_integrator.record_response(user_id, content)

        # Duplicate should need enhancement
        should_enhance, reason = anti_repetition_integrator.should_enhance_response(user_id, content)
        self.assertTrue(should_enhance)

    def test_system_prompt_integration(self):
        """Test system prompt enhancement through integrator."""
        user_id = "prompt_integration_user"
        base_prompt = "You are Jakey, a Discord bot."

        # Without history, should return base prompt
        enhanced = anti_repetition_integrator.get_enhanced_system_prompt(user_id, base_prompt)
        self.assertEqual(enhanced, base_prompt)

        # Add some history
        anti_repetition_integrator.record_response(user_id, "I love talking about cryptocurrency!")

        # Should enhance prompt
        enhanced = anti_repetition_integrator.get_enhanced_system_prompt(user_id, base_prompt)
        self.assertNotEqual(enhanced, base_prompt)
        self.assertIn("Internal Guidance", enhanced)

    def test_legacy_mode_toggle(self):
        """Test legacy mode toggle functionality."""
        # Should start in advanced mode
        self.assertFalse(anti_repetition_integrator.legacy_mode)

        # Toggle to legacy mode
        anti_repetition_integrator.toggle_legacy_mode(True)
        self.assertTrue(anti_repetition_integrator.legacy_mode)

        # Toggle back to advanced
        anti_repetition_integrator.toggle_legacy_mode(False)
        self.assertFalse(anti_repetition_integrator.legacy_mode)

    def test_user_analytics(self):
        """Test user analytics through integrator."""
        user_id = "analytics_test_user"

        # Add some interactions
        for i in range(5):
            anti_repetition_integrator.record_response(user_id, f"Response {i} about AI and technology.")

        analytics = anti_repetition_integrator.get_user_analytics(user_id)

        self.assertIn('total_responses', analytics)
        self.assertIn('vocabulary_diversity', analytics)
        self.assertEqual(analytics['total_responses'], 5)


if __name__ == '__main__':
    unittest.main()