# services/llm_service.py - FIXED VERSION
import logging
import google.generativeai as genai  # CORRECTED IMPORT

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Gemini API key is required")
        
        # Configure the API key
        genai.configure(api_key=api_key)
        
        # Initialize the model - USING GEMINI 2.5 AS IN YOUR ORIGINAL CODE
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info("LLM Service initialized with Gemini 2.5 Flash")
    
    def generate_response(self, prompt: str) -> str:
        """Generate response using Gemini LLM."""
        try:
            response = self.model.generate_content(prompt)
            text = response.text if hasattr(response, 'text') else str(response)
            return text.strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise