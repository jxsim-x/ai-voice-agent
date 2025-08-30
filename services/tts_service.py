import logging
import requests
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Murf API key is required")
        
        self.api_key = api_key
        self.base_url = "https://api.murf.ai/v1/speech/generate"
        self.max_chars = 3000
        logger.info("TTS Service initialized with Murf")
    
    def generate_audio(self, text: str, voice_id: str = "en-US-natalie", 
                      format: str = "mp3") -> Tuple[str, Dict[str, Any]]:
        """Generate audio URL from text using Murf TTS."""
        if not text:
            raise ValueError("Empty text provided for TTS")
        
        # Truncate if too long
        text_for_tts = text if len(text) <= self.max_chars else text[:self.max_chars]
        
        payload = {
            "voiceId": voice_id,
            "text": text_for_tts,
            "format": format
        }
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.base_url, 
                json=payload, 
                headers=headers, 
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            audio_url = data.get("audioFile")
            
            if not audio_url:
                raise ValueError("No audio URL returned from Murf API")
            
            logger.info("TTS generation successful")
            return audio_url, data
            
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise
