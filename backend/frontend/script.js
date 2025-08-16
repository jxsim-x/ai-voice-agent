// script.js
console.log("✅ script.js loaded");
// ===== Day 10 Session Setup =====
let params = new URLSearchParams(window.location.search);
if (!params.has("session_id")) {
    // Generate random session id and reload page
    params.set("session_id", Math.random().toString(36).slice(2));
    window.location.search = params.toString();
}
const sessionId = params.get("session_id");
console.log("💬 Session ID:", sessionId);
const echoStatus = document.getElementById("echo-status");

// Flag to switch between day9 and day10 mode
const DAY10_MODE = true; // set false to use old /llm/query endpoint

//
// Simple text-to-murf button (kept from original)
//
/*
document.getElementById("generateBtn").addEventListener("click", async () => {
  const text = document.getElementById("textInput").value;
  const statusMsg = document.getElementById("statusMsg");
  const audioPlayer = document.getElementById("audioPlayer");

  if (!text.trim()) {
    statusMsg.innerText = "Please enter some text!";
    return;
  }

  statusMsg.innerText = "Generating voice... 🔄";
  audioPlayer.style.display = "none";

  try {
    const response = await fetch("/generate-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await response.json();
    if (data.audio_url) {
      statusMsg.innerText = "✅ Generated! Click below to play.";
      audioPlayer.src = data.audio_url;
      audioPlayer.style.display = "block";
    } else {
      statusMsg.innerText = "❌ Failed to generate audio.";
      console.error("generate-audio returned:", data);
    }
  } catch (err) {
    statusMsg.innerText = "⚠️ Error contacting backend.";
    console.error(err);
  }
});
*/
//
// Recording + workflow logic
//

let mediaRecorder = null;
let audioChunks = [];
let recordedBlob = null;

// const startBtn = document.getElementById("start-recording");
// const stopBtn = document.getElementById("stop-recording");

async function startRecording() {
  echoStatus.innerText = "🎤 Requesting microphone...";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: "audio/webm" });
      audioChunks = [];
      sendAudio(recordedBlob); // send automatically after stop
    };

    mediaRecorder.start();
    echoStatus.innerText = "🎤 Recording...";
  } catch (err) {
    console.error("getUserMedia error:", err);
    echoStatus.innerText = "❌ Microphone access denied or error.";
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
}


document.addEventListener("DOMContentLoaded", () => {
    const recordBtn = document.getElementById("record-toggle-btn");
    let isRecording = false;

    recordBtn.addEventListener("click", () => {
        if (!isRecording) {
            startRecording();
            recordBtn.textContent = "🛑 Stop Recording";
            isRecording = true;
        } else {
            stopRecording();
            recordBtn.textContent = "🎙️ Start Recording";
            isRecording = false;
        }
    });
});

/*
const echoAudio = document.getElementById("echo-audio");
const echoStatus = document.getElementById("echo-status");
const sendToWorkflowBtn = document.getElementById("send-to-llm");
sendToWorkflowBtn.disabled = true; // disabled until we have a recording
*/ 
/*startBtn.addEventListener("click", async () => {
  echoStatus.innerText = "🎤 Requesting microphone...";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      // build final blob
      recordedBlob = new Blob(audioChunks, { type: "audio/webm" });
      audioChunks = [];

      // preview locally
      echoAudio.src = URL.createObjectURL(recordedBlob);
      echoAudio.style.display = "block";

      echoStatus.innerText = "Recorded — click 'Send to Workflow' to process.";
      sendToWorkflowBtn.disabled = false;
    };

    mediaRecorder.start();
    echoStatus.innerText = "🎤 Recording...";
    startBtn.disabled = true;
    stopBtn.disabled = false;
  } catch (err) {
    console.error("getUserMedia error:", err);
    echoStatus.innerText = "❌ Microphone access denied or error.";
  }
});

stopBtn.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  startBtn.disabled = false;
  stopBtn.disabled = true;
});
*/
async function sendAudio(blob) {
  console.log("🎤 Blob passed:", blob);

  if (!blob) {
    alert("No recording available. Please record first.");
    return;
  }

  echoStatus.innerText = "🤖 Sending to LLM & Murf...";
  //sendToWorkflowBtn.disabled = true;

  const formData = new FormData();
  formData.append("file", blob, "recording.webm");

  // Choose endpoint based on mode
  const endpoint = DAY10_MODE
    ? `/agent/chat/${sessionId}`
    : `/llm/query`;
  console.log("🌐 Sending to:", endpoint);

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const txt = await res.text();
      echoStatus.innerText = `❌ Server error: ${res.status}`;
      console.error("Server error body:", txt);
      //sendToWorkflowBtn.disabled = false;
      return;
    }

    const data = await res.json();
    console.log("Server response:", data);

    const out = document.getElementById("llm-response-text");

    // === If backend sent error ===
    if (data.error) {
      if (out) {
        out.value += `LLM (error): I'm having trouble connecting right now.\n⚠️ Fallback used due to error\n`;
        out.scrollTop = out.scrollHeight;
      }
      // Play fallback audio if exists
      if (data.audio_url) {
        const llmAudio = document.getElementById("llm-response-audio");
        llmAudio.src = data.audio_url;
        llmAudio.style.display = "none";
        try {
          await llmAudio.play();
        } catch (err) {
          console.warn("Autoplay blocked", err);
        }
      }
      echoStatus.innerText = "⚠️ Fallback used due to error.";
      return; // Stop normal flow
    }

    // === Normal flow ===
    // Show transcription if available
    if (data.transcription) {
      const tbox = document.getElementById("transcription-text");
      if (tbox) tbox.value = data.transcription;
    }

    // Append chat log
    if (out) {
      let userLine = data.transcription ? `You: ${data.transcription}\n` : "";
      let llmLine = data.text ? `LLM: ${data.text}\n` : "";
      out.value += userLine + llmLine;
      out.scrollTop = out.scrollHeight;
    }

    // Play Murf audio
    if (data.audio_url) {
      const llmAudio = document.getElementById("llm-response-audio");
      llmAudio.src = data.audio_url;
      llmAudio.style.display = "block";
      try {
        await llmAudio.play();
      } catch (err) {
        console.warn("Autoplay blocked", err);
      }

      // Auto-record next input
      if (DAY10_MODE) {
        llmAudio.onended = () => {
          console.log("🎬 LLM finished speaking — starting next recording...");
          startBtn.click();
        };
      }
    }

    echoStatus.innerText = "✅ Response ready.";
  } catch (err) {
    console.error("sendAudio error:", err);
    echoStatus.innerText = "❌ Error sending to LLM.";

    // Append error message to chat log
    const out = document.getElementById("llm-response-text");
    if (out) {
      out.value += `LLM: I'm having trouble connecting right now (network issue)\n`;
      out.scrollTop = out.scrollHeight;
    }

  // Play local fallback audio if available
    const llmAudio = document.getElementById("llm-response-audio");
    llmAudio.src = "/fallback.mp3"; // Ensure this file exists in your frontend/static
    llmAudio.style.display = "block";
    try {
      await llmAudio.play();
    } catch (err) {
      console.warn("Autoplay blocked for fallback audio", err);
    }
  } finally {
    //sendToWorkflowBtn.disabled = false;
  }
}
/*
sendToWorkflowBtn.addEventListener("click", () => {
  console.log("🚀 Send button clicked");
  sendAudio(recordedBlob);
});
*/
// Now sending happens automatically when recording stops
async function onRecordingStop() {
  console.log("🚀 Recording stopped, sending to LLM...");
  await sendAudio(recordedBlob);
}
