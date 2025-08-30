from services.llm_service import LLMService
import logging
import asyncio
import json
import threading
from typing import Dict, Optional, Callable, Type
from pathlib import Path
import tempfile
import requests
import assemblyai as aai
from fastapi import WebSocket, UploadFile
import uuid
import queue
import time

# CRITICAL: Import the NEW streaming v3 API (like the working GitHub code)
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)

logger = logging.getLogger(__name__)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from services.llm_service import LLMService
    
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
        "🎙️": "[MICROPHONE]",
        "🔄": "[PROCESSING]",
        "🎵": "[AUDIO]",
        "🔊": "[SPEAKER]",
        "👂": "[LISTENING]",
        "💬": "[SPEECH]",
        "🌟": "[STAR]",
        "🛑": "[STOP]"
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
        
        # Initialize the transcriber for file-based transcription
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
    
    def transcribe_upload(self, audio_file: UploadFile) -> str:
        """Transcribes audio to text using AssemblyAI (like GitHub code)."""
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_file.file)
        if transcript.status == aai.TranscriptStatus.error or not transcript.text:
            raise Exception(f"Transcription failed: {transcript.error or 'No speech detected'}")
        return transcript.text

class StreamingTranscriptionManager:
    """
    REVERTED: Manager using your ORIGINAL working AssemblyAI Streaming V3 API + turn detection
    """
    
    def __init__(self, stt_service: STTService, llm_service: 'LLMService' = None, murf_service=None):
        self.stt_service = stt_service
        self.llm_service = llm_service  # Store LLM service for streaming
        self.murf_service = murf_service  # 🎵 NEW: Day 20 - Store Murf service
        self.active_sessions: Dict[str, 'NewStreamingSession'] = {}
        logger.info(make_log_safe("🎤 StreamingTranscriptionManager initialized (Streaming V3 API + Murf)"))
    
    async def create_session(self, session_id: str, websocket: WebSocket, sample_rate: int = 16000, 
                           enable_turn_detection: bool = True, **kwargs) -> bool:
        """
        Create a new streaming transcription session using V3 API
        FIXED: Now accepts enable_turn_detection parameter without breaking
        """
        try:
            session = NewStreamingSession(
                session_id=session_id,
                websocket=websocket,
                api_key=self.stt_service.api_key,
                sample_rate=sample_rate,
                manager=self,
                enable_turn_detection=enable_turn_detection,
                llm_service=self.llm_service,
                murf_service=self.murf_service  # 🎵 NEW: Pass Murf service
            )
            
            success = await session.start()
            if success:
                self.active_sessions[session_id] = session
                logger.info(make_log_safe(f"✅ Created Streaming V3 session: {session_id} (turn_detection: {enable_turn_detection})"))
                return True
            else:
                logger.error(f"Failed to start Streaming V3 session: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating Streaming V3 session: {e}")
            return False
    
    def process_audio_chunk(self, session_id: str, audio_data: bytes):
        """Process audio chunk for real-time transcription"""
        session = self.active_sessions.get(session_id)
        if session and session.is_active:
            session.add_audio_data(audio_data)
        else:
            if session_id in self.active_sessions:
                logger.warning(f"Session exists but not active: {session_id}")
            else:
                logger.warning(f"No active session found: {session_id}")
    
    def end_session(self, session_id: str):
        """End a streaming session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            asyncio.create_task(session.close())
            del self.active_sessions[session_id]
            logger.info(make_log_safe(f"🔴 Ended Streaming V3 session: {session_id}"))
        else:
            logger.warning(f"Session not found for cleanup: {session_id}")

class NewStreamingSession:
    """
    REVERTED TO YOUR ORIGINAL WORKING CODE + proper turn detection support
    """
    
    def __init__(self, session_id: str, websocket: WebSocket, api_key: str, 
                 sample_rate: int, manager: StreamingTranscriptionManager,
                 enable_turn_detection: bool = True, llm_service: 'LLMService' = None, murf_service=None):
        self.session_id = session_id
        self.websocket = websocket
        self.api_key = api_key
        self.sample_rate = sample_rate
        self.manager = manager
        self.enable_turn_detection = enable_turn_detection
        self.llm_service = llm_service 
        self.murf_service = murf_service  # 🎵 NEW: Store Murf service

        # Streaming components (EXACT same as your working code)
        self.streaming_client = None
        self.is_active = False
        self.audio_queue = queue.Queue()
        self._processing_thread = None
        self.loop = None
        
        # Turn detection tracking
        self.last_transcript = ""
        self.turn_silence_start = None
        self.last_processed_transcript = ""  # NEW: Track processed transcripts to prevent duplicates

        logger.info(make_log_safe(f"🎯 Session initialized with turn_detection: {enable_turn_detection}"))
    
    async def start(self) -> bool:
        """Start streaming session using ORIGINAL WORKING Streaming V3 API"""
        try:
            self.loop = asyncio.get_running_loop()
            
            # EXACT same initialization as your working code
            self.streaming_client = StreamingClient(
                StreamingClientOptions(
                    api_key=self.api_key,
                    api_host="streaming.assemblyai.com",
                )
            )
            
            # EXACT same event handlers as your working code
            self.streaming_client.on(StreamingEvents.Begin, self._on_begin)
            self.streaming_client.on(StreamingEvents.Turn, self._on_turn)
            self.streaming_client.on(StreamingEvents.Termination, self._on_terminated)
            self.streaming_client.on(StreamingEvents.Error, self._on_error)
            
            # REVERTED: Use your ORIGINAL working parameters (no enable_extra_session_information)
            self.streaming_client.connect(
                StreamingParameters(
                    sample_rate=self.sample_rate,
                    format_turns=True,
                )
            )
            
            self.is_active = True
            
            # Start processing thread for audio data (EXACT same as working code)
            self._processing_thread = threading.Thread(target=self._process_audio_queue, daemon=True)
            self._processing_thread.start()
            
            logger.info(make_log_safe(f"🎤 Streaming V3 connected (sample_rate: {self.sample_rate}Hz)"))
            print(make_log_safe("\n🎯 STREAMING V3 CONNECTED"))
            print("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Streaming V3: {e}")
            return False
    
    def add_audio_data(self, audio_data: bytes):
        """Add audio data to processing queue (EXACT same as working code)"""
        if self.is_active and len(audio_data) > 0:
            self.audio_queue.put(audio_data)
    
    def _process_audio_queue(self):
        """Process audio data from queue and send to Streaming V3 (EXACT same as working code)"""
        while self.is_active:
            try:
                audio_data = self.audio_queue.get(timeout=1.0)
                
                logger.info(f"Processing audio chunk: {len(audio_data)} bytes")
                print(f"AUDIO DEBUG: Chunk size: {len(audio_data)}, First 10 bytes: {audio_data[:10]}")
            

                if self.streaming_client and self.is_active:
                    # Send audio data using V3 API (same as your working code)
                    self.streaming_client.stream(audio_data)
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio queue: {e}")
                break
    
    # EXACT same event handlers as your working code
    def _on_begin(self, client: Type[StreamingClient], event: BeginEvent):
        """Called when transcription session starts (same as working code)"""
        logger.info(f"Transcription session started: {event.id}")
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._send_websocket_message({
                    "type": "session_opened",
                    "session_id": self.session_id,
                    "message": "Streaming V3 session opened",
                    "session_info": {"id": event.id},
                    "turn_detection_enabled": self.enable_turn_detection
                }), 
                self.loop
            )
    
    def _on_turn(self, client: Type[StreamingClient], event: TurnEvent):
        """FIXED: Turn event handler - prevent duplicate processing"""
        try:
            transcript_text = event.transcript
            is_turn_ending = event.end_of_turn
            is_formatted = event.turn_is_formatted
            
            logger.info(f"Real-time transcript: {transcript_text}")
            print(f"TRANSCRIPTION: {transcript_text}")
            
            if transcript_text.strip():
                # Send live transcript - avoid duplicates by checking if text changed
                if transcript_text != self.last_transcript and self.loop and not self.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        self._send_transcript_message(
                            transcript_text, 
                            is_final=is_turn_ending,
                            turn_data={
                                'end_of_turn': is_turn_ending,
                                'turn_is_formatted': is_formatted
                            }
                        ), 
                        self.loop
                    )
                            
                # Console output
                status = "[FORMATTED]" if is_formatted else "[UNFORMATTED]"
                finality = "[TURN_COMPLETE]" if is_turn_ending else "[ONGOING]"
                print(make_log_safe(f"🔡 {status}{finality}: {transcript_text}"))
                
                # FIXED: Only process turn completion ONCE for formatted final transcripts
                if is_turn_ending and is_formatted and self.enable_turn_detection:
                    # Check if we already processed this exact transcript
                    if transcript_text != self.last_processed_transcript:
                        self.last_processed_transcript = transcript_text  # NEW: Track processed transcripts
                        
                        print("=" * 60)
                        print(make_log_safe("🎯 USER FINISHED SPEAKING - TURN COMPLETE"))
                        print(make_log_safe(f"💬 Final transcript: {transcript_text}"))
                        print("=" * 60)
                        
                        # Send turn completion notification
                        if self.loop and not self.loop.is_closed():
                            asyncio.run_coroutine_threadsafe(
                                self._send_turn_complete_notification(transcript_text),
                                self.loop
                            )
                        
                        # Trigger LLM streaming response
                        if self.llm_service and transcript_text.strip():
                            if self.loop and not self.loop.is_closed():
                                asyncio.run_coroutine_threadsafe(
                                    self._trigger_llm_streaming(transcript_text),
                                    self.loop
                                )
                    else:
                        print(f"SKIPPED: Already processed transcript: {transcript_text}")
                
                # Keep track for turn detection
                self.last_transcript = transcript_text
                
                if is_turn_ending:
                    print("-" * 60)
            
            # Format turns logic (keep as-is)
            if is_turn_ending and not is_formatted:
                params = StreamingParameters(sample_rate=self.sample_rate, format_turns=True)
                client.set_params(params)
                    
        except Exception as e:
            logger.error(f"Error handling transcript data: {e}")
        
    def _on_terminated(self, client: Type[StreamingClient], event: TerminationEvent):
        """Called when session is terminated (EXACT same as working code)"""
        logger.info(f"Transcription session terminated: {event.audio_duration_seconds} seconds processed")
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._send_websocket_message({
                    "type": "session_terminated",
                    "session_id": self.session_id,
                    "message": f"Session terminated after {event.audio_duration_seconds}s",
                    "duration": event.audio_duration_seconds
                }), 
                self.loop
            )
    
    def _on_error(self, client: Type[StreamingClient], error: StreamingError):
        """Called when an error occurs (EXACT same as working code)"""
        logger.error(f"AssemblyAI streaming error: {error}")
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._send_websocket_message({
                    "type": "error",
                    "session_id": self.session_id,
                    "message": f"Transcription error: {error}",
                    "error_details": str(error)
                }), 
                self.loop
            )
        self.is_active = False
    
    async def _send_turn_complete_notification(self, final_transcript: str):
        """NEW: Send turn completion notification to client"""
        message_data = {
            "type": "turn_complete",
            "session_id": self.session_id,
            "final_transcript": final_transcript,
            "message": "User finished speaking - turn complete",
            "timestamp": time.time(),
            "api_version": "streaming_v3",
            "ui_action": "display_final_transcript"
        }
        
        await self._send_websocket_message(message_data)
        logger.info(f"Sent turn completion notification: '{final_transcript}'")
    async def _trigger_llm_streaming(self, transcript: str):
        """
        🚀 NEW: Trigger LLM streaming response when turn is complete
        This is where the magic happens!
        """
        try:
            logger.info(make_log_safe(f"⚡ Triggering LLM streaming for: {transcript[:50]}..."))
            
            # Call the LLM service to process and stream the response
            if self.llm_service:
                complete_response = await self.llm_service.process_transcript_and_stream_to_client(
                    transcript, 
                    self.murf_service, 
                    self.websocket  # 🔥 NEW: Pass client WebSocket for audio forwarding
                )
                # Optional: Send the complete response back to WebSocket for UI
                await self._send_websocket_message({
                    "type": "llm_response_complete",
                    "session_id": self.session_id,
                    "user_transcript": transcript,
                    "llm_response": complete_response,
                    "message": "LLM streaming response completed",
                    "timestamp": time.time()
                })
                
                logger.info(make_log_safe(f"🌟 LLM streaming completed for session: {self.session_id[:8]}"))
            else:
                logger.warning("No LLM service available for streaming")
                
        except Exception as e:
            logger.error(f"Error triggering LLM streaming: {e}")
            print(make_log_safe(f"\n❌ LLM STREAMING TRIGGER ERROR: {e}"))    

    async def _send_transcript_message(self, text: str, is_final: bool, turn_data: dict = None):
        """Send transcript message to client WebSocket (ENHANCED but compatible)"""
        message_data = {
            "type": "transcript",
            "session_id": self.session_id,
            "text": text,
            "is_final": is_final,
            "message": f"Transcript: {text}",
            "api_version": "streaming_v3",
            "timestamp": time.time()
        }
        
        # Add turn detection data if available
        if turn_data:
            message_data["turn_data"] = turn_data
            message_data["user_stopped_talking"] = turn_data.get('end_of_turn', False)
            message_data["transcript_formatted"] = turn_data.get('turn_is_formatted', False)
            
            # Set display mode for UI
            if turn_data.get('end_of_turn', False):
                message_data["display_mode"] = "final"
            else:
                message_data["display_mode"] = "live"
        
        await self._send_websocket_message(message_data)
    
    async def _send_websocket_message(self, message_data: dict):
        """Send message to client WebSocket (EXACT same as working code)"""
        try:
            # Check if WebSocket is still connected
            if not hasattr(self.websocket, 'client_state'):
                return
                
            from starlette.websockets import WebSocketState
            if self.websocket.client_state != WebSocketState.CONNECTED:
                return
                
            await self.websocket.send_text(json.dumps(message_data))
        except Exception as e:
            logger.error(f"Error sending WebSocket message to client: {e}")
            self.is_active = False
    
    async def close(self):
        """Close the streaming session (EXACT same as working code)"""
        self.is_active = False
        
        # Close Streaming V3 client
        if self.streaming_client:
            try:
                self.streaming_client.disconnect(terminate=True)
                logger.info("Streaming V3 client disconnected")
            except Exception as e:
                logger.error(f"Error closing Streaming V3 client: {e}")
        
        # Stop the processing thread
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=2.0)
            
        logger.info(make_log_safe(f"👂 Session {self.session_id} fully closed"))