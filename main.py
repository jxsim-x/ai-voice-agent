import uuid 

import os
import sys
import time
import random
import json
from pathlib import Path
from typing import Dict, List
import asyncio

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv



from services.stt_service import STTService, StreamingTranscriptionManager
from services.llm_service import LLMService  
from services.tts_service import TTSService
from services.audio_service import AudioService
from services.murf_websocket_service import MurfWebSocketService  # 🎵 NEW: Day 20
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
from fastapi.responses import FileResponse

# CRITICAL FIX: Force UTF-8 encoding for Windows console
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')
        print("[SUCCESS] UTF-8 encoding enabled")
    except Exception as e:
        print(f"[WARNING] UTF-8 setup failed: {e}")

import uuid
import logging

# ---- Emoji Replacement for Safe Logging ----
def make_log_safe(message: str) -> str:
    """Replace emojis with text alternatives for safe console logging"""
    emoji_replacements = {
        "🎤": "[MIC]",
        "🎯": "[TARGET]", 
        "✅": "[SUCCESS]",
        "🔴": "[RECORDING]",
        "⏹️": "[STOP]",
        "🎙️": "[MICROPHONE]",
        "📡": "[STREAMING]",
        "🎵": "[AUDIO]",
        "🖥️": "[CONSOLE]",
        "🎉": "[CELEBRATION]",
        "❌": "[ERROR]",
        "⚠️": "[WARNING]",
        "📌": "[PIN]",
        "🔌": "[CONNECT]",
        "📨": "[MESSAGE]",
        "📊": "[DATA]",
        "🚀": "[LAUNCH]",
        "💡": "[IDEA]",
        "🛠️": "[TOOLS]",
        "⚡": "[POWER]",
        "🌟": "[STAR]"
    }
    
    for emoji, replacement in emoji_replacements.items():
        message = message.replace(emoji, replacement)
    return message

# ---- Configuration ----
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# PRODUCTION: Get port from environment (Render sets this automatically)
PORT = int(os.getenv("PORT", 8000))


# ---- Initialize Services ----
try:
    stt_service = STTService(os.getenv("ASSEMBLYAI_API_KEY"))
    llm_service = LLMService(os.getenv("GEMINI_API_KEY"), os.getenv("WEATHER_API_KEY"))
    tts_service = TTSService(os.getenv("MURF_API_KEY"))
    audio_service = AudioService()
    
    # 🎵 NEW: Day 20 - Initialize Murf WebSocket service
    murf_websocket_service = MurfWebSocketService(os.getenv("MURF_API_KEY"))
    
    # ENHANCED: Initialize streaming transcription manager with Murf service
    streaming_manager = StreamingTranscriptionManager(stt_service, llm_service, murf_websocket_service)
    
    logger.info(make_log_safe("✅ All services initialized successfully (including Murf WebSocket)"))
except Exception as e:
    logger.error(make_log_safe(f"❌ Failed to initialize services: {e}"))
    raise



# ---- FastAPI App Setup ----
app = FastAPI(
    title="Zody Voice Agent API", 
    version="1.0.0",
    description="30 Days of AI Voice Agents - Zody Deployment"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# ===== Serve Frontend Files =====
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
frontend_dir = os.path.abspath(frontend_dir)

if not os.path.exists(frontend_dir):
    raise RuntimeError(f"Frontend directory not found: {frontend_dir}")

app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
# Serve index.html at root

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Zody Voice Agent"}

# Root endpoint
#@app.get("/")
#async def root():
 #   return {"message": "Zody Voice Agent is running!", "status": "active"}

# 🎵 NEW: Day 20 - Startup event to connect Murf WebSocket
@app.on_event("startup")
async def startup_event():
    """Initialize Murf WebSocket connection on server startup"""
    try:
        logger.info("Connecting to Murf WebSocket on startup...")
        success = await murf_websocket_service.connect()
        if success:
            logger.info(make_log_safe("🎵 Murf WebSocket connected successfully on startup"))
        else:
            logger.warning("Failed to connect to Murf WebSocket on startup - will retry on first use")
    except Exception as e:
        logger.error(f"Error connecting Murf WebSocket on startup: {e}")
        # Don't crash the server if Murf fails to connect
        logger.info("Server starting without Murf WebSocket - will attempt to connect on demand")
# 🎵 NEW: Day 20 - Cleanup event to close Murf WebSocket
@app.on_event("shutdown")
async def shutdown_event():
    """Close Murf WebSocket connection on server shutdown"""
    try:
        logger.info("Closing Murf WebSocket connection...")
        await murf_websocket_service.close()
        logger.info(make_log_safe("🎵 Murf WebSocket closed successfully"))
    except Exception as e:
        logger.error(f"Error closing Murf WebSocket: {e}")

        

# ---- Constants ----
UPLOAD_DIR = Path("uploads")
TMP_DIR = Path("tmp")
STREAMING_DIR = Path("streaming")
UPLOAD_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)
STREAMING_DIR.mkdir(exist_ok=True)

# Simple in-memory store for chat history
chat_histories: Dict[str, List[Dict[str, str]]] = {}

# ---- Enhanced WebSocket Connection Manager ----
class ConnectionManager:
    """Manages WebSocket connections and streaming sessions"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.streaming_sessions: Dict[str, Dict] = {}
        # NEW: Track transcription sessions
        self.transcription_sessions: Dict[str, str] = {}  # websocket -> session_id mapping
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(make_log_safe(f"🔌 WebSocket connected. Total: {len(self.active_connections)}"))
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection and clean up sessions"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Clean up streaming sessions
        sessions_to_remove = []
        for session_id, session_data in self.streaming_sessions.items():
            if session_data.get('websocket') == websocket:
                if 'audio_file' in session_data and session_data['audio_file']:
                    session_data['audio_file'].close()
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.streaming_sessions[session_id]
        
        # NEW: Clean up transcription sessions
        if websocket in self.transcription_sessions:
            transcription_session_id = self.transcription_sessions[websocket]
            streaming_manager.end_session(transcription_session_id)
            del self.transcription_sessions[websocket]
            logger.info(make_log_safe(f"🔴 Cleaned up transcription session: {transcription_session_id[:8]}"))
        
        logger.info(make_log_safe(f"❌ WebSocket disconnected. Total: {len(self.active_connections)}"))
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection with connection state check"""
        try:
            # Check if websocket is still in active connections
            if websocket in self.active_connections:
                await websocket.send_text(message)
            else:
                logger.warning("Attempted to send message to disconnected websocket")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            # Remove from active connections if sending fails
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
    
    def is_websocket_active(self, websocket: WebSocket) -> bool:
        """Check if websocket is still active - ENHANCED"""
        try:
            # Check if in active connections list
            if websocket not in self.active_connections:
                return False
                
            # Check WebSocket client state if available
            if hasattr(websocket, 'client_state'):
                from starlette.websockets import WebSocketState
                return websocket.client_state == WebSocketState.CONNECTED
            
            # Fallback: assume active if in connections list
            return True
            
        except Exception as e:
            logger.error(f"Error checking websocket state: {e}")
            return False
    
    # Audio streaming session management (preserved from Day 16)
    def start_streaming_session(self, websocket: WebSocket) -> str:
        """Start a new audio streaming session"""
        session_id = uuid.uuid4().hex
        timestamp = uuid.uuid4().hex[:8]
        audio_filename = f"streamed_audio_{timestamp}_{session_id[:8]}.wav"
        audio_path = STREAMING_DIR / audio_filename
        
        session_data = {
            'websocket': websocket,
            'session_id': session_id,
            'audio_path': audio_path,
            'audio_file': None,
            'chunks_received': 0,
            'total_bytes': 0,
            'start_time': asyncio.get_event_loop().time()
        }
        
        self.streaming_sessions[session_id] = session_data
        logger.info(make_log_safe(f"🎵 Started streaming session: {session_id[:8]} -> {audio_filename}"))
        return session_id
    
    def get_streaming_session(self, session_id: str) -> Dict:
        """Get streaming session data"""
        return self.streaming_sessions.get(session_id)
    
    def end_streaming_session(self, session_id: str):
        """End a streaming session and close files"""
        if session_id in self.streaming_sessions:
            session_data = self.streaming_sessions[session_id]
            
            if 'audio_file' in session_data and session_data['audio_file']:
                session_data['audio_file'].close()
            
            duration = asyncio.get_event_loop().time() - session_data['start_time']
            logger.info(make_log_safe(f"🔴 Ended streaming session: {session_id[:8]}. Duration: {duration:.2f}s"))
            
            del self.streaming_sessions[session_id]

# Create connection manager instance
manager = ConnectionManager()

# ---- WebSocket Endpoints ----

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """✅ PRESERVED: Text-based WebSocket endpoint from Day 15"""
    await manager.connect(websocket)
    
    await manager.send_personal_message(
        make_log_safe("🎉 Welcome to Voice Agent WebSocket! Send me a message and I'll echo it back!"), 
        websocket
    )
    
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(make_log_safe(f"📨 Received: {data}"))
            
            echo_message = f"Echo: {data}"
            await manager.send_personal_message(echo_message, websocket)
            
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            await manager.send_personal_message(make_log_safe(f"⏰ Message received at {timestamp}"), websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Text WebSocket error: {e}")
        manager.disconnect(websocket)

@app.websocket("/ws/stream-audio")
async def stream_audio_endpoint(websocket: WebSocket):
    """✅ PRESERVED: Audio streaming WebSocket from Day 16"""
    await manager.connect(websocket)
    session_id = None
    
    try:
        await manager.send_personal_message(
            json.dumps({
                "type": "connection", 
                "status": "connected",
                "message": make_log_safe("🎙️ Audio streaming ready! Send binary audio data to start recording.")
            }), 
            websocket
        )
        
        while True:
            try:
                data = await websocket.receive()
                
                if "text" in data:
                    message_data = json.loads(data["text"])
                    session_id = await handle_streaming_command(websocket, message_data, session_id)
                    
                elif "bytes" in data:
                    audio_chunk = data["bytes"]
                    
                    if session_id is None:
                        session_id = manager.start_streaming_session(websocket)
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "session_started", 
                                "session_id": session_id,
                                "message": make_log_safe("🔴 Recording started! Receiving audio data...")
                            }), 
                            websocket
                        )
                    
                    await handle_audio_chunk(session_id, audio_chunk, websocket)
                    
            except json.JSONDecodeError:
                if manager.is_websocket_active(websocket):
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "message": "Invalid JSON format"}), 
                        websocket
                    )
            except Exception as e:
                logger.error(f"Error processing websocket data: {e}")
                if manager.is_websocket_active(websocket):
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "message": f"Processing error: {str(e)}"}), 
                        websocket
                    )
                
    except WebSocketDisconnect:
        logger.info(f"Audio streaming client disconnected. Session: {session_id}")
        if session_id:
            manager.end_streaming_session(session_id)
        manager.disconnect(websocket)
        
    except Exception as e:
        logger.error(f"Audio streaming WebSocket error: {e}")
        if session_id:
            manager.end_streaming_session(session_id)
        manager.disconnect(websocket)

