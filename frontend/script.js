// complete-voice-agent.js - Complete Voice Agent Implementation
console.log("✅ Complete Voice Agent loaded");
// ===== Backend URL Configuration =====
// Use your Render backend in production, fallback to localhost in dev
const BACKEND_URL = window.location.protocol === 'https:' ? "https://zody-voice-agent.onrender.com" : `${window.location.protocol}//${window.location.host}`;
// ===== Session Setup =====
let params = new URLSearchParams(window.location.search);
if (!params.has("session_id")) {
    params.set("session_id", Math.random().toString(36).slice(2));
    window.location.search = params.toString();
}
const sessionId = params.get("session_id");
console.log("💬 Session ID:", sessionId);

// ===== Global Variables =====
let conversationState = 'idle'; // idle, listening, processing, speaking, ending
let websocket = null;
let audioContext = null;
let isConversationActive = false;
let chatHistory = [];
let userApiKeys = {
    gemini: null,
    weather: null,
    murf: null,
    assemblyai: null
};

// Audio recording variables
let mediaRecorder = null;
let audioChunks = [];

// Audio playback variables
let audioPlaybackContext = null;
let audioPlayheadTime = 0;
let audioBufferQueue = [];
let bufferThreshold = 3;
let isBuffering = true;
let isAudioPlaying = false;
let wavHeaderProcessed = false;
const AUDIO_SAMPLE_RATE = 44100;

// ===== DOM Elements =====
let conversationBtn, statusDisplay, liveTranscript, transcriptText, chatMessages;

document.addEventListener("DOMContentLoaded", function() {
    console.log("🔄 DOM loaded, initializing complete voice agent...");
    
    // Get DOM elements
    conversationBtn = document.getElementById("conversation-btn");
    statusDisplay = document.getElementById("status-display");
    liveTranscript = document.getElementById("live-transcript");
    transcriptText = document.getElementById("transcript-text");
    chatMessages = document.getElementById("chat-messages");

    // Check if all elements exist
    console.log("🔍 Elements found:", {
        conversationBtn: !!conversationBtn,
        statusDisplay: !!statusDisplay,
        liveTranscript: !!liveTranscript,
        transcriptText: !!transcriptText,
        chatMessages: !!chatMessages
    });

    // Add main conversation button event listener
    conversationBtn.addEventListener("click", handleConversationButton);
// Initialize settings functionality
    initializeSettings();
    console.log("✅ Complete voice agent initialized");
});

// ===== Settings Management =====
function initializeSettings() {
    console.log("⚙️ Initializing settings...");
    
    // Load saved API keys from sessionStorage
    loadSavedApiKeys();
    
    // Get settings button and modal elements
    const settingsBtn = document.getElementById("settings-btn");
    const settingsModal = document.getElementById("settings-modal");
    const closeModal = document.getElementById("close-modal");
    const cancelModal = document.getElementById("cancel-modal");
    const saveKeys = document.getElementById("save-keys");
    const clearKeys = document.getElementById("clear-keys");
    
    // Add event listeners
    if (settingsBtn) {
        settingsBtn.addEventListener("click", openSettingsModal);
    }
    
    if (closeModal) {
        closeModal.addEventListener("click", closeSettingsModal);
    }
    
    if (cancelModal) {
        cancelModal.addEventListener("click", closeSettingsModal);
    }
    
    if (saveKeys) {
        saveKeys.addEventListener("click", saveApiKeys);
    }
    
    if (clearKeys) {
        clearKeys.addEventListener("click", clearApiKeys);
    }
    
    // Close modal when clicking outside
    if (settingsModal) {
        settingsModal.addEventListener("click", function(e) {
            if (e.target === settingsModal) {
                closeSettingsModal();
            }
        });
    }
    
    console.log("✅ Settings initialized");
}

function loadSavedApiKeys() {
    try {
        const savedKeys = sessionStorage.getItem('userApiKeys');
        if (savedKeys) {
            userApiKeys = JSON.parse(savedKeys);
            console.log("📝 Loaded saved API keys from session");
        }
    } catch (error) {
        console.log("⚠️ No saved API keys found");
    }
}

function openSettingsModal() {
    console.log("⚙️ Opening settings modal...");
    
    const modal = document.getElementById("settings-modal");
    
    // Populate current values
    document.getElementById("gemini-key").value = userApiKeys.gemini || '';
    document.getElementById("weather-key").value = userApiKeys.weather || '';
    document.getElementById("murf-key").value = userApiKeys.murf || '';
    document.getElementById("assemblyai-key").value = userApiKeys.assemblyai || '';
    
    modal.classList.add("active");
}

function closeSettingsModal() {
    const modal = document.getElementById("settings-modal");
    modal.classList.remove("active");
}

function saveApiKeys() {
    console.log("💾 Saving API keys...");
    
    // Get values from inputs
    const geminiKey = document.getElementById("gemini-key").value.trim();
    const weatherKey = document.getElementById("weather-key").value.trim();
    const murfKey = document.getElementById("murf-key").value.trim();
    const assemblyaiKey = document.getElementById("assemblyai-key").value.trim();
    
    // Update userApiKeys object
    userApiKeys = {
        gemini: geminiKey || null,
        weather: weatherKey || null,
        murf: murfKey || null,
        assemblyai: assemblyaiKey || null
    };
    
    // Save to sessionStorage
    try {
        sessionStorage.setItem('userApiKeys', JSON.stringify(userApiKeys));
        console.log("✅ API keys saved to session storage");
        
        // Show success message
        updateStatus("✅ API keys saved successfully!");
        
        // Close modal
        closeSettingsModal();
        
        // Reset status after 3 seconds
        setTimeout(() => {
            if (conversationState === 'idle') {
                updateStatus("Ready to start your conversation with AI...");
            }
        }, 3000);
        
    } catch (error) {
        console.error("❌ Error saving API keys:", error);
        updateStatus("❌ Error saving API keys");
    }
}

function clearApiKeys() {
    console.log("🗑️ Clearing API keys...");
    
    // Clear the object
    userApiKeys = {
        gemini: null,
        weather: null,
        murf: null,
        assemblyai: null
    };
    
    // Clear sessionStorage
    sessionStorage.removeItem('userApiKeys');
    
    // Clear input fields
    document.getElementById("gemini-key").value = '';
    document.getElementById("weather-key").value = '';
    document.getElementById("murf-key").value = '';
    document.getElementById("assemblyai-key").value = '';
    
    updateStatus("🗑️ All API keys cleared!");
    
    console.log("✅ API keys cleared");
}

// ===== Main Conversation Button Handler =====
function handleConversationButton() {
    console.log("🎯 Conversation button clicked, current state:", conversationState);
    
    if (conversationState === 'idle') {
        startConversation();
    } else if (conversationState === 'listening' || conversationState === 'processing' || conversationState === 'speaking') {
        endConversation();
    }
    // Remove the intermediate click behavior - let it flow automatically
}

// ===== Start Conversation =====
async function startConversation() {
    console.log("🎤 Starting conversation...");
    
    try {
        conversationState = 'listening';
        isConversationActive = true;
        
        // Only clear chat history on first conversation, not on subsequent turns
        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
            chatHistory = [];
            clearChatDisplay();
            
            // Update UI
            updateButtonState();
            updateStatus("🔌 Connecting to AI...");
            
            // Connect to WebSocket only if not already connected
            await connectToLLMWebSocket();
        } else {
            // WebSocket already connected, just update UI for next turn
            updateButtonState();
            updateStatus("🎤 Listening... Speak now!");
            showLiveTranscript();
            
            // Ensure audio recording is active
            if (audioContext && audioContext.state === 'suspended') {
                await audioContext.resume();
            }
        }
        
    } catch (error) {
        console.error("❌ Error starting conversation:", error);
        updateStatus(`❌ Error: ${error.message}`);
        resetToIdle();
    }
}

// ===== Connect to LLM WebSocket =====
async function connectToLLMWebSocket() {
    console.log("🔌 Connecting to LLM WebSocket...");
    
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.protocol === 'https:' ? 'zody-voice-agent.onrender.com' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/llm-stream`;
    console.log("🔌 WebSocket URL:", wsUrl);
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = async () => {
        console.log("✅ WebSocket connected");
        
        // Send user API keys if available
        if (userApiKeys.gemini || userApiKeys.weather || userApiKeys.murf || userApiKeys.assemblyai) {
            console.log("📤 Sending user API keys to server...");
            const configMessage = {
                type: "user_api_keys",
                keys: userApiKeys,
                session_id: sessionId
            };
            websocket.send(JSON.stringify(configMessage));
        }
        
        updateStatus("🎤 Requesting microphone access...");
        await setupAudioRecording();
    };
    
    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    websocket.onclose = (event) => {
        console.log("❌ WebSocket closed:", event);
        if (isConversationActive) {
            updateStatus("❌ Connection lost");
            resetToIdle();
        }
    };
    
    websocket.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        updateStatus("❌ Connection error");
        resetToIdle();
    };
}

// ===== Setup Audio Recording =====
async function setupAudioRecording() {
    console.log("🎤 Setting up audio recording...");
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });
        
        console.log("✅ Microphone access granted");
        
        // Create audio context for real-time processing
        audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 16000
        });
        
        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(4096, 1, 1);
        
        processor.onaudioprocess = (event) => {
            if (conversationState !== 'listening') return;
            
            const inputData = event.inputBuffer.getChannelData(0);
            const outputData = new Int16Array(inputData.length);
            
            // Convert float32 to int16
            for (let i = 0; i < inputData.length; i++) {
                outputData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
            }
            
            // Send audio data to WebSocket
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(outputData.buffer);
            }
        };
        
        source.connect(processor);
        processor.connect(audioContext.destination);
        
        // Update UI for listening state
        updateStatus("🎤 Listening... Speak now!");
        showLiveTranscript();
        updateButtonState();
        
        console.log("✅ Audio recording setup complete");
        
    } catch (error) {
        console.error('❌ Error accessing microphone:', error);
        updateStatus("❌ Microphone access denied");
        resetToIdle();
    }
}

// ===== Handle WebSocket Messages =====
function handleWebSocketMessage(data) {
    console.log('📨 WebSocket message:', data.type, data);
    
    switch (data.type) {
        case 'connection':
            updateStatus("✅ Connected! Start speaking...");
            break;
            
        case 'session_opened':
            console.log('🟢 Session opened');
            updateStatus("🎤 Session ready - start speaking!");
            break;
            
        case 'transcript':
            handleTranscriptMessage(data);
            break;
            
        case 'turn_complete':
            handleTurnComplete(data);
            break;
            
        case 'chat_started':
            handleChatStarted(data);
            break;
            
        case 'audio_chunk':
            handleAudioChunk(data);
            break;
            
        case 'llm_response_complete':
            handleLLMResponseComplete(data);
            break;
            
        case 'chat_complete':
            handleChatComplete(data);
            break;
            
        case 'error':
            console.error('❌ WebSocket error:', data.message);
            updateStatus(`❌ Error: ${data.message}`);
            break;
         
        case 'audio_complete':
            handleAudioComplete(data);
            break;    

        case 'conversation_ended':
            console.log('👋 Conversation ended gracefully');
            updateStatus("👋 Thank you for the conversation!");
        // Let the timeout in endConversation handle the final cleanup
            break;
        
        default:
            console.log('ℹ️ Unknown message type:', data.type, data);
    }
}

// ===== Handle Live Transcript =====
function handleTranscriptMessage(data) {
    console.log('📝 Live transcript:', data.text);
    
    if (conversationState === 'listening') {
        updateLiveTranscript(data.text);
        updateStatus("💂 Listening... (keep speaking)");
    }
}

// ===== Handle Turn Complete =====
function handleTurnComplete(data) {
    console.log('🎯 Turn complete:', data.final_transcript);
    
    conversationState = 'processing';
    updateButtonState();
    updateStatus("🤖 Processing your message...");
    hideLiveTranscript();
    
    // Add user message to chat history
    addMessageToChat('user', data.final_transcript);
}

// ===== Handle Chat Started =====
function handleChatStarted(data) {
    console.log('🤖 Chat started:', data.user_message);
    updateStatus(`🤖 AI is thinking about: "${data.user_message.substring(0, 30)}..."`);
    
    // Initialize audio playback for the response
    initializeAudioPlayback();
}

// ===== Handle Audio Chunk =====
function handleAudioChunk(data) {
    console.log('🎵 Audio chunk received:', data.chunk_index);
    
    if (conversationState !== 'speaking') {
        conversationState = 'speaking';
        updateButtonState();
        updateStatus("🔊 AI is speaking...");
    }
    
    const base64Audio = data.audio_data;
    const pcmData = base64ToPCMFloat32(base64Audio);
    
    if (pcmData && pcmData.length > 0) {
        audioBufferQueue.push(pcmData);
        
        // Start playback when we have enough chunks buffered
        if (isBuffering && audioBufferQueue.length >= bufferThreshold) {
            console.log("🎵 Buffer threshold reached - starting playback");
            isBuffering = false;
            isAudioPlaying = true;
            startBufferedPlayback();
        }
        // Continue adding chunks if already playing
        else if (!isBuffering && audioBufferQueue.length > 0) {
            processBufferedChunks();
        }
    }
    // Add enhanced completion detection
    if (!isAudioPlaying) {
        isAudioPlaying = true;
        
        // Set a safety timeout to ensure we don't get stuck
        setTimeout(() => {
            if (conversationState === 'speaking' && isConversationActive) {
                console.log("🔧 Safety timeout - forcing return to listening");
                handleAudioComplete({total_chunks: audioBufferQueue.length + 1});
            }
        }, 15000); // 15 second safety timeout
    }
}

// ===== Handle LLM Response Complete =====
function handleLLMResponseComplete(data) {
    console.log('🤖 LLM response complete:', data.llm_response);
    
    // Add AI message to chat history
    addMessageToChat('ai', data.llm_response);
}

// ===== Handle Chat Complete =====
function handleChatComplete(data) {
    console.log('✅ Chat complete - waiting for audio to finish');
    
    // FIXED: Don't automatically transition - let handleAudioComplete do it
    // Just reset audio playback state for next turn
    resetAudioPlaybackState();
    
    // Ensure audio recording is ready for next turn
    if (audioContext && audioContext.state === 'suspended') {
        audioContext.resume().then(() => {
            console.log("🎤 Audio context resumed for next turn");
        });
    }
}

function handleAudioComplete(data) {
    console.log('✅ Audio streaming complete:', data.total_chunks, 'chunks');
    
    // Process any remaining buffered chunks
    if (audioBufferQueue.length > 0) {
        console.log(`🎵 Processing final ${audioBufferQueue.length} buffered chunks`);
        processBufferedChunks();
    }
    
    // Update status to show audio is finishing
    updateStatus("🔊 AI finishing response...");
    
    // FIXED: Wait for actual audio playback to finish, then transition to listening
    const estimatedPlaybackTime = data.total_chunks * 1000; // Rough estimate
    const waitTime = Math.max(2000, Math.min(estimatedPlaybackTime, 5000)); // 2-5 seconds
    
    setTimeout(() => {
        // Reset audio state
        isBuffering = true;
        isAudioPlaying = false;
        
        // CRITICAL FIX: Automatically return to listening state
        if (isConversationActive && conversationState === 'speaking') {
            conversationState = 'listening';
            updateButtonState();
            updateStatus("🎤 Ready for your next message... (speak anytime)");
            showLiveTranscript();
            
            console.log("🎵 Audio completed - automatically returned to listening");
        }
    }, waitTime);
}


// ===== End Conversation =====
function endConversation() {
    console.log("🛑 Ending conversation...");
    
    conversationState = 'ending';
    isConversationActive = false;
    updateButtonState();
    updateStatus("👋 AI saying goodbye...");
    
    // Send goodbye command to trigger AI farewell
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const goodbyeMessage = {
            type: "end_conversation",
            session_id: sessionId
        };
        websocket.send(JSON.stringify(goodbyeMessage));
    }
    
    // Close connections after a longer delay to allow goodbye audio
    setTimeout(() => {
        closeConnections();
        resetToIdle();
        updateStatus("👋 Conversation ended. Click to start a new one!");
    }, 8000); // Longer delay for goodbye message
}

// ===== Close Connections =====
function closeConnections() {
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    
    if (websocket) {
        websocket.close();
        websocket = null;
    }
    
    if (audioPlaybackContext) {
        audioPlaybackContext.close();
        audioPlaybackContext = null;
    }
}

// ===== Reset to Idle State =====
function resetToIdle() {
    conversationState = 'idle';
    isConversationActive = false;
    updateButtonState();
    hideLiveTranscript();
    closeConnections();
}

// ===== Update Button State =====
function updateButtonState() {
    conversationBtn.className = 'conversation-button';
    
    switch (conversationState) {
        case 'idle':
            conversationBtn.classList.add('btn-idle');
            conversationBtn.textContent = '🎙️ Start Conversation';
            break;
        case 'listening':
            conversationBtn.classList.add('btn-listening');
            conversationBtn.textContent = '🛑 End Conversation'; // Changed text
            break;
        case 'processing':
            conversationBtn.classList.add('btn-processing');
            conversationBtn.textContent = '🛑 End Conversation'; // Changed text
            break;
        case 'speaking':
            conversationBtn.classList.add('btn-speaking');
            conversationBtn.textContent = '🛑 End Conversation'; // Changed text
            break;
        case 'ending':
            conversationBtn.classList.add('btn-ending');
            conversationBtn.textContent = '👋 Ending...';
            break;
    }
}

// ===== Update Status =====
function updateStatus(message) {
    statusDisplay.textContent = message;
}

// ===== Show/Hide Live Transcript =====
function showLiveTranscript() {
    liveTranscript.classList.add('active');
    transcriptText.textContent = 'Listening...';
}

function hideLiveTranscript() {
    liveTranscript.classList.remove('active');
}

function updateLiveTranscript(text) {
    transcriptText.textContent = text;
}

// ===== Chat History Management =====
function addMessageToChat(sender, message) {
    // Remove empty state if present
    const emptyState = chatMessages.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    messageDiv.innerHTML = `
        <div class="message-label">${sender === 'user' ? 'You' : 'AI Assistant'}:</div>
        <div class="message-text">${message}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Update chat history array
    chatHistory.push({
        sender: sender,
        message: message,
        timestamp: new Date()
    });
    
    console.log(`💬 Added ${sender} message to chat:`, message.substring(0, 50));
}

function clearChatDisplay() {
    chatMessages.innerHTML = '<div class="empty-state">Starting new conversation...</div>';
}

// ===== Audio Playback Functions =====
    function initializeAudioPlayback() {
        try {
            // FIXED: Always create a new context for playback if it doesn't exist
            if (!audioPlaybackContext || audioPlaybackContext.state === 'closed') {
                audioPlaybackContext = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: AUDIO_SAMPLE_RATE
                });
                console.log("🎵 New audio playback context created");
            }
            
            // Resume if suspended
            if (audioPlaybackContext.state === 'suspended') {
                audioPlaybackContext.resume().then(() => {
                    console.log("🎵 Audio context resumed");
                });
            }
            
            resetAudioPlaybackState();
            
            console.log("🎵 Audio playback initialized successfully");
            
        } catch (error) {
            console.error("Failed to initialize audio context:", error);
            
            // Try fallback with default sample rate
            try {
                audioPlaybackContext = new (window.AudioContext || window.webkitAudioContext)();
                console.log("🎵 Fallback audio context created");
            } catch (fallbackError) {
                console.error("Fallback audio context also failed:", fallbackError);
            }
        }
    }

function resetAudioPlaybackState() {
    audioPlayheadTime = audioPlaybackContext ? audioPlaybackContext.currentTime + 0.1 : 0;
    audioBufferQueue = [];
    isBuffering = true;
    isAudioPlaying = false;
    wavHeaderProcessed = false;
}

