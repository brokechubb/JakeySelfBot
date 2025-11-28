"""Test backward compatibility of enhanced pollinations implementation"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.pollinations import pollinations_api


def test_basic_text_generation():
    """Test basic text generation (backward compatibility)"""
    print("Testing basic text generation...")
    
    messages = [
        {"role": "user", "content": "What is 2+2?"}
    ]
    
    response = pollinations_api.generate_text(messages=messages)
    print(f"Response: {response}")
    
    # Even if there's an API error, the function should still return a dict with error key
    if isinstance(response, dict):
        print("Success: Basic text generation interface works")
        return True
    else:
        print("Error: Basic text generation interface broken")
        return False


def test_basic_image_generation():
    """Test basic image generation (backward compatibility)"""
    print("Testing basic image generation...")
    
    url = pollinations_api.generate_image("A cat")
    print(f"Image URL: {url}")
    
    if url and isinstance(url, str):
        print("Success: Basic image generation interface works")
        return True
    else:
        print("Error: Basic image generation interface broken")
        return False


def test_model_listing():
    """Test model listing (backward compatibility)"""
    print("Testing model listing...")
    
    text_models = pollinations_api.list_text_models()
    image_models = pollinations_api.list_image_models()
    
    print(f"Text models: {text_models}")
    print(f"Image models: {image_models}")
    
    # Should return lists (even if empty due to API issues)
    if isinstance(text_models, list) and isinstance(image_models, list):
        print("Success: Model listing interface works")
        return True
    else:
        print("Error: Model listing interface broken")
        return False


def main():
    """Run backward compatibility tests"""
    print("Running backward compatibility tests...")
    
    try:
        text_success = test_basic_text_generation()
        image_success = test_basic_image_generation()
        model_success = test_model_listing()
        
        if text_success and image_success and model_success:
            print("All backward compatibility tests passed!")
            return True
        else:
            print("Some backward compatibility tests failed!")
            return False
    except Exception as e:
        print(f"Test failed with exception: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)