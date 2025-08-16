// script.js
console.log("✅ script.js loaded");

//
// Simple text-to-murf button (kept from original)
//
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

//
// Recording + workflow logic
//

let mediaRecorder = null;
let audioChunks = [];
let recordedBlob = null;

const startBtn = document.getElementById("start-recording");
const stopBtn = document.getElementById("stop-recording");
const echoAudio = document.getElementById("echo-audio");
const echoStatus = document.getElementById("echo-status");
const sendToWorkflowBtn = document.getElementById("send-to-llm");
sendToWorkflowBtn.disabled = true; // disabled until we have a recording

startBtn.addEventListener("click", async () => {
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

async function sendAudioToLLM(blob) {
  if (!blob) {
    alert("No recording available. Please record first.");
    return;
  }

  echoStatus.innerText = "🤖 Sending to LLM & Murf...";
  sendToWorkflowBtn.disabled = true;

  const formData = new FormData();
  // choose a sensible filename extension to help ffmpeg/inference server
  formData.append("file", blob, "recording.webm");

  try {
    const res = await fetch("/llm/query", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const txt = await res.text();
      echoStatus.innerText = `❌ Server error: ${res.status}`;
      console.error("Server error body:", txt);
      sendToWorkflowBtn.disabled = false;
      return;
    }

    const data = await res.json();
    console.log("LLM+Murf response:", data);

    // show transcription (if present) and LLM text
    if (data.transcription) {
      const tbox = document.getElementById("transcription-text");
      if (tbox) tbox.value = data.transcription;
    }

    const llmText = data.text || "";
    const out = document.getElementById("llm-response-text");
    if (out) out.value = llmText;

    if (data.audio_url) {
      const llmAudio = document.getElementById("llm-response-audio");
      llmAudio.src = data.audio_url;
      llmAudio.style.display = "block";
      try {
        await llmAudio.play();
      } catch (err) {
        console.warn("Autoplay blocked", err);
      }
    }

    echoStatus.innerText = "✅ Response ready.";
  } catch (err) {
    console.error("sendAudioToLLM error:", err);
    echoStatus.innerText = "❌ Error sending to LLM.";
  } finally {
    sendToWorkflowBtn.disabled = false;
  }
}

sendToWorkflowBtn.addEventListener("click", () => {
  console.log("🚀 Send button clicked");
  sendAudio(recordedBlob);
});



