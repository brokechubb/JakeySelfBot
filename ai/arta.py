import re
import time
from typing import List, Optional

import requests

from utils.logging_config import get_logger

logger = get_logger(__name__)


class ArtaAPI:
    def __init__(self):
        self.base_url = "https://img-gen-prod.ai-arta.com/api/v1"
        self.auth_url = (
            "https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser"
        )
        from config import ARTA_API_KEY

        self.api_key = ARTA_API_KEY

        # Available styles from the arta.go file
        self.styles = [
            "Medieval",
            "Vincent Van Gogh",
            "F Dev",
            "Low Poly",
            "Dreamshaper-xl",
            "Anima-pencil-xl",
            "Biomech",
            "Trash Polka",
            "No Style",
            "Cheyenne-xl",
            "Chicano",
            "Embroidery tattoo",
            "Red and Black",
            "Fantasy Art",
            "Watercolor",
            "Dotwork",
            "Old school colored",
            "Realistic tattoo",
            "Japanese_2",
            "Realistic-stock-xl",
            "F Pro",
            "RevAnimated",
            "Katayama-mix-xl",
            "SDXL L",
            "Cor-epica-xl",
            "Anime tattoo",
            "New School",
            "Death metal",
            "Old School",
            "Juggernaut-xl",
            "Photographic",
            "SDXL 1.0",
            "Graffiti",
            "Mini tattoo",
            "Surrealism",
            "Neo-traditional",
            "On limbs black",
            "Yamers-realistic-xl",
            "Pony-xl",
            "Playground-xl",
            "Anything-xl",
            "Flame design",
            "Kawaii",
            "Cinematic Art",
            "Professional",
            "Flux",
            "Black Ink",
            "Epicrealism-xl",
            "High GPT4o",
        ]

        # Available ratios from the arta.go file
        self.ratios = [
            "1:1",
            "2:3",
            "3:2",
            "3:4",
            "4:3",
            "9:16",
            "16:9",
            "9:21",
            "21:9",
        ]

    def generate_auth_token(self) -> Optional[str]:
        """
        Generate an authentication token using Firebase
        """
        try:
            url = f"{self.auth_url}?key={self.api_key}"
            headers = {
                "X-Android-Cert": "ADC09FCA89A2CE4D0D139031A2A587FA87EE4155",
                "X-Firebase-Gmpid": "1:713239656559:android:f9e37753e9ee7324cb759a",
                "X-Firebase-Client": "H4sIAAAAAAAA_6tWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
                "X-Client-Version": "Android/Fallback/X22003001/FirebaseCore-Android",
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 15;)",
                "X-Android-Package": "ai.generated.art.maker.image.picture.photo.generator.painting",
                "Content-Type": "application/json",
            }

            payload = {"clientType": "CLIENT_TYPE_ANDROID"}

            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()

            data = response.json()
            return data.get("idToken")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating auth token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating auth token: {e}")
            return None

    def generate_image(
        self,
        prompt: str,
        style: str = "SDXL 1.0",
        ratio: str = "1:1",
        negative_prompt: str = "",
        count: str = "1",
        steps: str = "40",
    ) -> Optional[str]:
        """
        Generate an image using Arta API and return the image URL
        """
        try:
            # Sanitize prompt to remove special characters that might cause API errors
            # More comprehensive sanitization that preserves common punctuation but removes problematic characters
            sanitized_prompt = re.sub(
                r"[\x00-\x1f\x7f-\x9f]", "", prompt
            )  # Remove control characters
            sanitized_prompt = re.sub(
                r"[^\w\s.,!?\'\"@#\$%\^&*()\[\]{}\-:;/\\]", " ", sanitized_prompt
            )  # Keep common chars
            sanitized_prompt = re.sub(
                r"\s+", " ", sanitized_prompt
            ).strip()  # Normalize whitespace

            if sanitized_prompt != prompt:
                logger.info(f"Sanitized prompt: '{prompt}' -> '{sanitized_prompt}'")

            # Generate auth token
            token = self.generate_auth_token()
            if not token:
                logger.error("Failed to generate authentication token")
                return None

            # Validate style
            if style not in self.styles:
                logger.warning(f"Invalid style '{style}', using default 'SDXL 1.0'")
                style = "SDXL 1.0"

            # Validate ratio
            if ratio not in self.ratios:
                logger.warning(f"Invalid ratio '{ratio}', using default '1:1'")
                ratio = "1:1"

            # Prepare the image generation request
            url = f"{self.base_url}/text2image"
            headers = {
                "Authorization": token,
                "User-Agent": "AiArt/4.18.6 okHttp/4.12.0 Android R",
            }

            # Prepare form data as a dictionary (requests will handle multipart encoding)
            data = {
                "prompt": sanitized_prompt,
                "negative_prompt": negative_prompt,
                "style": style,
                "images_num": count,
                "cfg_scale": "7",
                "steps": steps,
                "aspect_ratio": ratio,
            }

            # Make the initial request to start image generation
            response = requests.post(url, headers=headers, data=data, timeout=30)
            response.raise_for_status()

            status_data = response.json()
            record_id = status_data.get("record_id")

            if not record_id:
                logger.error("Failed to get record_id from image generation request")
                return None

            # Poll for image generation status
            image_url = self._poll_for_image(record_id, token)
            return image_url

        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating image: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating image: {e}")
            return None

    def _poll_for_image(self, record_id: str, token: str) -> Optional[str]:
        """
        Poll for image generation status and return the image URL when ready
        """
        url = f"{self.base_url}/text2image/{record_id}/status"
        headers = {
            "Authorization": token,
            "User-Agent": "AiArt/3.23.12 okHttp/4.12.0 Android VANILLA_ICE_CREAM",
        }

        # Poll for up to 5 minutes (300 seconds)
        max_wait_time = 300
        poll_interval = 5
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()

                status_data = response.json()
                status = status_data.get("status", "").upper()

                if status == "DONE":
                    # Image generation complete, return the first image URL
                    images = status_data.get("response", [])
                    if images:
                        return images[0].get("url")
                    else:
                        logger.error("No images found in response")
                        return None

                elif status in ["FAILED", "ERROR"]:
                    # Image generation failed
                    error_details = status_data.get("detail", [])
                    if error_details:
                        error_msg = error_details[0].get("msg", "Unknown error")
                        logger.error(f"Image generation failed: {error_msg}")
                    else:
                        logger.error("Image generation failed with no details")
                    return None

                elif status in ["QUEUED", "PROCESSING", "IN_QUEUE", "IN_PROGRESS"]:
                    # Still processing, wait and poll again
                    logger.info(f"Image generation status: {status}, waiting...")
                    time.sleep(poll_interval)
                    continue

                else:
                    # Unknown status
                    logger.warning(f"Unknown image generation status: {status}")
                    time.sleep(poll_interval)
                    continue

            except requests.exceptions.RequestException as e:
                logger.error(f"Error polling for image status: {e}")
                time.sleep(poll_interval)
                continue
            except Exception as e:
                logger.error(f"Unexpected error polling for image status: {e}")
                time.sleep(poll_interval)
                continue

        # Timeout reached
        logger.error("Image generation timed out")
        return None

    def get_available_styles(self) -> List[str]:
        """Get list of available artistic styles"""
        return self.styles.copy()

    def get_available_ratios(self) -> List[str]:
        """Get list of available aspect ratios"""
        return self.ratios.copy()


# Global Arta API instance
arta_api = ArtaAPI()
