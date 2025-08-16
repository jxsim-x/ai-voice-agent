import logging
import assemblyai as aai

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("AssemblyAI API key is required")
        
        aai.settings.api_key = api_key
        self.transcriber = aai.Transcriber()
        logger.info("STT Service initialized with AssemblyAI")
    
    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text."""
        try:
            transcript = self.transcriber.transcribe(audio_bytes)
            text = getattr(transcript, "text", None) or str(transcript)
            return text.strip()
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

