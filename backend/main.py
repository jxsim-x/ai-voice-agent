# main.py - Optimized and refactored
import os
import uuid
import logging
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from services.stt_service import STTService
from services.llm_service import LLMService  
from services.tts_service import TTSService
from services.audio_service import AudioService
from schemas.requests import TTSRequest
from schemas.responses import (
    AudioGenerationResponse,
    UploadResponse,
    EchoResponse,
    ChatResponse,
    ErrorResponse
)
from utils.logging_config import setup_logging
from utils.cleanup import cleanup_files

# ---- Configuration ----
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# ---- Initialize Services ----
try:
    stt_service = STTService(os.getenv("ASSEMBLYAI_API_KEY"))
    llm_service = LLMService(os.getenv("GEMINI_API_KEY"))
    tts_service = TTSService(os.getenv("MURF_API_KEY"))
    audio_service = AudioService()
    logger.info("All services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise

# ---- FastAPI App Setup ----
app = FastAPI(title="Voice Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Constants ----
UPLOAD_DIR = Path("uploads")
TMP_DIR = Path("tmp")
UPLOAD_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)

# Simple in-memory store for chat history
chat_histories: Dict[str, List[Dict[str, str]]] = {}

# ---- API Endpoints ----

@app.post("/generate-audio", response_model=AudioGenerationResponse)
async def generate_audio(req: TTSRequest):
    """Generate audio from text using Murf TTS."""
    try:
        logger.info(f"Generating audio for text: {req.text[:50]}...")
        audio_url, raw_data = tts_service.generate_audio(req.text, req.voiceId)
        
        logger.info("Audio generation successful")
        return AudioGenerationResponse(audio_url=audio_url, raw=raw_data)
        
    except Exception as e:
        logger.error(f"Audio generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-audio", response_model=UploadResponse)
async def upload_audio(file: UploadFile = File(...)):
    """Save uploaded audio file for debugging purposes."""
    try:
        uid = uuid.uuid4().hex
        dest = UPLOAD_DIR / f"{uid}_{file.filename}"
        contents = await file.read()
        dest.write_bytes(contents)
        
        logger.info(f"Audio file uploaded: {dest.name}, size: {len(contents)} bytes")
        return UploadResponse(
            filename=dest.name,
            content_type=file.content_type,
            size=len(contents)
        )
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts/echo", response_model=EchoResponse)
async def tts_echo(file: UploadFile = File(...)):
    """Transcribe uploaded audio and return Murf TTS of the transcription."""
    uid = uuid.uuid4().hex
    temp_files = []
    
    try:
        logger.info("Processing echo request")
        
        # Save and convert audio
        in_path, wav_path = await _save_and_convert_audio(file, uid, temp_files)
        
        # Transcribe audio
        transcription = await _transcribe_audio(wav_path)
        
        # Generate TTS audio
        audio_url, raw_data = tts_service.generate_audio(transcription)
        
        logger.info("Echo processing completed successfully")
        return EchoResponse(
            transcription=transcription,
            audio_url=audio_url,
            raw_murf=raw_data
        )
        
    except Exception as e:
        logger.error(f"Echo processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        cleanup_files(*temp_files)


@app.post("/llm/query", response_model=ChatResponse)
async def llm_query(file: UploadFile = File(...)):
    """Process audio through STT -> LLM -> TTS pipeline."""
    logger.info("Processing LLM query request")
    return await _process_chat_request(file, session_id=None)


@app.post("/agent/chat/{session_id}", response_model=ChatResponse)
async def chat_with_agent(session_id: str, file: UploadFile = File(...)):
    """Process audio chat with conversation history."""
    logger.info(f"Processing chat request for session: {session_id}")
    return await _process_chat_request(file, session_id)


# ---- Helper Functions ----

async def _save_and_convert_audio(file: UploadFile, uid: str, temp_files: List[Path]):
    """Save uploaded file and convert to WAV format."""
    in_path = TMP_DIR / f"{uid}_{file.filename}"
    wav_path = TMP_DIR / f"{uid}.wav"
    temp_files.extend([in_path, wav_path])
    
    # Save uploaded file
    content = await file.read()
    in_path.write_bytes(content)
    logger.debug(f"Saved uploaded file: {in_path}")
    
    # Convert to WAV
    audio_service.convert_to_wav(in_path, wav_path)
    logger.debug(f"Converted to WAV: {wav_path}")
    
    return in_path, wav_path


async def _transcribe_audio(wav_path: Path) -> str:
    """Transcribe audio file using STT service."""
    with open(wav_path, "rb") as fh:
        audio_bytes = fh.read()
    
    transcription = stt_service.transcribe(audio_bytes)
    logger.info(f"Transcription result: {transcription}")
    return transcription


async def _process_chat_request(file: UploadFile, session_id: str = None) -> ChatResponse:
    """Process chat request through the full STT -> LLM -> TTS pipeline."""
    uid = uuid.uuid4().hex
    temp_files = []
    fallback_audio = "/fallback.mp3"
    
    try:
        # Save and convert audio
        try:
            in_path, wav_path = await _save_and_convert_audio(file, uid, temp_files)
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return ChatResponse(
                transcription="",
                text="I'm having trouble connecting right now.",
                audio_url=fallback_audio,
                error="convert_failed"
            )
        
        # Transcribe audio
        try:
            user_text = await _transcribe_audio(wav_path)
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ChatResponse(
                transcription="",
                text="I'm having trouble connecting right now.",
                audio_url=fallback_audio,
                error="stt_failed"
            )
        
        # Process with LLM
        try:
            if session_id:
                assistant_text = await _process_chat_with_history(user_text, session_id)
            else:
                assistant_text = llm_service.generate_response(user_text)
                
            logger.info(f"LLM response: {assistant_text}")
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            return ChatResponse(
                transcription=user_text,
                text="I'm having trouble connecting right now.",
                audio_url=fallback_audio,
                error="llm_failed"
            )
        
        # Generate TTS audio
        try:
            audio_url, _ = tts_service.generate_audio(assistant_text)
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return ChatResponse(
                transcription=user_text,
                text=assistant_text,
                audio_url=fallback_audio,
                error="tts_failed"
            )
        
        # Return successful response
        response = ChatResponse(
            transcription=user_text,
            text=assistant_text,
            audio_url=audio_url
        )
        
        if session_id:
            response.history = chat_histories.get(session_id, [])
            
        return response
        
    finally:
        cleanup_files(*temp_files)


async def _process_chat_with_history(user_text: str, session_id: str) -> str:
    """Process chat with conversation history."""
    # Get or create history
    history = chat_histories.setdefault(session_id, [])
    
    # Add user message
    history.append({"role": "user", "text": user_text})
    
    # Build conversation context
    conversation = "\n".join([
        f"{msg['role'].capitalize()}: {msg['text']}" 
        for msg in history
    ]) + "\nAssistant:"
    
    # Generate response
    assistant_text = llm_service.generate_response(conversation)
    
    # Save assistant response
    history.append({"role": "assistant", "text": assistant_text})
    chat_histories[session_id] = history
    
    return assistant_text


# ---- Static Files ----
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
