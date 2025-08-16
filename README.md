# 🎙️ 30 Days of Voice Agents Challenge

Welcome to my **30 Days of Voice Agents** journey — a hands-on challenge to build a fully functional, voice-powered conversational AI from scratch.  
Over the span of this project, a simple webpage evolves into an advanced, **context-aware voice agent** capable of natural, back-and-forth conversations.

-----

## 🤖 About The Project

This application enables **real-time, voice-to-voice conversations** with an AI powered by **Google Gemini LLM**.  
It remembers your session context, allowing for smooth follow-up questions and more **human-like interaction**.



-----

### ✨ Key Features

* **🎤 Voice-to-Voice Interaction** – Speak naturally to the agent and hear instant, high-quality spoken responses.
* **🧠 Contextual Conversations** – Maintains chat history per session to handle follow-ups intelligently.
* **🔗 End-to-End AI Pipeline** – Integrates multiple AI services for a smooth `Speech-to-Text → LLM → Text-to-Speech` flow.
* **🎨 Modern & Intuitive UI** – A single interactive button with live visual feedback for different states (`ready`, `recording`, `thinking`).
* **🛡️ Robust Error Handling** – Fallback audio ensures uninterrupted interaction even if an API call fails.

-----

## 🛠️ Tech Stack

**Backend**  
* **FastAPI** – High-performance, asynchronous Python API framework.  
* **Uvicorn** – ASGI server for running FastAPI.  
* **Python-Dotenv** – Secure environment variable management.

**Frontend**  
* **HTML, CSS, JavaScript** – Lightweight and responsive client interface.  
* **Bootstrap** – Modern UI components and responsive grid system.  
* **MediaRecorder API** – Captures audio from the user’s microphone directly in the browser.

**AI & Voice APIs**  
* **Murf AI** – High-quality, natural-sounding Text-to-Speech (TTS).  
* **AssemblyAI** – Fast, accurate Speech-to-Text (STT) transcription.  
* **Google Gemini** – Context-aware text generation via LLM.

-----

## ⚙️ Architecture

The application follows a **client–server architecture**:

1. **Client** records audio via the **MediaRecorder API**.  
2. Audio is sent to the **FastAPI backend**.  
3. Backend sends audio to **AssemblyAI** for transcription (STT).  
4. Transcribed text + chat history → **Google Gemini LLM** → generates a response.  
5. LLM’s text → **Murf AI** → converts to speech (TTS).  
6. Backend returns the audio URL to the **client**.  
7. **Client** plays the received audio, and the cycle continues.

-----

## 🚀 Getting Started

### Prerequisites

* Python 3.8+  
* An IDE (e.g., VS Code)  
* API keys for:
    * Murf AI  
    * AssemblyAI  
    * Google Gemini  

### Installation & Running the App

1. **Clone the repository**
    ```sh
    git clone https://github.com/jxsim-x/ai-voice-agent.git
    ```

2. **Install dependencies** from `requirements.txt`
    ```sh
    pip install -r requirements.txt
    ```

3. **Create a `.env` file** in the chosen day's directory
    ```env
    MURF_API_KEY="your_murf_api_key_here"
    ASSEMBLYAI_API_KEY="your_assemblyai_api_key_here"
    GEMINI_API_KEY="your_gemini_api_key_here"
    ```

4. **Run the FastAPI server** with hot reloading
    ```sh
    uvicorn main:app --reload
    ```

5. **Open your browser**  
    Visit `http://localhost:8000`, grant microphone permissions, and start conversing!

-----

## 🗓️ Project Journey: Day 1 to 13

* **Day 01** – Basic **FastAPI server** + **Bootstrap UI**.  
* **Day 02** – `/tts` endpoint using **Murf AI**.  
* **Day 03** – Frontend for TTS testing.  
* **Day 04** – Client-side Echo Bot with `MediaRecorder` API.  
* **Day 05** – Server-side audio upload support.  
* **Day 06** – Added **AssemblyAI** STT integration.  
* **Day 07** – Voice transformation bot (STT → TTS).  
* **Day 08** – Integrated **Google Gemini LLM** for intelligent responses.  
* **Day 09** – Full **voice-to-voice conversational loop**.  
* **Day 10** – Implemented chat history for context-aware conversations.  
* **Day 11** – Robust error handling + fallback audio.  
* **Day 12** – UI revamp with a single interactive record button.  
* **Day 13** – Comprehensive README documentation.

## 🗓️ Project Journey: Day 1 to 13

Here is a summary of the progress made during the first 13 days of the challenge.

  * **Day 01**: Laid the foundation with a basic **FastAPI server** and a simple **Bootstrap UI**.
  * **Day 02**: Integrated the **Murf AI API** to create the first endpoint for Text-to-Speech (TTS).
  * **Day 03**: Built the **frontend interface** to interact with the TTS endpoint, allowing users to type text and hear it spoken.
  * **Day 04**: Developed a client-side **Echo Bot** using the `MediaRecorder` API to record and play back user audio.
  * **Day 05**: Enhanced the echo bot by implementing **server-side audio upload**, moving from client-only to a client-server model.
  * **Day 06**: Integrated the **AssemblyAI API** for Speech-to-Text (STT), allowing the server to transcribe user audio.
  * **Day 07**: Created a **voice transformation bot** by chaining the STT and TTS services. The app would listen, transcribe, and speak the user's words back in a different voice.
  * **Day 08**: Introduced intelligence by integrating the **Google Gemini LLM**, creating an endpoint that could generate text-based responses to queries.
  * **Day 09**: Achieved a full **voice-to-voice conversational loop**. The app could now listen to a spoken question and provide a spoken answer generated by the LLM.
  * **Day 10**: Implemented **chat history** and session management, giving the agent a "memory" to hold context-aware conversations.
  * **Day 11**: Made the application more robust by adding **server-side and client-side error handling**, including a friendly fallback audio message for API failures.
  * **Day 12**: Performed a major **UI revamp**, simplifying the interface to a single, animated record button and a cleaner, more modern aesthetic.
  * **Day 13**: Focused on **documentation**, creating this comprehensive `README.md` file to explain the project's architecture, features, and setup.
