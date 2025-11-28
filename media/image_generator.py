import urllib.parse
from typing import Optional
import importlib

# Dynamically import the arta API
try:
    arta_module = importlib.import_module('ai.arta')
    arta_api = getattr(arta_module, 'arta_api', None)
except ImportError:
    arta_api = None

class ImageGenerator:
    def __init__(self):
        self.api = arta_api
     
    def generate_image(self, prompt: str, model: str = "SDXL 1.0", width: int = 1024, height: int = 1024, 
                      seed: Optional[int] = None, nologo: bool = True) -> str:
        """
        Generate an image using Arta API and return the image URL
        Note: width/height parameters are converted to aspect ratios for Arta
        Falls back to Pollinations API if Arta fails
        """
        # Try Arta API first
        if self.api is not None:
            result = self._generate_with_arta(prompt, model, width, height)
            if not result.startswith("Error:"):
                return result
            # If Arta fails, fall back to Pollinations (continue to the code below)
            print(f"Arta API failed: {result}, falling back to Pollinations")
        
        # Fallback to Pollinations API
        return self._generate_with_pollinations(prompt, model, width, height, seed, nologo)
     
    def _generate_with_arta(self, prompt: str, model: str, width: int, height: int) -> str:
        """Generate image using Arta API"""
        try:
            # Convert width/height to aspect ratio
            ratio = self._convert_dimensions_to_ratio(width, height)
            
            # Convert model parameter to style (for backward compatibility)
            if self.api is not None and hasattr(self.api, 'get_available_styles'):
                available_styles = self.api.get_available_styles()
                style = model if model in available_styles else "SDXL 1.0"
            else:
                style = "SDXL 1.0"
            
            # Generate the image
            if self.api is not None and hasattr(self.api, 'generate_image'):
                image_url = self.api.generate_image(
                    prompt=prompt,
                    style=style,
                    ratio=ratio
                )
                return image_url if image_url else "Error: Failed to generate image - API returned no URL"
            else:
                return "Error: Arta API generate_image method not available"
        except Exception as e:
            return f"Error: Failed to generate image with Arta - {str(e)}"
     
    def _generate_with_pollinations(self, prompt: str, model: str, width: int, height: int, 
                                  seed: Optional[int], nologo: bool) -> str:
        """Generate image using Pollinations API as fallback"""
        try:
            # Import pollinations API
            from ai.pollinations import pollinations_api
            
            # Generate the image using Pollinations
            image_url = pollinations_api.generate_image(
                prompt=prompt,
                model=model,
                width=width,
                height=height,
                seed=seed,
                nologo=nologo
            )
            return image_url
        except Exception as e:
            return f"Error: Failed to generate image with Pollinations - {str(e)}"
     
    def _convert_dimensions_to_ratio(self, width: int, height: int) -> str:
        """Convert width/height dimensions to aspect ratio string"""
        # Calculate the greatest common divisor to simplify the ratio
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a
        
        # Simplify the ratio
        divisor = gcd(width, height)
        simplified_width = width // divisor
        simplified_height = height // divisor
        
        # Format as string
        ratio = f"{simplified_width}:{simplified_height}"
        
        # Check if it's one of the supported ratios, otherwise use default
        if self.api is not None and hasattr(self.api, 'get_available_ratios'):
            supported_ratios = self.api.get_available_ratios()
            if ratio in supported_ratios:
                return ratio
        
        return "1:1"  # Default fallback
    
    def get_available_models(self) -> list:
        """Get list of available image styles (backward compatibility)"""
        # Try to get from Arta first
        if self.api is not None:
            if hasattr(self.api, 'get_available_styles'):
                return self.api.get_available_styles()
        
        # Fallback to Pollinations models
        try:
            from ai.pollinations import pollinations_api
            return pollinations_api.list_image_models()
        except:
            return []

# Global image generator instance
image_generator = ImageGenerator()