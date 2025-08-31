# 🤖 Zody – Your Humourous AI Robot Companion  

![Build](https://img.shields.io/badge/build-passing-brightgreen)  
![Made with](https://img.shields.io/badge/Made%20with-FastAPI-009688)  
![Challenge](https://img.shields.io/badge/30Days-Voice%20Agents-orange)  

---

## 🗣️ Tagline  
**"Talk. Ask. Discover. Zody listens, understands, and speaks back in real-time."**

---

## 📖 Description  
Zody is a fully functional **conversational AI voice agent** built in just **30 days**.  
It listens to your voice, detects when you finish speaking, and then uses:  

- 🎙️ **AssemblyAI** → Transcription & Turn Detection  
- 🧠 **Gemini 2.5 Flash** → Conversational Intelligence  
- 🎵 **Murf AI** → Natural Voice Responses  

With **real-time streaming playback**, Zody gives a seamless back-and-forth conversation.  
It also comes with smart skills like **Weather Forecasting** powered by **Visual Crossing API**.  

---

## 🌍 Demo & Deployment  
- **Hosted App** → [Zody on Render](https://zody-voice-agent.onrender.com)  

📸 **Screenshots & Proofs** (place your files here later):  
- ![UI Screenshot](docs/images/ui.png) *(Premium beige theme with golden text ✨)*  
- ![Conversation Demo GIF](docs/images/demo.gif)   

---

## 🛠️ Tech Stack  

**Backend** → Python, FastAPI, WebSockets, Uvicorn, Gunicorn  
**Frontend** → HTML, CSS, JavaScript (Premium beige + golden UI)  
**AI/ML Services**:  
- AssemblyAI → Speech-to-Text (Realtime + Turn Detection)  
- Gemini 2.5 Flash (Google Generative AI) → Conversational LLM  
- Murf AI → Text-to-Speech (Streaming Voice Synthesis)  

**APIs**: Visual Crossing Weather API  
**Audio Processing**: Pydub  
**Utilities**: python-dotenv, logging, cleanup scripts  

---

## ⚙️ Installation / Setup (Local Development)  

```bash
# Clone the Repository
git clone https://github.com/<your-username>/zody-voice-agent.git
cd zody-voice-agent

# Create a Virtual Environment & Activate
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
.venv\Scripts\activate      # Windows

# Install Dependencies
pip install -r requirements.txt

# Create .env file in root and add:
GEMINI_API_KEY=your_google_gemini_key
ASSEMBLYAI_API_KEY=your_assemblyai_key
MURF_API_KEY=your_murf_key
WEATHER_API_KEY=your_visual_crossing_key

# Run the Server
uvicorn main:app --reload
# App will be live at → http://localhost:8000/
```

---

## 🚀 Core Features

| 🎤 **Voice Input** | 🧠 **AI Processing** | 🎵 **Natural TTS** |
|:---:|:---:|:---:|
| One-click recording | Gemini 2.5 Flash | Murf AI voices |
| Turn detection | Conversational AI | Streaming playback |

| 🌤️ **Weather API** | ⚡ **Real-time** | 💬 **Memory Chat** |
|:---:|:---:|:---:|
| Visual Crossing | Low latency | Session memory |
| Live forecasts | WebSocket streaming | Continuous talk |

---

## 🧑‍💻 How to Use

### End Users (Web UI)
1. Open `localhost:8000` or Render link
2. Click 🎤 **Record** → Start speaking
3. Zody will → Listen → Transcribe → Think → Speak back
4. Conversation continues hands-free until you hit Stop

### Developers (API Endpoints)

**Web UI**: `/`

**WebSocket**:
- `/ws` → Echo bot
- `/ws/stream-audio` → Audio streaming
- `/ws/transcribe-stream` → Live transcription
- `/ws/llm-stream` → Full pipeline (STT → LLM → TTS)

**REST**:
- `POST /generate-audio` → Text → Voice
- `POST /upload-audio` → Upload audio
- `POST /tts/echo` → Transcribe + Echo
- `POST /llm/query` → One-shot query
- `POST /agent/chat/{session_id}` → Memory-enabled chat

---

## 📂 Project Structure

```
backend/
├── frontend/        # Web UI
├── schemas/         # Request/response models
├── services/        # STT, LLM, TTS, Weather, etc.
├── streaming/       # Audio streaming sessions
├── tmp/             # Temporary audio files
├── uploads/         # Uploaded audio files
├── utils/           # Logging, cleanup, helpers
├── backup_/         # Backup files/configs
│
├── .env             # Environment variables
├── .gitignore       # Git ignore rules
├── config.py        # Configurations
├── main.py          # FastAPI entry point
├── render.yaml      # Deployment config
├── requirements.txt # Dependencies
├── structure.txt    # Debugging dump
└── voice_agent.log  # Logs
```

---

## 🔑 Configuration & Env Variables

`.env` file example:

```ini
GEMINI_API_KEY=your_google_gemini_key
ASSEMBLYAI_API_KEY=your_assemblyai_key
MURF_API_KEY=your_murf_key
WEATHER_API_KEY=your_visual_crossing_key
```

**Bonus Security Feature**:
- Users can paste their own API keys directly in the UI
- Keys are stored only in browser memory → deleted after refresh

---

## 🔮 Future Scope

- 🎭 Add more personas (Pirate Zody, Coach Zody, etc.)
- 🌍 Multi-language support (Hindi, Arabic, etc.)
- 📱 Mobile app (Android/iOS)
- 💾 Cloud memory for long-term conversations
- 🧠 Add more skills (reminders, jokes, news, small talk)
- 🔊 Custom TTS voices for personality

---

## 💡 Motivation

Built as part of the **30 Days of AI Voice Agents Challenge**.  
I wanted to prove that with dedication + curiosity, even in just 30 days,  
I could engineer an AI companion robot that listens, understands, and responds naturally.

---

## 🙌 Acknowledgements

- **AssemblyAI** → Real-time speech-to-text
- **Google Gemini 2.5 Flash** → Conversational intelligence
- **Murf AI** → Natural text-to-speech
- **Visual Crossing** → Weather API
- **FastAPI & Uvicorn** → Backend framework
- **30 Days of AI Voice Agents Challenge (Murf AI)** → Inspiration

---

## 📬 Contact

👨‍💻 **Muhammed Jasim Nisam**

- **LinkedIn** → [linkedin.com/in/muhammed-jassim-nisam-656973277](https://linkedin.com/in/muhammed-jassim-nisam-656973277)
- **GitHub** → [github.com/jxsim-x](https://github.com/jxsim-x)
- **📧 Email** → jasimnisam123@gmail.com

---

## 📜 License

This project is licensed under the **MIT License**.  
Feel free to fork, modify, and build upon Zody 🎉