# NEW: Real-time transcription WebSocket endpoint
@app.websocket("/ws/transcribe-stream")
async def transcribe_stream_endpoint(websocket: WebSocket):
    """
    🔥 UPDATED: WebSocket endpoint for real-time audio transcription WITH TURN DETECTION
    """
    await manager.connect(websocket)
    transcription_session_id = None
    
    try:
        # Welcome message with turn detection info
        if manager.is_websocket_active(websocket):
            await manager.send_personal_message(
                json.dumps({
                    "type": "connection", 
                    "status": "connected",
                    "message": make_log_safe("🎤 Real-time transcription with TURN DETECTION ready! Send 16kHz PCM audio data."),
                    "requirements": {
                        "sample_rate": "16000 Hz",
                        "format": "16-bit PCM",
                        "channels": "mono",
                        "turn_detection": "enabled"  # 🔥 NEW: Indicate turn detection is active
                    }
                }), 
                websocket
            )
        
        while True:
            try:
                if not manager.is_websocket_active(websocket):
                    logger.info("WebSocket no longer active, breaking loop")
                    break
                    
                data = await websocket.receive()
                
                # Handle text commands
                if "text" in data:
                    command_data = json.loads(data["text"])
                    transcription_session_id = await handle_transcription_command(
                        websocket, command_data, transcription_session_id
                    )
                
                # Handle binary audio data
                elif "bytes" in data:
                    audio_chunk = data["bytes"]
                    
                    # Auto-start transcription session with TURN DETECTION
                    if transcription_session_id is None:
                        transcription_session_id = uuid.uuid4().hex
                        
                        # 🔥 NEW: Create session with turn detection enabled
                        success = await streaming_manager.create_session(
                            session_id=transcription_session_id, 
                            websocket=websocket, 
                            sample_rate=16000,
                            enable_turn_detection=True  # 🔥 KEY CHANGE: Enable turn detection
                        )
                        
                        if success:
                            manager.transcription_sessions[websocket] = transcription_session_id
                            if manager.is_websocket_active(websocket):
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "transcription_started",
                                        "session_id": transcription_session_id,
                                        "message": make_log_safe("🎤 Live transcription with TURN DETECTION started! Speak naturally..."),
                                        "turn_detection": True  # 🔥 NEW: Confirm turn detection is active
                                    }), 
                                    websocket
                                )
                                
                                # Console output for debugging
                                print(make_log_safe(f"\n🎯 STARTED TURN DETECTION SESSION: {transcription_session_id[:8]}"))
                                print("=" * 60)
                        else:
                            logger.error("Failed to create transcription session")
                            if manager.is_websocket_active(websocket):
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "error", 
                                        "message": "Failed to start transcription session"
                                    }), 
                                    websocket
                                )
                            break
                    
                    # Process audio chunk for transcription
                    if transcription_session_id:
                        streaming_manager.process_audio_chunk(transcription_session_id, audio_chunk)
                    
            except WebSocketDisconnect:
                logger.info("WebSocket disconnect received")
                break
            except json.JSONDecodeError:
                if manager.is_websocket_active(websocket):
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "message": "Invalid JSON format"}), 
                        websocket
                    )
                else:
                    break
            except RuntimeError as e:
                if "disconnect message" in str(e):
                    logger.info("WebSocket disconnected during receive")
                    break
                else:
                    logger.error(f"Runtime error in transcription websocket: {e}")
                    break
            except Exception as e:
                logger.error(f"Error in transcription websocket: {e}")
                if manager.is_websocket_active(websocket):
                    try:
                        await manager.send_personal_message(
                            json.dumps({"type": "error", "message": f"Transcription error: {str(e)}"}), 
                            websocket
                        )
                    except:
                        pass
                break
                
    except WebSocketDisconnect:
        logger.info(f"Transcription client disconnected. Session: {transcription_session_id}")
    except Exception as e:
        logger.error(f"Transcription WebSocket error: {e}")
    finally:
        # Cleanup in finally block
        if transcription_session_id:
            streaming_manager.end_session(transcription_session_id)
            if websocket in manager.transcription_sessions:
                del manager.transcription_sessions[websocket]
            print(make_log_safe(f"\n🔴 CLEANED UP TURN DETECTION SESSION: {transcription_session_id[:8]}"))
            print("=" * 60)

# 🔥 NEW: Update the transcription command handler to support turn detection
async def handle_transcription_command(websocket: WebSocket, message: dict, current_session_id: str):
    """Handle transcription control commands WITH TURN DETECTION"""
    if not manager.is_websocket_active(websocket):
        return current_session_id
        
    command = message.get("type", "").lower()
    
    if command == "start_transcription":
        if current_session_id is None:
            session_id = uuid.uuid4().hex
            # 🔥 NEW: Enable turn detection for manual start too
            success = await streaming_manager.create_session(
                session_id, 
                websocket,
                enable_turn_detection=True  # 🔥 Enable turn detection
            )
            
            if success:
                manager.transcription_sessions[websocket] = session_id
                await manager.send_personal_message(
                    json.dumps({
                        "type": "transcription_started", 
                        "session_id": session_id,
                        "message": make_log_safe("🎤 Transcription with TURN DETECTION started! Send audio data."),
                        "turn_detection": True  # 🔥 NEW: Confirm turn detection
                    }), 
                    websocket
                )
                print(make_log_safe(f"\n🎯 MANUAL START WITH TURN DETECTION: {session_id[:8]}"))
                return session_id
            else:
                await manager.send_personal_message(
                    json.dumps({"type": "error", "message": "Failed to start transcription"}), 
                    websocket
                )
        else:
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": "Transcription already active"}), 
                websocket
            )
    
    elif command == "stop_transcription":
        if current_session_id:
            streaming_manager.end_session(current_session_id)
            if websocket in manager.transcription_sessions:
                del manager.transcription_sessions[websocket]
            
            await manager.send_personal_message(
                json.dumps({
                    "type": "transcription_stopped", 
                    "session_id": current_session_id,
                    "message": make_log_safe("⏹️ Turn detection transcription stopped!")
                }), 
                websocket
            )
            print(make_log_safe(f"\n🔴 MANUAL STOP TURN DETECTION: {current_session_id[:8]}"))
            print("=" * 60)
            return None
        else:
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": "No active transcription"}), 
                websocket
            )
    
    elif command == "get_transcription_status":
        if current_session_id:
            await manager.send_personal_message(
                json.dumps({
                    "type": "transcription_status", 
                    "session_id": current_session_id,
                    "status": "active",
                    "turn_detection": True,  # 🔥 NEW: Include turn detection status
                    "message": make_log_safe(f"🎤 Active turn detection transcription: {current_session_id[:8]}")
                }), 
                websocket
            )
        else:
            await manager.send_personal_message(
                json.dumps({
                    "type": "transcription_status", 
                    "status": "inactive",
                    "message": "No active transcription session"
                }), 
                websocket
            )
    
    return current_session_id

