"""Async Pollinations API wrapper maintaining backward compatibility"""
from ai.clients.async_client import AsyncPollinationsClient
from ai.models.text_models import TextGenerationRequest, Message
from ai.models.image_models import ImageGenerationRequest

# Create a global instance
async_pollinations_api = AsyncPollinationsClient()


class PollinationsAsyncAPI:
    def __init__(self):
        self.client = async_pollinations_api

    async def generate_text(self, messages=None, model=None, temperature=0.7,
                          max_tokens=500, tools=None, tool_choice="auto"):
        """
        Generate text using Pollinations API with OpenAI-compatible format (async version)
        """
        # Handle case where messages is None
        if messages is None:
            messages = []
        
        # Ensure messages is always a list
        if not isinstance(messages, list):
            messages = []
            
        # Convert to Pydantic models
        pydantic_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                pydantic_messages.append(Message(role=msg.get('role', 'user'), content=msg.get('content', '')))
            else:
                pydantic_messages.append(msg)
        
        request = TextGenerationRequest(
            messages=pydantic_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice
        )
        
        response = await self.client.generate_text(request)
        if response.error:
            return {"error": response.error}
        else:
            return {
                "content": response.content,
                "model": response.model,
                "usage": response.usage
            }

    async def generate_image(self, prompt, model="flux", width=1024, height=1024,
                           seed=None, nologo=True, private=True):
        """
        Generate an uncensored image with automatic system prompt enhancement and return the image URL (async version)
        Images are marked as private by default to prevent public feed appearance
        """
        request = ImageGenerationRequest(
            prompt=prompt,
            model=model,
            width=width,
            height=height,
            seed=seed,
            nologo=nologo,
            private=private
        )
        
        return self.client.generate_image_url(request)

    async def list_text_models(self):
        """List available text models (async version)"""
        return await self.client.list_text_models()

    async def list_image_models(self):
        """List available image models (async version)"""
        return await self.client.list_image_models()


# Global API instance for backward compatibility
pollinations_async_api = PollinationsAsyncAPI()