function base64ToPCMFloat32(base64Audio) {
    try {
        const binary = atob(base64Audio);
        const offset = wavHeaderProcessed ? 0 : 44;
        if (!wavHeaderProcessed) {
            console.log("🎵 Skipping WAV header from first chunk");
            wavHeaderProcessed = true;
        }
        
        const length = binary.length - offset;
        const buffer = new ArrayBuffer(length);
        const byteArray = new Uint8Array(buffer);
        
        for (let i = 0; i < length; i++) {
            byteArray[i] = binary.charCodeAt(i + offset);
        }
        
        const view = new DataView(byteArray.buffer);
        const sampleCount = length / 2;
        const float32Array = new Float32Array(sampleCount);
        
        for (let i = 0; i < sampleCount; i++) {
            const int16 = view.getInt16(i * 2, true);
            float32Array[i] = int16 / 32768.0;
        }
        
        return float32Array;
    } catch (error) {
        console.error("❌ Error converting base64 to PCM:", error);
        return null;
    }
}

function startBufferedPlayback() {
    // FIXED: Ensure context exists before checking state
    if (!audioPlaybackContext) {
        console.error("Audio context is null - reinitializing");
        initializeAudioPlayback();
        return;
    }
    
    if (audioPlaybackContext.state === 'suspended') {
        audioPlaybackContext.resume().then(() => {
            processBufferedChunks();
        });
    } else {
        processBufferedChunks();
    }
}
function processBufferedChunks() {
    const chunksToProcess = Math.min(audioBufferQueue.length, 5);
    
    for (let i = 0; i < chunksToProcess; i++) {
        const chunk = audioBufferQueue.shift();
        scheduleChunkAtPlayhead(chunk);
    }
    
    console.log(`🎵 Processed ${chunksToProcess} chunks, ${audioBufferQueue.length} remaining`);
}

function scheduleChunkAtPlayhead(chunk) {
    try {
        // FIXED: Check if context exists
        if (!audioPlaybackContext || audioPlaybackContext.state === 'closed') {
            console.error("Audio context unavailable for chunk scheduling");
            return;
        }
        
        const buffer = audioPlaybackContext.createBuffer(1, chunk.length, AUDIO_SAMPLE_RATE);
        buffer.copyToChannel(chunk, 0);
        
        const source = audioPlaybackContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioPlaybackContext.destination);
        
        const now = audioPlaybackContext.currentTime;
        if (audioPlayheadTime <= now) {
            audioPlayheadTime = now + 0.01;
        }
        
        source.start(audioPlayheadTime);
        audioPlayheadTime += buffer.duration;
        
        console.log(`🎵 Scheduled chunk at ${audioPlayheadTime.toFixed(3)}s, duration: ${buffer.duration.toFixed(3)}s`);
        
    } catch (error) {
        console.error("Error scheduling chunk:", error);
    }
}