# ---- Helper functions for audio streaming (✅ PRESERVED from Day 16) ----
async def handle_streaming_command(websocket: WebSocket, message: dict, current_session_id: str):
    """Handle text commands for audio streaming control (preserved)"""
    if not manager.is_websocket_active(websocket):
        return current_session_id
        
    command = message.get("type", "").lower()
    
    if command == "start_recording":
        if current_session_id is None:
            session_id = manager.start_streaming_session(websocket)
            await manager.send_personal_message(
                json.dumps({
                    "type": "session_started", 
                    "session_id": session_id,
                    "message": make_log_safe("🔴 Recording session started! Send audio data.")
                }), 
                websocket
            )
            return session_id
        else:
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": "Recording already in progress"}), 
                websocket
            )
    
    elif command == "stop_recording":
        if current_session_id:
            session_data = manager.get_streaming_session(current_session_id)
            if session_data:
                await manager.send_personal_message(
                    json.dumps({
                        "type": "recording_stopped", 
                        "session_id": current_session_id,
                        "chunks_received": session_data["chunks_received"],
                        "total_bytes": session_data["total_bytes"],
                        "file_path": str(session_data["audio_path"]),
                        "message": make_log_safe("⹸ Recording stopped and saved!")
                    }), 
                    websocket
                )
                manager.end_streaming_session(current_session_id)
                return None
        else:
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": "No active recording session"}), 
                websocket
            )
    
    elif command == "get_status":
        if current_session_id:
            session_data = manager.get_streaming_session(current_session_id)
            if session_data:
                duration = asyncio.get_event_loop().time() - session_data['start_time']
                await manager.send_personal_message(
                    json.dumps({
                        "type": "status", 
                        "session_id": current_session_id,
                        "chunks_received": session_data["chunks_received"],
                        "total_bytes": session_data["total_bytes"],
                        "duration_seconds": round(duration, 2),
                        "file_path": str(session_data["audio_path"]),
                        "message": make_log_safe(f"📊 Recording: {duration:.1f}s, {session_data['chunks_received']} chunks")
                    }), 
                    websocket
                )
        else:
            await manager.send_personal_message(
                json.dumps({"type": "status", "message": "No active recording session"}), 
                websocket
            )
    
    return current_session_id

async def handle_audio_chunk(session_id: str, audio_data: bytes, websocket: WebSocket):
    """Handle incoming audio chunk and save to file (✅ PRESERVED)"""
    if not manager.is_websocket_active(websocket):
        return
        
    session_data = manager.get_streaming_session(session_id)
    if not session_data:
        await manager.send_personal_message(
            json.dumps({"type": "error", "message": "Invalid session"}), 
            websocket
        )
        return
    
    try:
        # Open file for writing if not already open
        if session_data['audio_file'] is None:
            session_data['audio_file'] = open(session_data['audio_path'], 'wb')
            logger.info(f"Opened audio file: {session_data['audio_path']}")
        
        # Write audio chunk to file
        session_data['audio_file'].write(audio_data)
        session_data['audio_file'].flush()
        
        # Update session statistics
        session_data['chunks_received'] += 1
        session_data['total_bytes'] += len(audio_data)
        
        # Send periodic progress updates (every 20 chunks to avoid spam)
        if session_data['chunks_received'] % 20 == 0:
            duration = asyncio.get_event_loop().time() - session_data['start_time']
            await manager.send_personal_message(
                json.dumps({
                    "type": "chunk_received", 
                    "chunks_received": session_data['chunks_received'],
                    "total_bytes": session_data['total_bytes'],
                    "duration_seconds": round(duration, 2),
                    "chunk_size": len(audio_data),
                    "message": make_log_safe(f"📡 Recording: {duration:.1f}s ({session_data['total_bytes']} bytes)")
                }), 
                websocket
            )
        
        logger.debug(f"Session {session_id[:8]}: Saved {len(audio_data)} bytes (chunk #{session_data['chunks_received']})")
        
    except Exception as e:
        logger.error(f"Failed to save audio chunk: {e}")
        if manager.is_websocket_active(websocket):
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": f"Failed to save audio: {str(e)}"}), 
                websocket
            )

