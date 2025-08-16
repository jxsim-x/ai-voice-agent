from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class AudioGenerationResponse(BaseModel):
    audio_url: str
    raw: Optional[Dict[str, Any]] = None

class UploadResponse(BaseModel):
    filename: str
    content_type: Optional[str] = None
    size: int

class EchoResponse(BaseModel):
    transcription: str
    audio_url: str
    raw_murf: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    transcription: str
    text: str
    audio_url: str
    history: Optional[List[Dict[str, str]]] = None
    error: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
