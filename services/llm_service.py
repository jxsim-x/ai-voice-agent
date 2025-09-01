# services/llm_service.py - ENHANCED VERSION WITH STREAMING SUPPORT
import logging
import asyncio
from urllib import response
import google.generativeai as genai
import json 
from services.weather_service import WeatherService
ZODY_PERSONA = (
    "You are Zody, a friendly and funny robotic assistant. "
    "Always speak like a cheerful robot, mixing humanised humor with helpfulness. "
    "Stay in character as Zody in every reply. " \
    "you are my assistant - i am user"
)
logger = logging.getLogger(__name__)

def make_log_safe(message: str) -> str:
    """Replace emojis with text alternatives for safe console logging"""
    emoji_replacements = {
        "🤖": "[BOT]",
        "⚡": "[POWER]", 
        "🎯": "[TARGET]",\
        "✅": "[SUCCESS]",
        "❌": "[ERROR]",
        "💬": "[SPEECH]",
        "🔄": "[PROCESSING]",
        "📤": "[SENDING]",
        "📥": "[RECEIVING]",
        "🧠": "[BRAIN]",
        "💡": "[IDEA]",
        "🌟": "[STAR]"
    }
    
    for emoji, replacement in emoji_replacements.items():
        message = message.replace(emoji, replacement)
    return message