# ---- Original API Endpoints (✅ PRESERVED from previous days) ----
@app.websocket("/ws/llm-stream")
async def llm_stream_endpoint(websocket: WebSocket):
    """
    FIXED: Complete Voice Agent WebSocket with STT + Turn Detection + LLM + TTS
    """
    await manager.connect(websocket)
    transcription_session_id = None  # NEW: Track transcription session
    
    try:
        # Welcome message
        await manager.send_personal_message(
            json.dumps({
                "type": "connection", 
                "status": "connected",
                "message": make_log_safe("[MIC] LLM + Audio streaming ready! Send text or audio for AI response with streamed audio.")
            }), 
            websocket
        )
        
        while True:
            try:
                if not manager.is_websocket_active(websocket):
                    logger.info("WebSocket no longer active, breaking loop")
                    break
                    
                data = await websocket.receive()
                
                # Handle text commands/messages
                if "text" in data:
                    message_data = json.loads(data["text"])
                    await handle_llm_stream_command(websocket, message_data)
                
                # FIXED: Handle binary audio data with STT + Turn Detection
                elif "bytes" in data:
                    audio_chunk = data["bytes"]
                    logger.info("Received audio data for STT processing")
                    
                    # AUTO-START transcription session with turn detection
                    if transcription_session_id is None:
                        transcription_session_id = uuid.uuid4().hex
                        
                        # Create STT session with turn detection enabled
                        success = await streaming_manager.create_session(
                            session_id=transcription_session_id, 
                            websocket=websocket, 
                            sample_rate=16000,
                            enable_turn_detection=True  # KEY: Enable turn detection
                        )
                        
                        if success:
                            manager.transcription_sessions[websocket] = transcription_session_id
                            logger.info(f"[SUCCESS] Started STT session with turn detection: {transcription_session_id[:8]}")
                            
                            # Notify client that session started
                            await manager.send_personal_message(
                                json.dumps({
                                    "type": "session_opened",
                                    "session_id": transcription_session_id,
                                    "message": "[MIC] STT session with turn detection started!",
                                    "turn_detection_enabled": True
                                }), 
                                websocket
                            )
                        else:
                            logger.error("Failed to create STT transcription session")
                            await manager.send_personal_message(
                                json.dumps({
                                    "type": "error", 
                                    "message": "Failed to start voice recognition"
                                }), 
                                websocket
                            )
                            continue
                    
                    # FIXED: Process audio chunk through STT system
                    if transcription_session_id:
                        streaming_manager.process_audio_chunk(transcription_session_id, audio_chunk)
                    
            except WebSocketDisconnect:
                logger.info("LLM stream WebSocket disconnect received")
                break
            except RuntimeError as e:
                if "disconnect message" in str(e).lower():
                    logger.info("WebSocket disconnected during receive")
                    break
                else:
                    logger.error(f"Runtime error in LLM stream websocket: {e}")
                    break
            except json.JSONDecodeError:
                if manager.is_websocket_active(websocket):
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "message": "Invalid JSON format"}), 
                        websocket
                    )
                else:
                    break
            except Exception as e:
                logger.error(f"Error in LLM stream websocket: {e}")
                if manager.is_websocket_active(websocket):
                    try:
                        await manager.send_personal_message(
                            json.dumps({"type": "error", "message": f"Processing error: {str(e)}"}), 
                            websocket
                        )
                    except:
                        pass
                break
                
    except WebSocketDisconnect:
        logger.info("LLM stream client disconnected")
    except Exception as e:
        logger.error(f"LLM stream WebSocket error: {e}")
    finally:
        # FIXED: Cleanup transcription session
        if transcription_session_id:
            streaming_manager.end_session(transcription_session_id)
            if websocket in manager.transcription_sessions:
                del manager.transcription_sessions[websocket]
            logger.info(f"[SUCCESS] Cleaned up STT session: {transcription_session_id[:8]}")
        
        manager.disconnect(websocket)

