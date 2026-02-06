# Clueless - Feature Roadmap & Implementation Plan

This document outlines the planned features for transforming Clueless from a screenshot-first tool into a comprehensive AI assistant with multiple interaction modes.

---

## Table of Contents
1. [Completed: Step 0 - Core Refactoring](#step-0-core-refactoring-completed)
2. [Feature 1: Precision Screenshot Mode](#feature-1-precision-screenshot-mode)
3. [Feature 2: Full Screen Mode (Default)](#feature-2-full-screen-mode-default)
4. [Feature 3: Voice Input Mode](#feature-3-voice-input-mode)
5. [Feature 4: Transcription/Recording Mode](#feature-4-transcriptionrecording-mode)
6. [Feature 5: Model Selection](#feature-5-model-selection)
7. [Feature 6: Chat History Tab](#feature-6-chat-history-tab)
8. [UI/UX Design Reference](#uiux-design-reference)
9. [Technical Architecture](#technical-architecture)
10. [Local Storage Strategy](#local-storage-strategy)

---

## Step 0: Core Refactoring (COMPLETED) ✅

### Goal
Allow users to interact with the LLM immediately upon app launch, without requiring a screenshot first.

### Changes Made

#### Backend (`source/main.py`)
- ✅ Made screenshot optional in `handle_submit_query()`
- ✅ Updated `_stream_ollama_chat()` to handle `None` image_path
- ✅ Added model selection: `qwen3-vl` for vision, `qwen3` for text-only
- ✅ Added `ready` message sent on WebSocket connection
- ✅ Added `clear_context` message handler
- ✅ Added `handle_clear_context()` function

#### Frontend (`src/ui/App.tsx`)
- ✅ Added `hasScreenshot` state to track screenshot presence
- ✅ Handle `ready` message to enable input immediately
- ✅ Handle `context_cleared` message
- ✅ Added `handleClearContext()` function
- ✅ Added screenshot indicator with clear button
- ✅ Dynamic placeholder text based on context

#### Styles (`src/ui/App.css`)
- ✅ Added `.screenshot-indicator` styles
- ✅ Added `.screenshot-badge` styles
- ✅ Added `.clear-btn` styles with hover effects

---

## Feature 1: Precision Screenshot Mode

### Description
The user can take a precise screenshot of a selected region using a hotkey (Ctrl+Shift+Alt+S). This is the existing functionality, now made optional.

### Current Status: ✅ FUNCTIONAL

### Behavior
1. User presses Ctrl+Shift+Alt+S at any time
2. App window hides (opacity → 0)
3. Full-screen overlay appears with dimmed background
4. User clicks and drags to select region
5. Selected region shows at full brightness with white border
6. On release, screenshot saved and attached to context
7. App window reappears with "📷 Screenshot attached" indicator
8. User can type query about the screenshot OR continue text-only chat
9. User can clear screenshot context with × button

### Files Involved
- `source/ss.py` - `RegionSelector` class, `ScreenshotService` class
- `source/main.py` - Screenshot lifecycle handling
- `src/ui/App.tsx` - UI state management

### No Changes Needed
This feature is complete and working.

---

## Feature 2: Full Screen Mode (Default)

### Description
When enabled, submitting a query automatically captures the entire screen and includes it with the prompt. This is ideal for quick "what's on my screen" questions.

### Implementation Plan

#### UI Changes (`src/ui/App.tsx`)
```tsx
// Add mode state
const [captureMode, setCaptureMode] = useState<'fullscreen' | 'precision' | 'none'>('fullscreen');

// Mode selector buttons at bottom of UI
<div className="mode-selector">
  <button 
    className={captureMode === 'fullscreen' ? 'active' : ''} 
    onClick={() => setCaptureMode('fullscreen')}
    title="Full Screen Mode (Default)"
  >
    <ScreenIcon />
  </button>
  <button 
    className={captureMode === 'precision' ? 'active' : ''} 
    onClick={() => setCaptureMode('precision')}
    title="Precision Screenshot Mode"
  >
    <CropIcon />
  </button>
</div>
```

#### Backend Changes (`source/main.py`)
```python
# New WebSocket message type
{"type": "submit_query", "content": "...", "capture_mode": "fullscreen"}

# In handle_submit_query():
if capture_mode == "fullscreen":
    # Take full screen screenshot automatically
    image_path = take_fullscreen_screenshot()
```

#### New Function (`source/ss.py`)
```python
def take_fullscreen_screenshot(save_folder="screenshots"):
    """Capture entire screen without UI overlay"""
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    screen = ImageGrab.grab()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fullscreen_{timestamp}.png"
    filepath = os.path.join(save_folder, filename)
    screen.save(filepath)
    return filepath
```

#### Workflow
1. User is in Full Screen mode (default)
2. User types query and presses Enter
3. App automatically captures entire screen
4. Screenshot + query sent to vision model
5. Response streamed back

#### Edge Cases
- If in fullscreen mode but user already has a precision screenshot attached, use that instead
- Hide app window briefly during auto-capture to avoid capturing the app itself

---

## Feature 3: Voice Input Mode

### Description
Voice-to-text input that captures both system audio (videos, meetings) and microphone input. Activated by clicking a mic button.

### Implementation Plan

#### Dependencies to Add (`requirements.txt`)
```
sounddevice          # Cross-platform audio capture
numpy               # Audio processing
vosk                # Offline speech recognition (lightweight)
# OR
whisper             # OpenAI Whisper (more accurate, larger)
# OR
speech_recognition  # Google/other cloud APIs
```

#### Recommended: Vosk (Offline, Lightweight)
- ~50MB model download
- Works offline
- Good accuracy for English
- Low latency

#### UI Changes (`src/ui/App.tsx`)
```tsx
const [isRecording, setIsRecording] = useState(false);

// Mic button next to input
<button 
  className={`mic-btn ${isRecording ? 'recording' : ''}`}
  onClick={toggleVoiceInput}
>
  <MicIcon />
</button>

// WebSocket messages
ws.send(JSON.stringify({ type: 'start_voice_input' }));
ws.send(JSON.stringify({ type: 'stop_voice_input' }));

// Handle incoming transcription
case 'voice_transcription':
  setQuery(prev => prev + data.content);
  break;
```

#### Backend Changes (`source/main.py`)
```python
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# Global state
_voice_recorder = None

async def handle_start_voice_input():
    """Start capturing audio from mic + system"""
    global _voice_recorder
    _voice_recorder = VoiceRecorder(callback=on_transcription)
    _voice_recorder.start()
    await broadcast_message("voice_started", "Listening...")

async def handle_stop_voice_input():
    """Stop recording and get final transcription"""
    global _voice_recorder
    if _voice_recorder:
        _voice_recorder.stop()
        _voice_recorder = None
    await broadcast_message("voice_stopped", "")
```

#### New File: `source/voice.py`
```python
import sounddevice as sd
import numpy as np
from vosk import Model, KaldiRecognizer
import json
import threading
import queue

class VoiceRecorder:
    def __init__(self, callback, model_path="vosk-model-small-en-us"):
        self.callback = callback
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.audio_queue = queue.Queue()
        self.running = False
        
    def start(self):
        self.running = True
        self.stream = sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=self._audio_callback
        )
        self.stream.start()
        threading.Thread(target=self._process_audio, daemon=True).start()
        
    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            
    def _audio_callback(self, indata, frames, time, status):
        if self.running:
            self.audio_queue.put(bytes(indata))
            
    def _process_audio(self):
        while self.running:
            try:
                data = self.audio_queue.get(timeout=0.5)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    if result.get('text'):
                        self.callback(result['text'] + ' ')
                else:
                    partial = json.loads(self.recognizer.PartialResult())
                    # Could broadcast partial results for live preview
            except queue.Empty:
                continue
```

#### System Audio Capture (Windows)
```python
# For capturing system audio (what you hear), need virtual audio device
# Options:
# 1. VB-CABLE / VoiceMeeter (user installs)
# 2. WASAPI loopback (Windows-specific)

import pyaudiowpatch as pyaudio  # Windows WASAPI loopback

def get_system_audio_stream():
    p = pyaudio.PyAudio()
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    # Find loopback device
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['hostApi'] == wasapi_info['index'] and dev['maxInputChannels'] > 0:
            if 'loopback' in dev['name'].lower():
                return dev['index']
```

#### Available in Both Modes
Voice input should work regardless of whether user is in precision or fullscreen mode. The transcribed text simply goes into the input field.

---

## Feature 4: Transcription/Recording Mode

### Description
Record meetings/calls, transcribe to text, save locally. Access recordings from a dedicated tab.

### Implementation Plan

#### UI Changes - New Tab (`src/ui/App.tsx`)
```tsx
type TabType = 'chat' | 'recordings' | 'settings';
const [activeTab, setActiveTab] = useState<TabType>('chat');

// Tab navigation at top
<div className="tab-bar">
  <button onClick={() => setActiveTab('chat')}>💬</button>
  <button onClick={() => setActiveTab('recordings')}>📝</button>
  <button onClick={() => setActiveTab('settings')}>⚙️</button>
</div>

// Conditional rendering
{activeTab === 'chat' && <ChatView />}
{activeTab === 'recordings' && <RecordingsView />}
{activeTab === 'settings' && <SettingsView />}
```

#### Recording Mode UI
```tsx
const RecordingsView = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [currentRecording, setCurrentRecording] = useState<Recording | null>(null);
  
  return (
    <div className="recordings-view">
      <div className="recording-controls">
        <button 
          className={`record-btn ${isRecording ? 'active' : ''}`}
          onClick={toggleRecording}
        >
          {isRecording ? '⏹️ Stop' : '🔴 Record'}
        </button>
        {isRecording && <span className="recording-timer">{formatTime(elapsed)}</span>}
      </div>
      
      <div className="recordings-list">
        {recordings.map(rec => (
          <div key={rec.id} className="recording-item" onClick={() => setCurrentRecording(rec)}>
            <span>{rec.title}</span>
            <span>{rec.date}</span>
            <span>{rec.duration}</span>
          </div>
        ))}
      </div>
      
      {currentRecording && (
        <div className="transcript-view">
          <h3>{currentRecording.title}</h3>
          <div className="transcript-text">{currentRecording.transcript}</div>
          <button onClick={() => summarize(currentRecording)}>🤖 Summarize</button>
        </div>
      )}
    </div>
  );
};
```

#### Backend: Recording Service (`source/recording.py`)
```python
import os
import json
import datetime
from pathlib import Path

# Storage location: app_data/recordings/
RECORDINGS_DIR = Path(__file__).parent.parent / "app_data" / "recordings"

class RecordingService:
    def __init__(self, transcription_callback):
        self.voice_recorder = None
        self.current_transcript = []
        self.start_time = None
        self.callback = transcription_callback
        
    def start_recording(self):
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        self.current_transcript = []
        self.start_time = datetime.datetime.now()
        
        self.voice_recorder = VoiceRecorder(
            callback=self._on_transcription,
            include_system_audio=True
        )
        self.voice_recorder.start()
        
    def _on_transcription(self, text):
        timestamp = (datetime.datetime.now() - self.start_time).total_seconds()
        entry = {"time": timestamp, "text": text}
        self.current_transcript.append(entry)
        self.callback(entry)  # Broadcast to UI
        
    def stop_recording(self) -> dict:
        if self.voice_recorder:
            self.voice_recorder.stop()
            
        # Save to file
        recording_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        recording = {
            "id": recording_id,
            "title": f"Recording {recording_id}",
            "date": self.start_time.isoformat(),
            "duration": (datetime.datetime.now() - self.start_time).total_seconds(),
            "transcript": self.current_transcript
        }
        
        filepath = RECORDINGS_DIR / f"{recording_id}.json"
        with open(filepath, 'w') as f:
            json.dump(recording, f, indent=2)
            
        return recording
        
    def list_recordings(self) -> list:
        recordings = []
        for file in RECORDINGS_DIR.glob("*.json"):
            with open(file) as f:
                data = json.load(f)
                recordings.append({
                    "id": data["id"],
                    "title": data["title"],
                    "date": data["date"],
                    "duration": data["duration"]
                })
        return sorted(recordings, key=lambda x: x["date"], reverse=True)
        
    def get_recording(self, recording_id: str) -> dict:
        filepath = RECORDINGS_DIR / f"{recording_id}.json"
        with open(filepath) as f:
            return json.load(f)
            
    def summarize_recording(self, recording_id: str) -> str:
        recording = self.get_recording(recording_id)
        full_transcript = " ".join([t["text"] for t in recording["transcript"]])
        
        # Use Ollama to summarize
        from ollama import chat
        response = chat(
            model='qwen3:8b',
            messages=[{
                'role': 'user',
                'content': f"""Summarize this meeting transcript. Include:
1. Key topics discussed
2. Action items
3. Important decisions made

Transcript:
{full_transcript}"""
            }]
        )
        return response['message']['content']
```

#### Storage Format (Lightweight JSON)
```json
{
  "id": "20260205_143022",
  "title": "Team Standup",
  "date": "2026-02-05T14:30:22",
  "duration": 1823.5,
  "transcript": [
    {"time": 0.0, "text": "Hello everyone, let's start the standup."},
    {"time": 3.2, "text": "I worked on the API integration yesterday."},
    ...
  ],
  "summary": null
}
```

#### WebSocket Messages
```json
// Client → Server
{"type": "start_recording"}
{"type": "stop_recording"}
{"type": "list_recordings"}
{"type": "get_recording", "id": "..."}
{"type": "summarize_recording", "id": "..."}

// Server → Client
{"type": "recording_started", "content": ""}
{"type": "recording_transcript", "content": {"time": 5.2, "text": "..."}}
{"type": "recording_stopped", "content": {"id": "...", "duration": 1823.5}}
{"type": "recordings_list", "content": [...]}
{"type": "recording_data", "content": {...}}
{"type": "recording_summary", "content": "..."}
```

---

## Feature 5: Model Selection

### Description
Allow users to select different AI providers (Ollama, Gemini, Claude, OpenAI) and specific models within each provider.

### Implementation Plan

#### Settings Storage (`app_data/settings.json`)
```json
{
  "providers": {
    "ollama": {
      "enabled": true,
      "models": ["qwen3:8b", "qwen3-vl:8b-instruct", "llama3:8b"],
      "default_text_model": "qwen3:8b",
      "default_vision_model": "qwen3-vl:8b-instruct"
    },
    "openai": {
      "enabled": false,
      "api_key": "",
      "models": ["gpt-4o", "gpt-4o-mini"],
      "default_model": "gpt-4o"
    },
    "anthropic": {
      "enabled": false,
      "api_key": "",
      "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
      "default_model": "claude-3-5-sonnet-20241022"
    },
    "google": {
      "enabled": false,
      "api_key": "",
      "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
      "default_model": "gemini-1.5-pro"
    }
  },
  "active_provider": "ollama",
  "active_model": "qwen3:8b"
}
```

#### Settings UI (`src/ui/SettingsView.tsx`)
```tsx
const SettingsView = () => {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  
  return (
    <div className="settings-view">
      <h2>⚙️ Settings</h2>
      
      <section className="provider-section">
        <h3>Ollama (Local)</h3>
        <p className="provider-status">✅ Running on localhost:11434</p>
        <ModelSelector models={settings.providers.ollama.models} />
      </section>
      
      <section className="provider-section">
        <h3>OpenAI</h3>
        <input 
          type="password" 
          placeholder="API Key (sk-...)"
          value={settings.providers.openai.api_key}
          onChange={e => updateApiKey('openai', e.target.value)}
        />
        {settings.providers.openai.api_key && (
          <ModelSelector models={settings.providers.openai.models} />
        )}
      </section>
      
      <section className="provider-section">
        <h3>Anthropic (Claude)</h3>
        <input 
          type="password" 
          placeholder="API Key (sk-ant-...)"
          value={settings.providers.anthropic.api_key}
          onChange={e => updateApiKey('anthropic', e.target.value)}
        />
      </section>
      
      <section className="provider-section">
        <h3>Google (Gemini)</h3>
        <input 
          type="password" 
          placeholder="API Key"
          value={settings.providers.google.api_key}
          onChange={e => updateApiKey('google', e.target.value)}
        />
      </section>
    </div>
  );
};
```

#### Model Selector Dropdown (Main UI)
```tsx
// In App.tsx, next to input field
<select 
  className="model-selector"
  value={activeModel}
  onChange={e => setActiveModel(e.target.value)}
>
  <optgroup label="Ollama">
    <option value="ollama:qwen3:8b">qwen3:8b</option>
    <option value="ollama:qwen3-vl:8b-instruct">qwen3-vl (Vision)</option>
  </optgroup>
  {settings.providers.openai.api_key && (
    <optgroup label="OpenAI">
      <option value="openai:gpt-4o">GPT-4o</option>
      <option value="openai:gpt-4o-mini">GPT-4o Mini</option>
    </optgroup>
  )}
  {/* ... other providers */}
</select>
```

#### Backend: Model Router (`source/models.py`)
```python
from abc import ABC, abstractmethod
import os

class ModelProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list, image_path: str | None = None) -> AsyncGenerator[str, None]:
        pass

class OllamaProvider(ModelProvider):
    def __init__(self, model: str):
        self.model = model
        
    async def chat(self, messages, image_path=None):
        from ollama import chat
        # ... existing Ollama streaming code

class OpenAIProvider(ModelProvider):
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
    async def chat(self, messages, image_path=None):
        # Convert messages to OpenAI format
        # Handle vision if image_path provided
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class AnthropicProvider(ModelProvider):
    def __init__(self, api_key: str, model: str):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        
    async def chat(self, messages, image_path=None):
        # Convert messages to Anthropic format
        # ...

class GoogleProvider(ModelProvider):
    def __init__(self, api_key: str, model: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        
    async def chat(self, messages, image_path=None):
        # ...

def get_provider(provider_model: str, settings: dict) -> ModelProvider:
    """Factory function to get appropriate provider"""
    provider, model = provider_model.split(':', 1)
    
    if provider == 'ollama':
        return OllamaProvider(model)
    elif provider == 'openai':
        return OpenAIProvider(settings['providers']['openai']['api_key'], model)
    elif provider == 'anthropic':
        return AnthropicProvider(settings['providers']['anthropic']['api_key'], model)
    elif provider == 'google':
        return GoogleProvider(settings['providers']['google']['api_key'], model)
```

#### Security Note
- API keys stored in local `app_data/settings.json`
- Consider encrypting with user password or OS keychain
- Never transmit keys over network (all API calls from local Python)

---

## Feature 6: Chat History Tab

### Description
Persistent chat history that users can browse, search, and resume conversations from.

### Implementation Plan

#### Storage (`app_data/chats/`)
```
app_data/
├── chats/
│   ├── index.json          # List of all chats
│   ├── chat_20260205_143022.json
│   └── chat_20260205_150512.json
```

#### Chat Index Format
```json
{
  "chats": [
    {
      "id": "chat_20260205_143022",
      "title": "Python async programming",
      "created": "2026-02-05T14:30:22",
      "updated": "2026-02-05T14:45:10",
      "preview": "How do I use asyncio...",
      "message_count": 8,
      "has_screenshot": true
    }
  ]
}
```

#### Individual Chat Format
```json
{
  "id": "chat_20260205_143022",
  "title": "Python async programming",
  "created": "2026-02-05T14:30:22",
  "updated": "2026-02-05T14:45:10",
  "model": "ollama:qwen3:8b",
  "screenshot_path": "screenshots/screenshot_20260205_143022.png",
  "messages": [
    {"role": "user", "content": "How do I use asyncio?"},
    {"role": "assistant", "content": "Here's how to use asyncio..."},
    ...
  ]
}
```

#### Chat History UI (`src/ui/ChatHistoryView.tsx`)
```tsx
const ChatHistoryView = () => {
  const [chats, setChats] = useState<ChatPreview[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  return (
    <div className="chat-history-view">
      <input 
        type="text" 
        placeholder="Search chats..."
        value={searchQuery}
        onChange={e => setSearchQuery(e.target.value)}
      />
      
      <div className="chats-list">
        {chats
          .filter(c => c.title.includes(searchQuery) || c.preview.includes(searchQuery))
          .map(chat => (
            <div 
              key={chat.id} 
              className="chat-item"
              onClick={() => loadChat(chat.id)}
            >
              <div className="chat-title">
                {chat.has_screenshot && '📷 '}
                {chat.title}
              </div>
              <div className="chat-preview">{chat.preview}</div>
              <div className="chat-meta">
                {formatDate(chat.updated)} · {chat.message_count} messages
              </div>
            </div>
          ))
        }
      </div>
      
      <button className="new-chat-btn" onClick={startNewChat}>
        + New Chat
      </button>
    </div>
  );
};
```

#### Auto-Save Logic
```typescript
// In App.tsx
useEffect(() => {
  // Auto-save chat after each response completes
  if (chatHistory.length > 0 && canSubmit) {
    saveChat({
      id: currentChatId,
      messages: chatHistory,
      screenshot_path: hasScreenshot ? currentScreenshotPath : null
    });
  }
}, [chatHistory, canSubmit]);
```

#### Title Generation
```python
async def generate_chat_title(first_message: str) -> str:
    """Use LLM to generate a short title for the chat"""
    response = chat(
        model='qwen3:8b',
        messages=[{
            'role': 'user',
            'content': f'Generate a short (3-5 word) title for a chat that starts with: "{first_message[:200]}". Reply with just the title, no quotes.'
        }]
    )
    return response['message']['content'].strip()
```

---

## UI/UX Design Reference

Based on the provided mockup image:

```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️  🕐  📝                                            ?    │  ← Settings, History, Recordings, Help
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│                     [Chat Messages Area]                    │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  User input here                                            │
│  ┌──────────────────────────────────────────┬────────┬───┐  │
│  │ +  [Text Input Field                    ]│ Model ▼│ 🎤│  │
│  └──────────────────────────────────────────┴────────┴───┘  │
│                                                             │
│               [🖥️]    [⊞]    [👥]                           │  ← Mode buttons
│            Fullscreen  Crop   Meeting                       │
└─────────────────────────────────────────────────────────────┘
```

### Icon Legend
- ⚙️ Settings (API keys, model config)
- 🕐 Chat History
- 📝 Recordings/Transcriptions
- ? Help/Info
- + Add files (future: attach documents)
- Model ▼ Model selector dropdown
- 🎤 Voice input toggle
- 🖥️ Full screen mode (default)
- ⊞ Precision/region screenshot mode
- 👥 Meeting recorder mode

---

## Technical Architecture

### Local-First Storage

All data stored locally in `app_data/` directory:

```
app_data/
├── settings.json       # User preferences, API keys
├── chats/              # Chat history
│   ├── index.json
│   └── chat_*.json
├── recordings/         # Meeting transcriptions
│   └── *.json
└── screenshots/        # Cached screenshots (cleaned periodically)
    └── *.png
```

### Thread Safety

Python backend handles concurrency:
- Main thread: FastAPI/uvicorn event loop
- Background threads: Audio recording, Ollama streaming
- Thread-safe queue for audio processing
- `asyncio.call_soon_threadsafe()` for cross-thread WebSocket broadcasts

### Security Considerations

1. **API Keys**: Store encrypted or use OS keychain
2. **Screenshots**: Auto-delete after session unless saved in chat
3. **Audio**: Never stored raw, only transcriptions
4. **Local Network**: WebSocket only on localhost

---

## Local Storage Strategy

### Why Local Storage?

1. **Privacy**: All data stays on user's machine
2. **Offline**: Works without internet (with Ollama)
3. **Speed**: No network latency for data access
4. **Control**: User owns their data

### Data Lifecycle

| Data Type | Storage Location | Retention |
|-----------|------------------|-----------|
| Chat History | `app_data/chats/` | Permanent until user deletes |
| Recordings | `app_data/recordings/` | Permanent until user deletes |
| Screenshots | `app_data/screenshots/` | 24 hours or until chat saved |
| Settings | `app_data/settings.json` | Permanent |
| Temp Screenshots | `screenshots/` | Cleared on app close |

### Backup/Export (Future)
- Export chat as Markdown
- Export recording as text file
- Backup all data as ZIP

---

## Implementation Priority

1. ✅ **Step 0**: Core refactoring (DONE)
2. 🔜 **Feature 2**: Full screen mode (easiest, high value)
3. 🔜 **Feature 5**: Model selection (enables cloud providers)
4. 🔜 **Feature 6**: Chat history (persistence)
5. 🔜 **Feature 3**: Voice input (medium complexity)
6. 🔜 **Feature 4**: Transcription mode (most complex)

---

## Dependencies to Add

```txt
# requirements.txt additions
sounddevice>=0.4.6      # Audio capture
numpy>=1.24.0           # Audio processing
vosk>=0.3.45            # Offline speech recognition
openai>=1.0.0           # OpenAI API
anthropic>=0.18.0       # Claude API
google-generativeai>=0.3.0  # Gemini API

# Optional for system audio capture (Windows)
pyaudiowpatch>=0.0.6    # WASAPI loopback
```

---

## Notes

- Keep the floating window aesthetic - it's a key differentiator
- Maintain the "always-on-top" behavior for quick access
- Ensure smooth animations during screenshot capture
- Test thoroughly on high-DPI displays (already handling this)
- Consider keyboard shortcuts for all major actions
