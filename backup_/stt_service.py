# services/stt_service.py - FIXED VERSION FOR UNIVERSAL-STREAMING
import logging
import asyncio
import json
import threading
from typing import Dict, Optional, Callable
from pathlib import Path
import tempfile
import requests
import assemblyai as aai
from fastapi import WebSocket

logger = logging.getLogger(__name__)

def make_log_safe(message: str) -> str:
    """Replace emojis with text alternatives for safe console logging"""
    emoji_replacements = {
        "🎤": "[MIC]",
        "✅": "[SUCCESS]", 
        "❌": "[ERROR]",
        "🔴": "[RECORDING]",
        "🟢": "[GREEN]",
        "📡": "[STREAMING]",
        "⚡": "[POWER]",
        "🎯": "[TARGET]",
        "🎙️": "[MICROPHONE]"
    }
    
    for emoji, replacement in emoji_replacements.items():
        message = message.replace(emoji, replacement)
    return message

class STTService:
    """Speech-to-Text service using AssemblyAI."""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("AssemblyAI API key is required")
        
        self.api_key = api_key
        aai.settings.api_key = api_key
        
        # Initialize the transcriber
        self.transcriber = aai.Transcriber()
        logger.info("STT Service initialized with AssemblyAI")
    
    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio bytes using AssemblyAI."""
        try:
            # Create a temporary file for the audio data
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Use the file path for transcription
                transcript = self.transcriber.transcribe(temp_path)
                
                if transcript.status == aai.TranscriptStatus.error:
                    raise Exception(f"Transcription failed: {transcript.error}")
                
                return transcript.text or ""
                
            finally:
                # Clean up the temporary file
                Path(temp_path).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

class StreamingTranscriptionManager:
    """
    UPDATED: Manager for Universal-Streaming real-time transcription sessions
    """
    
    def __init__(self, stt_service: STTService):
        self.stt_service = stt_service
        self.active_sessions: Dict[str, 'StreamingSession'] = {}
        logger.info(make_log_safe("🎤 StreamingTranscriptionManager initialized"))
    
    async def create_session(self, session_id: str, websocket: WebSocket, sample_rate: int = 16000,enable_turn_detection: bool = True) -> bool:
        """Create a new Universal-Streaming session"""
        try:
            # Get temporary auth token for Universal-Streaming
            auth_token = self._get_temporary_token()
            if not auth_token:
                logger.error("Failed to get temporary auth token")
                return False
            
            session = StreamingSession(
                session_id=session_id,
                websocket=websocket,
                auth_token=auth_token,
                sample_rate=sample_rate,
                manager=self
            )
            
            success = await session.start()
            if success:
                self.active_sessions[session_id] = session
                logger.info(make_log_safe(f"✅ Created streaming session: {session_id}"))
                return True
            else:
                logger.error(f"Failed to start streaming session: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating streaming session: {e}")
            return False
    
    def _get_temporary_token(self) -> Optional[str]:
        """Get temporary authentication token for Universal-Streaming"""
        try:
            headers = {
                "Authorization": f"Bearer {self.stt_service.api_key}",
                "Content-Type": "application/json"
            }
            
            # Updated endpoint for Universal-Streaming
            response = requests.post(
                "https://api.assemblyai.com/v2/realtime/token",
                headers=headers,
                json={"expires_in": 3600}  # 1 hour expiration
            )
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data.get("token")
            else:
                logger.error(f"Failed to get auth token: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting temporary token: {e}")
            return None
    
    def process_audio_chunk(self, session_id: str, audio_data: bytes):
        """Process audio chunk for streaming transcription"""
        session = self.active_sessions.get(session_id)
        if session:
            session.send_audio(audio_data)
        else:
            logger.warning(f"No active session found: {session_id}")
    
    def end_session(self, session_id: str):
        """End a streaming session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.close()
            del self.active_sessions[session_id]
            logger.info(make_log_safe(f"🔴 Ended streaming session: {session_id}"))
        else:
            logger.warning(f"Session not found for cleanup: {session_id}")