async def handle_llm_stream_command(websocket: WebSocket, message: dict):
    """
    Handle LLM streaming commands and process with audio streaming + session management
    """
    command = message.get("type", "").lower()
    
    if command == "chat_message":
        user_text = message.get("text", "").strip()
        session_id = message.get("session_id", None)  # NEW: Get session_id from message
        
        if not user_text:
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": "Empty message"}), 
                websocket
            )
            return
        
        # NEW: Generate session_id if not provided
        if not session_id:
            session_id = f"ws_session_{int(time.time())}_{random.randint(1000, 9999)}"
            logger.info(f"Generated new session_id: {session_id}")
        
        try:
            # Send acknowledgment
            await manager.send_personal_message(
                json.dumps({
                    "type": "chat_started",
                    "user_message": user_text,
                    "session_id": session_id,  # NEW: Include session_id in response
                    "message": f"Processing: {user_text[:50]}..."
                }), 
                websocket
            )
            
            # NEW: Get or create conversation history for this session
            if session_id not in chat_histories:
                chat_histories[session_id] = []
                logger.info(f"Created new chat history for session: {session_id}")
            
            conversation_history = chat_histories[session_id]
            logger.info(f"Session {session_id} has {len(conversation_history)} previous messages")
            
            # NEW: Add user message to conversation history
            conversation_history.append({
                "role": "user", 
                "content": user_text
            })
            
            # Use the direct streaming method instead
            llm_response = await llm_service.process_transcript_and_stream_to_client(
                user_text,
                murf_websocket_service,
                websocket
            )
            
            # NEW: Add LLM response to conversation history
            conversation_history.append({
                "role": "assistant", 
                "content": llm_response
            })
            
            # NEW: Update chat_histories with the updated conversation
            chat_histories[session_id] = conversation_history
            
            # Send final LLM response with session info
            await manager.send_personal_message(
                json.dumps({
                    "type": "llm_response_complete",
                    "session_id": session_id,  # NEW: Include session_id
                    "user_transcript": user_text,  # NEW: Include user transcript
                    "llm_response": llm_response,
                    "message": "LLM response complete"
                }), 
                websocket
            )
            
            # Send chat complete notification
            await manager.send_personal_message(
                json.dumps({
                    "type": "chat_complete",
                    "session_id": session_id,  # NEW: Include session_id
                    "llm_response": llm_response,
                    "message": "Chat processing complete!"
                }), 
                websocket
            )
            
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            await manager.send_personal_message(
                json.dumps({
                    "type": "error", 
                    "session_id": session_id if 'session_id' in locals() else None,
                    "message": f"Chat processing failed: {str(e)}"
                }), 
                websocket
            )
    
    elif command == "ping":
        await manager.send_personal_message(
            json.dumps({"type": "pong", "message": "LLM stream WebSocket is active"}), 
            websocket
        )

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

# ---- Helper Functions (✅ PRESERVED from previous days) ----

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
                error="stt_failed"
            )
        
        # Transcribe audio - FIX: Actually transcribe the audio
        try:
            user_text = await _transcribe_audio(wav_path)
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ChatResponse(
                transcription="",
                text="I couldn't understand the audio.",
                audio_url=fallback_audio,
                error="stt_failed"
            )
        
        # Process with LLM
        try:
            if session_id:
                assistant_text = await _process_chat_with_history(user_text, session_id)
            else:
                # 🎵 NEW: Use Murf streaming for non-session chats too
                assistant_text = await llm_service.process_transcript_and_stream(
                    user_text, 
                    murf_websocket_service
                )
                
            logger.info(f"LLM response: {assistant_text}")
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            return ChatResponse(
                transcription=user_text,
                text="I'm having trouble processing your request right now.",
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
    
    # Generate response - handle both async and sync LLM services
    try:
        assistant_text = await llm_service.process_transcript_and_stream(
            user_text, 
            murf_websocket_service
        )
    except Exception as e:
        logger.error(f"Streaming LLM with Murf failed: {e}")
        # Fallback to regular LLM without Murf
        if asyncio.iscoroutinefunction(llm_service.generate_response):
            assistant_text = await llm_service.generate_response(conversation)
        else:
            assistant_text = llm_service.generate_response(conversation)
    
    # Save assistant response
    history.append({"role": "assistant", "text": assistant_text})
    chat_histories[session_id] = history
    
    return assistant_text

# ---- Static Files ----
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)