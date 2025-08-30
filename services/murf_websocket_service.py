# services/murf_websocket_service.py - FIXED VERSION WITH CONNECTION RESET
import asyncio
from email.mime import text
from urllib import response
import websockets
import json
import logging
import uuid
from typing import Optional, Callable

logger = logging.getLogger(__name__)

def make_log_safe(message: str) -> str:
    """Replace emojis with text alternatives for safe console logging"""
    emoji_replacements = {
        "🎵": "[AUDIO]",
        "🔊": "[SPEAKER]", 
        "⚡": "[POWER]",
        "✅": "[SUCCESS]",
        "❌": "[ERROR]",
        "🎯": "[TARGET]",
        "📡": "[STREAMING]",
        "🎤": "[MIC]",
        "🔥": "[FIRE]",
        "💬": "[SPEECH]",
        "🌟": "[STAR]"
    }
    
    for emoji, replacement in emoji_replacements.items():
        message = message.replace(emoji, replacement)
    return message

class MurfWebSocketService:
    """
    🎵 Murf WebSocket service for real-time text-to-speech streaming
    FIXED VERSION - Resets connection for each turn to prevent degradation
    """
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Murf API key is required")
                
        self.api_key = api_key
        self.websocket = None
        self.is_connected = False
        self.context_id = "voice_agent_day20_context"
        
        # Default voice configuration
        self.voice_config = {
            "voiceId": "en-US-darnell",
            "style": "Conversational",
            "rate": 0,
            "pitch": 0,
            "variation": 1
        }
        
        logger.info("[AUDIO] Murf WebSocket Service initialized")

    async def connect(self) -> bool:
        """Connect to Murf WebSocket endpoint"""
        try:
            # Close existing connection first
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None
            
            murf_ws_url ="wss://api.murf.ai/v1/speech/stream-input"
            logger.info("[STREAMING] Connecting to Murf WebSocket...")
            
            # Connect to Murf WebSocket
            ws_url_with_params = f"{murf_ws_url}?api-key={self.api_key}&sample_rate=44100&channel_type=MONO&format=WAV"
            self.websocket = await websockets.connect(
                ws_url_with_params,
                ping_interval=30,
                ping_timeout=20,
                close_timeout=15,
                max_size=10**7
            )
            
            self.is_connected = True
            # Reset voice config flag for fresh connection
            self._voice_config_sent = False
            
            logger.info("[SUCCESS] Connected to Murf WebSocket successfully")
            print(make_log_safe("\n🎯 MURF WEBSOCKET CONNECTED"))
            print("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Murf WebSocket: {e}")
            print(make_log_safe(f"\n❌ MURF CONNECTION ERROR: {e}"))
            self.is_connected = False
            return False

    async def _send_voice_config(self, voice_id: str = None):
        """Send voice configuration as first message"""
        voice_config_msg = {
            "voice_config": {
                "voiceId": voice_id or self.voice_config["voiceId"],
                "style": "Conversational",
                "rate": 0,
                "pitch": 0,
                "variation": 1
            }
        }
        await self.websocket.send(json.dumps(voice_config_msg))
        logger.debug("Sent voice configuration to Murf")

    # CRITICAL FIX: Reset connection before each streaming session
    async def ensure_fresh_connection(self) -> bool:
        """FIXED: Always create fresh connection for each streaming session"""
        try:
            logger.info("[RESET] Creating fresh Murf connection for new turn...")
            
            # Force close existing connection
            if self.websocket:
                try:
                    await self.websocket.close()
                    await asyncio.sleep(0.1)  # Brief pause
                except:
                    pass
            
            # Create new connection
            success = await self.connect()
            if success:
                logger.info("[RESET] Fresh Murf connection established")
                return True
            else:
                logger.error("[RESET] Failed to establish fresh connection")
                return False
                
        except Exception as e:
            logger.error(f"Error creating fresh connection: {e}")
            return False

    async def stream_tts_to_client(self, text: str, client_websocket, voice_id: str = None) -> None:
        """
        FIXED: Stream TTS audio with fresh connection for each session
        """
        try:
            logger.info(f"[TTS] Starting TTS streaming for text: {text[:50]}...")
            
            # CRITICAL FIX: Always use fresh connection
            if not await self.ensure_fresh_connection():
                logger.error("Failed to establish fresh Murf connection")
                return
            
            # Send voice config for fresh connection
            await self._send_voice_config(voice_id)
            
            # Split text into chunks
            words = text.split()
            chunk_size = 12
            chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
            chunks = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 3]
            
            total_chunks = len(chunks)
            logger.info(f"[TTS] Streaming {total_chunks} chunks with fresh connection")
            
            successful_chunks = 0
            
            for i, chunk in enumerate(chunks):
                try:
                    message = {
                        "text": chunk.strip(),
                        "end": (i == total_chunks - 1)
                    }
                    
                    await self.websocket.send(json.dumps(message))
                    logger.debug(f"[TTS] Sent chunk {i+1}/{total_chunks}")
                    
                    # Wait for response with timeout
                    response_data = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=10.0
                    )
                    response = json.loads(response_data)
                    
                    if "audio" in response and response["audio"]:
                        base64_audio = response["audio"]
                        successful_chunks += 1
                        
                        # Send to client
                        if client_websocket:
                            try:
                                audio_message = {
                                    "type": "audio_chunk",
                                    "audio_data": base64_audio,
                                    "chunk_index": successful_chunks,
                                    "chunk_size": len(base64_audio)
                                }
                                await client_websocket.send_text(json.dumps(audio_message))
                                logger.info(f"[TTS] Forwarded chunk {successful_chunks} to client")
                                
                            except Exception as send_error:
                                logger.error(f"Failed to forward audio: {send_error}")
                        
                        # Console output
                        print(make_log_safe(f"\n🎵 BASE64 AUDIO CHUNK {successful_chunks} ({len(base64_audio)} chars):"))
                        print("-" * 80)
                        print(base64_audio[:100] + "..." if len(base64_audio) > 100 else base64_audio)
                        print("-" * 80)
                    
                    await asyncio.sleep(0.05)
                    
                except asyncio.TimeoutError:
                    logger.error(f"Timeout on chunk {i+1}, skipping")
                    continue
                except Exception as chunk_error:
                    logger.error(f"Error processing chunk {i+1}: {chunk_error}")
                    continue
            
            # Send completion message
            if client_websocket and successful_chunks > 0:
                try:
                    completion_message = {
                        "type": "audio_complete",
                        "total_chunks": successful_chunks,
                        "message": f"Audio complete - {successful_chunks} chunks"
                    }
                    await client_websocket.send_text(json.dumps(completion_message))
                    logger.info(f"[TTS] Completed - {successful_chunks}/{total_chunks} chunks successful")
                except Exception as completion_error:
                    logger.error(f"Failed to send completion: {completion_error}")
            
            # CRITICAL: Close connection after each use to prevent degradation
            await self.close()
            logger.info("[TTS] Connection closed after streaming session")
            
        except Exception as e:
            logger.error(f"Error in stream_tts_to_client: {e}")
            await self.close()

    async def stream_weather_tts_to_client(self, text: str, client_websocket, voice_id: str = None) -> None:
        """Stream weather TTS with proper chunking and completion signals"""
        try:
            logger.info(f"[WEATHER-TTS] Starting weather TTS...")
            
            # Use fresh connection for weather too
            if not await self.ensure_fresh_connection():
                logger.error("Failed to establish fresh connection for weather")
                return
            
            await self._send_voice_config(voice_id)
            
            # FIXED: Split weather text into chunks like regular TTS
            words = text.split()
            chunk_size = 15  # Slightly larger chunks for weather
            chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
            chunks = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 3]
            
            total_chunks = len(chunks)
            successful_chunks = 0
            
            for i, chunk in enumerate(chunks):
                try:
                    message = {
                        "text": chunk.strip(),
                        "end": (i == total_chunks - 1)
                    }
                    
                    await self.websocket.send(json.dumps(message))
                    logger.debug(f"[WEATHER-TTS] Sent chunk {i+1}/{total_chunks}")
                    
                    response_data = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=15.0
                    )
                    response = json.loads(response_data)
                    
                    if "audio" in response and response["audio"]:
                        base64_audio = response["audio"]
                        successful_chunks += 1
                        
                        # Send to client with proper format
                        if client_websocket:
                            audio_message = {
                                "type": "audio_chunk",
                                "audio_data": base64_audio,
                                "chunk_index": successful_chunks,
                                "chunk_size": len(base64_audio)
                            }
                            await client_websocket.send_text(json.dumps(audio_message))
                            logger.info(f"[WEATHER-TTS] Forwarded chunk {successful_chunks} to client")
                        
                        print(f"\nWEATHER AUDIO CHUNK {successful_chunks} ({len(base64_audio)} chars):")
                        print("-" * 50)
                        print(base64_audio[:100] + "..." if len(base64_audio) > 100 else base64_audio)
                        print("-" * 50)
                    
                    await asyncio.sleep(0.05)
                    
                except Exception as chunk_error:
                    logger.error(f"Error processing weather chunk {i+1}: {chunk_error}")
                    continue
            
            # Send completion message
            if client_websocket and successful_chunks > 0:
                completion_message = {
                    "type": "audio_complete",
                    "total_chunks": successful_chunks,
                    "message": f"Weather audio complete - {successful_chunks} chunks"
                }
                await client_websocket.send_text(json.dumps(completion_message))
                logger.info(f"[WEATHER-TTS] Completed - {successful_chunks}/{total_chunks} chunks successful")
            
            # Close after weather
            await self.close()
            
        except Exception as e:
            logger.error(f"Weather TTS streaming failed: {e}")
            await self.close()
    async def close(self):
        """Close Murf WebSocket connection"""
        try:
            if self.websocket and self.is_connected:
                await self.websocket.close()
                logger.debug("[DISCONNECT] Murf WebSocket connection closed")
            
            self.is_connected = False
            self.websocket = None
            
        except Exception as e:
            logger.error(f"Error closing Murf WebSocket: {e}")
    
    def is_connection_active(self) -> bool:
        """Check if WebSocket connection is active"""
        return self.is_connected and self.websocket is not None
    
    async def ensure_connection(self) -> bool:
        """Ensure WebSocket connection is active"""
        return await self.ensure_fresh_connection()

    # Legacy methods - keeping for compatibility
    async def send_text_chunk(self, text_chunk: str, voice_id: str = None) -> Optional[str]:
        """Legacy method - maintained for compatibility"""
        if not await self.ensure_fresh_connection():
            return None
            
        try:
            await self._send_voice_config(voice_id)
            
            message = {
                "text": text_chunk.strip(),
                "end": True
            }
            
            await self.websocket.send(json.dumps(message))
            
            response_data = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=10.0
            )
            response = json.loads(response_data)
            
            base64_audio = response.get("audio")
            await self.close()  # Always close after use
            
            return base64_audio
            
        except Exception as e:
            logger.error(f"Error in send_text_chunk: {e}")
            await self.close()
            return None