class StreamingSession:
    """
    UPDATED: Individual Universal-Streaming session handler
    """
    
    def __init__(self, session_id: str, websocket: WebSocket, auth_token: str, 
                 sample_rate: int, manager: StreamingTranscriptionManager):
        self.session_id = session_id
        self.websocket = websocket
        self.auth_token = auth_token
        self.sample_rate = sample_rate
        self.manager = manager
        self.transcriber = None
        self.is_active = False
        
    async def start(self) -> bool:
        """Start the Universal-Streaming session"""
        try:
            # Configure Universal-Streaming transcriber
            config = aai.RealtimeTranscriberConfig(
                sample_rate=self.sample_rate,
                format_turns=False,  # For faster response in voice agents
                min_end_of_turn_silence_when_confident=160,  # Default for voice agents
                max_end_of_turn_silence=3000,  # 3 seconds max silence
                end_of_turn_confidence=0.8
            )
            
            # Create the new Universal-Streaming transcriber
            self.transcriber = aai.RealtimeTranscriber(
                config=config,
                on_data=self._on_transcript,
                on_error=self._on_error,
                on_open=self._on_open,
                on_close=self._on_close,
                token=self.auth_token
            )
            
            # Connect to Universal-Streaming service
            await asyncio.get_event_loop().run_in_executor(
                None, self.transcriber.connect
            )
            
            self.is_active = True
            logger.info(make_log_safe(f"🎤 Starting streaming transcription (sample_rate: {self.sample_rate}Hz)"))
            return True
            
        except Exception as e:
            logger.error(f"Failed to start streaming session: {e}")
            return False
    
    def send_audio(self, audio_data: bytes):
        """Send audio data to Universal-Streaming"""
        if self.transcriber and self.is_active:
            try:
                self.transcriber.stream(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio data: {e}")
    
    def close(self):
        """Close the streaming session"""
        self.is_active = False
        if self.transcriber:
            try:
                self.transcriber.close()
                logger.info(make_log_safe("🔴 Streaming transcription stopped"))
            except Exception as e:
                logger.error(f"Error closing transcriber: {e}")
    
    def _on_open(self, session_opened: aai.RealtimeSessionOpened):
        """Handle session opened event"""
        logger.info(make_log_safe("🟢 Connected to AssemblyAI Universal-Streaming service"))
    
    def _on_transcript(self, transcript: aai.RealtimeTranscript):
        """
        Handle Universal-Streaming transcript data
        FIXED: Proper async handling without create_task in thread
        """
        try:
            if hasattr(transcript, 'transcript') and transcript.transcript:
                # Send transcript to WebSocket - schedule in main event loop
                self._schedule_websocket_send({
                    "type": "transcript",
                    "session_id": self.session_id,
                    "text": transcript.transcript,
                    "is_final": getattr(transcript, 'end_of_turn', False),
                    "confidence": getattr(transcript, 'end_of_turn_confidence', 0.0),
                    "message": f"Transcript: {transcript.transcript}"
                })
                
                # Console output for debugging
                print(make_log_safe(f"📡 TRANSCRIPT: {transcript.transcript}"))
                
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
    
    def _on_error(self, error: aai.RealtimeError):
        """
        Handle Universal-Streaming errors
        FIXED: Proper async handling without create_task in thread
        """
        logger.error(make_log_safe(f"❌ Streaming transcription error: {error}"))
        
        # Send error to WebSocket
        self._schedule_websocket_send({
            "type": "error",
            "session_id": self.session_id,
            "error": str(error),
            "message": f"Transcription error: {str(error)}"
        })
    
    def _on_close(self, session_closed):
        """Handle session closed event"""
        logger.info(make_log_safe("🔴 AssemblyAI streaming session closed"))
        self.is_active = False
    
    def _schedule_websocket_send(self, message_data: dict):
        """
        FIXED: Schedule WebSocket message sending in the main event loop
        This avoids the 'no running event loop' error
        """
        try:
            # Use call_soon_threadsafe to schedule in main event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._send_websocket_message(message_data),
                    loop
                )
        except Exception as e:
            # Fallback: try to find any running loop
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        self._send_websocket_message(message_data)
                    )
                    future.result(timeout=1)  # Short timeout
            except Exception as fallback_error:
                logger.error(f"Failed to send websocket message: {e}, fallback failed: {fallback_error}")
    
    async def _send_websocket_message(self, message_data: dict):
        """Send message to WebSocket"""
        try:
            if self.websocket and hasattr(self.websocket, 'send_text'):
                await self.websocket.send_text(json.dumps(message_data))
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")