class LLMService:
    def __init__(self, api_key: str, weather_api_key: str = None):
        if not api_key:
            raise ValueError("Gemini API key is required")
        
        # Configure the API key
        genai.configure(api_key=api_key)
        
        # Initialize the model - KEEPING YOUR ORIGINAL GEMINI 2.5 
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info("LLM Service initialized with Gemini 2.5 Flash (streaming enabled)")

        self.weather_service = None
        if weather_api_key:
            try:
                self.weather_service = WeatherService(weather_api_key)
                logger.info("Weather service initialized in LLM service")
            except Exception as e:
                logger.error(f"Failed to initialize weather service: {e}")        
    
    def generate_response(self, prompt: str) -> str:
        """Generate response using Gemini LLM (non-streaming, for compatibility)."""
        try:
            response = self.model.generate_content(prompt)
            text = response.text if hasattr(response, 'text') else str(response)
            return text.strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
    
    async def generate_streaming_response(self, prompt: str, murf_service=None, client_websocket=None) -> str:
        """
        🚀 ENHANCED: Generate streaming response + forward base64 audio to client
        Now streams audio chunks directly to the frontend WebSocket
        """
        try:
            logger.info(make_log_safe("🤖 Starting LLM streaming response..."))
            
            # 🎯 Ensure Murf connection if service provided
            if murf_service:
                await murf_service.ensure_connection()
            
            # Start background receiver task for Murf responses
            audio_chunks = []
            receiver_task = None
            
            if murf_service and murf_service.is_connection_active():
                async def receive_murf_responses():
                    """Background task to receive and forward Murf audio to client - FIXED VERSION"""
                    try:
                        chunk_count = 0
                        last_chunk_time = asyncio.get_event_loop().time()
                        
                        while True:
                            try:
                                # Wait for response with shorter timeout to detect stalls
                                response_data = await asyncio.wait_for(
                                    murf_service.websocket.recv(),
                                    timeout=5.0  # Shorter timeout
                                )
                                response = json.loads(response_data)
                                current_time = asyncio.get_event_loop().time()
                                
                                if "audio" in response and response["audio"]:
                                    base64_audio = response["audio"]
                                    chunk_count += 1
                                    last_chunk_time = current_time
                                    audio_chunks.append(base64_audio)
                                    
                                    # Forward base64 audio to client WebSocket
                                    if client_websocket:
                                        try:
                                            audio_message = {
                                                "type": "audio_chunk",
                                                "audio_data": base64_audio,
                                                "chunk_index": chunk_count,
                                                "chunk_size": len(base64_audio)
                                            }
                                            await client_websocket.send_text(json.dumps(audio_message))
                                            logger.info(f"Forwarded audio chunk {chunk_count} to client")
                                        except Exception as send_error:
                                            logger.error(f"Failed to forward audio to client: {send_error}")
                                    
                                    # Print base64 audio to console
                                    print(make_log_safe(f"\n🎵 BASE64 AUDIO CHUNK {chunk_count} ({len(base64_audio)} chars):"))
                                    print("-" * 80)
                                    print(base64_audio[:100] + "..." if len(base64_audio) > 100 else base64_audio)
                                    print("-" * 80)
                                
                                # FIXED: Multiple exit conditions
                                if (response.get("final") or 
                                    response.get("end") or 
                                    response.get("audio") == "" or 
                                    response.get("status") == "complete"):
                                    logger.info("Received final audio chunk from Murf")
                                    break
                                    
                                # FIXED: Auto-exit if no chunks received for too long
                                if current_time - last_chunk_time > 8.0:
                                    logger.info("No chunks received for 8 seconds - assuming complete")
                                    break
                                    
                            except asyncio.TimeoutError:
                                # Check if we've been waiting too long without chunks
                                current_time = asyncio.get_event_loop().time()
                                if current_time - last_chunk_time > 6.0:
                                    logger.info("Timeout with no recent chunks - assuming audio complete")
                                    break
                                else:
                                    logger.debug("Short timeout - continuing to wait for audio")
                                    continue
                                    
                    except Exception as e:
                        logger.error(f"Error in Murf receiver: {e}")
                
                # Start the receiver task
                receiver_task = asyncio.create_task(receive_murf_responses())
            
            # [Rest of the method remains the same...]
            # Generate streaming response using Gemini's stream parameter
            response_stream = self.model.generate_content(prompt, stream=True)
            
            complete_response = ""
            chunk_count = 0
            
            # Process each streaming chunk
            for chunk in response_stream:
                if hasattr(chunk, 'text') and chunk.text:
                    chunk_text = chunk.text
                    complete_response += chunk_text
                    chunk_count += 1
                    
                    print(chunk_text, end='', flush=True)
                    
                    # Send chunk to Murf WebSocket
                    if murf_service and murf_service.is_connection_active():
                        try:
                            message = {
                                "text": chunk_text.strip(),
                                "end": False
                            }
                            await murf_service.websocket.send(json.dumps(message))
                        except Exception as murf_error:
                            logger.error(f"Murf sending error: {murf_error}")
                    
                    await asyncio.sleep(0.05)
            
            # Send final message to Murf
            if murf_service and murf_service.is_connection_active():
                try:
                    final_message = {"text": "", "end": True}
                    await murf_service.websocket.send(json.dumps(final_message))
                    
                    # Wait for receiver task to complete
                    if receiver_task:
                        try:
                            await asyncio.wait_for(receiver_task, timeout=15.0)
                            
                            # 🔥 NEW: Send completion message to client
                            if client_websocket and audio_chunks:
                                completion_message = {
                                    "type": "audio_complete",
                                    "total_chunks": len(audio_chunks),
                                    "message": f"Audio streaming complete! Received {len(audio_chunks)} chunks"
                                }
                                await client_websocket.send_text(json.dumps(completion_message))
                            
                        except asyncio.TimeoutError:
                            logger.warning("Timeout waiting for final Murf responses")
                            if not receiver_task.done():
                                receiver_task.cancel()
                except Exception as final_error:
                    logger.error(f"Error with final Murf message: {final_error}")
            
            logger.info(make_log_safe(f"🌟 Streaming response completed: {len(complete_response)} characters"))
            return complete_response.strip()
            
        except Exception as e:
            logger.error(f"LLM streaming generation failed: {e}")
            if 'receiver_task' in locals() and receiver_task and not receiver_task.done():
                receiver_task.cancel()
            raise
    async def process_transcript_and_stream(self, transcript: str, murf_service=None) -> str:
        """
        🎯 ENHANCED: Process user transcript and generate streaming LLM response + Murf audio
        Now integrates with Murf WebSocket for real-time audio generation
        """
        try:
            # Log the incoming transcript
            logger.info(make_log_safe(f"💬 Processing user transcript: {transcript}"))
            print(make_log_safe(f"\n🔥 USER: {transcript}"))
            
            # Create a conversational prompt
            prompt = f"""{ZODY_PERSONA} user's message.

User: {transcript}
"""
            # 🎵 Generate and stream the response WITH Murf integration
            return await self.generate_streaming_response(prompt, murf_service)
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            raise
    async def process_transcript_and_stream_to_client(self, transcript: str, murf_service=None, client_websocket=None) -> str:
        """
        ENHANCED: Process user transcript with weather detection + existing LLM streaming
        Weather queries are handled first, then fallback to normal LLM processing
        """
        try:
            # Log the incoming transcript
            logger.info(make_log_safe(f"💬 Processing user transcript for streaming: {transcript}"))
            print(make_log_safe(f"\n🔥 USER: {transcript}"))
            
            # NEW: Check for weather intent first (high priority)
            if self.weather_service and self.weather_service.detect_weather_intent(transcript):
                logger.info(f"🌤️ Weather intent detected: {transcript}")
                
                try:
                    # Get weather response directly from weather service
                    weather_response = self.weather_service.get_weather_response(transcript)
                    logger.info(f"📊 Weather response generated: {weather_response[:100]}...")
                    
                    # Stream the weather response directly as final text (not through LLM)
                    if murf_service and client_websocket:
                        try:
                            await murf_service.stream_weather_tts_to_client(weather_response, client_websocket)
                            logger.info("Weather response streamed through Murf TTS")
                            # REMOVE the completion signals from here - they're now handled in the Murf service
                        except Exception as stream_error:
                            logger.error(f"Weather TTS streaming error: {stream_error}")
                            logger.info("Weather data retrieved successfully despite streaming error")
                        return weather_response
                    
                except Exception as weather_error:
                    logger.error(f"Weather service error: {weather_error}")
                    # If weather service completely fails, fall back to normal LLM
                    fallback_prompt = f"The user asked about weather: {transcript}. Please provide a helpful response explaining that you couldn't get real-time weather data right now."
                    return await self._process_normal_llm_request(fallback_prompt, murf_service, client_websocket)
            
            # If not weather-related, use your EXISTING LLM processing
            else:
                return await self._process_normal_llm_request(transcript, murf_service, client_websocket)
                
        except Exception as e:
            logger.error(f"Error processing transcript for client streaming: {e}")
            raise

    async def _stream_text_directly(self, text_response: str, murf_service, client_websocket):
        """
        Helper method to stream final text response directly without LLM processing
        """
        try:
            # This mimics your existing streaming but with final text instead of LLM processing
            logger.info("Streaming weather response directly to client")
            
            # Send the text to Murf for TTS and stream to client
            # You might need to adjust this based on your actual Murf service methods
            # Send the text to Murf for TTS and stream to client
            try:
                await murf_service.stream_tts_to_client(text_response, client_websocket)
                logger.info("Weather response successfully streamed through Murf TTS")
            except Exception as murf_error:
                logger.error(f"Murf TTS streaming failed: {murf_error}")
                logger.warning("Weather response will be returned without audio streaming")
        except Exception as e:
            logger.error(f"Direct text streaming error: {e}")
            # Don't raise error, just log it - the weather response is still valid


    async def _process_normal_llm_request(self, transcript: str, murf_service=None, client_websocket=None) -> str:
        """
        Your ORIGINAL LLM processing logic - EXACTLY as it was before
        """
        try:
            # Create a conversational prompt (YOUR ORIGINAL CODE)
            prompt = f"""{ZODY_PERSONA}
    User: {transcript}
    """
            # Generate and stream the response WITH Murf integration (YOUR ORIGINAL CODE)
            return await self.generate_streaming_response(prompt, murf_service, client_websocket)
            
        except Exception as e:
            logger.error(f"Error in normal LLM processing: {e}")
            raise

    async def process_transcript_with_history_and_stream_to_client(
        self,
        user_transcript: str, 
        conversation_history: list,
        murf_service, 
        websocket
    ) -> str:
        """
        Process transcript with conversation history and stream audio response to client
        """
        logger.info(f"Processing transcript with {len(conversation_history)} messages in history")
        
        try:
            # Use conversation history instead of just the single message
            #llm_response = await get_llm_response_with_history(conversation_history)
            # llm_response = await process_transcript_and_stream_to_client(messages[-1]["content"], messages[:-1])
            
            # Build prompt from conversation history
            prompt = prompt = ZODY_PERSONA + "\n"
            for msg in conversation_history:
                role = msg.get("role", "user").capitalize()
                content = msg.get("content", "")
                prompt += f"{role}: {content}\n"
            prompt += f"User: {user_transcript}\n"
            
            llm_response = await self.generate_streaming_response(prompt, murf_service, websocket)
            logger.info(f"LLM Response: {llm_response[:100]}...")
            
            # Stream the response audio to the client
            await murf_service.stream_tts_to_client(llm_response, websocket)
            
            return llm_response
            
        except Exception as e:
            logger.error(f"Error in process_transcript_with_history_and_stream_to_client: {e}")
            raise e

    async def get_llm_response_with_history(conversation_history: list) -> str:
        """
        Get LLM response using full conversation history for context
        """
        try:
            # Format conversation history for your LLM API
            messages = []
            
            # Add system message
            messages.append({
                "role": "system",
                "content": ZODY_PERSONA 
            })
            
            # Add conversation history
            messages.extend(conversation_history)
            
            # Call your existing LLM service with the full conversation
            # REPLACE 'get_llm_response' with your actual LLM function name
            #llm_response = await process_transcript_and_stream_to_client(messages[-1]["content"], messages[:-1])
            llm_response = await get_llm_response_with_history(conversation_history)
            return llm_response
            
        except Exception as e:
            logger.error(f"Error getting LLM response with history: {e}")
            return "I apologize, I'm having trouble processing your request right now."   
    async def process_transcript_with_memory_and_stream(
        self, 
        user_transcript: str, 
        conversation_session_id: str, 
        murf_service=None, 
        client_websocket=None
    ) -> str:
        """
        NEW: Process transcript using conversation history for context + stream audio response
        This gives Zody memory of previous conversations!
        """
        try:
            logger.info(f"Processing transcript with memory for session: {conversation_session_id}")
            logger.info(f"User transcript: {user_transcript}")
            
            # Import chat_histories from main module
            import __main__
            if hasattr(__main__, 'chat_histories'):
                chat_histories = __main__.chat_histories
            else:
                # Fallback: create empty history
                chat_histories = {}
                logger.warning("chat_histories not found in main, using empty history")
            
            # Get or create conversation history for this session
            conversation_history = chat_histories.get(conversation_session_id, [])
            logger.info(f"Retrieved conversation history: {len(conversation_history)} messages")
            
            # Add current user message to history
            conversation_history.append({
                "role": "user",
                "content": user_transcript
            })
            
            # Build conversation context prompt
            conversation_prompt = f"{ZODY_PERSONA}\n\n"
            
            # Add conversation history to prompt
            if len(conversation_history) > 1:  # More than just current message
                conversation_prompt += "Previous conversation:\n"
                for msg in conversation_history[:-1]:  # All except current message
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    conversation_prompt += f"{role}: {content}\n"
                conversation_prompt += "\n"
            
            # Add current user message
            conversation_prompt += f"User: {user_transcript}\nAssistant:"
            
            logger.info(f"Generated conversation prompt with {len(conversation_history)} messages")
            
            # Generate streaming response using conversation context
            assistant_response = await self.generate_streaming_response(
                conversation_prompt, 
                murf_service, 
                client_websocket
            )
            
            # Add assistant response to conversation history
            conversation_history.append({
                "role": "assistant", 
                "content": assistant_response
            })
            
            # Update chat_histories with the new conversation
            chat_histories[conversation_session_id] = conversation_history
            logger.info(f"Updated conversation history: {len(conversation_history)} total messages")
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"Error in process_transcript_with_memory_and_stream: {e}")
            # Fallback to regular processing
            return await self.process_transcript_and_stream_to_client(
                user_transcript, murf_service, client_websocket
            )          