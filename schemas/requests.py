from pydantic import BaseModel, Field

class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to convert to speech")
    voiceId: str = Field("en-US-natalie", description="Voice ID for TTS")
