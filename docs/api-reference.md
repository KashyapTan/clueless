# API Reference

Clueless uses two communication protocols between the frontend and backend:
- **WebSocket** (`ws://localhost:8000/ws`) for real-time bidirectional messaging
- **REST API** (`http://localhost:8000/api/*`) for configuration and metadata

## REST API Endpoints

### Health Check

```
GET /api/health
```

Returns server status. Used by the Electron process to verify the Python server is running.

**Response:**
```json
{
    "status": "healthy"
}
```

### Model Management

#### List Ollama Models

```
GET /api/models/ollama
```

Returns all locally installed Ollama models.

**Response:**
```json
{
    "models": [
        {
            "name": "qwen3-vl:8b-instruct",
            "size": 5300000000,
            "modified_at": "2026-02-01T12:00:00Z"
        }
    ]
}
```

#### List Cloud Models

```
GET /api/models/anthropic
GET /api/models/openai
GET /api/models/gemini
```

Returns available models for the respective cloud provider. Requires a valid API key to be stored. If the API is unreachable, returns a fallback list of known models.

**Response:**
```json
[
    {
        "name": "anthropic/claude-3-5-sonnet-20241022",
        "provider": "anthropic",
        "description": "Claude 3.5 Sonnet"
    }
]
```

#### Get Enabled Models

```
GET /api/models/enabled
```

Returns the list of models currently enabled in the UI (both local and cloud).

**Response:**
```json
{
    "models": ["qwen3-vl:8b-instruct", "anthropic/claude-3-5-sonnet-20241022"]
}
```

#### Update Enabled Models

```
PUT /api/models/enabled
Content-Type: application/json
```

**Request Body:**
```json
{
    "models": ["qwen3-vl:8b-instruct", "llama3:8b"]
}
```

### API Key Management

#### Get Key Status

```
GET /api/keys
```

Returns the status of API keys for all cloud providers (masked).

**Response:**
```json
{
    "anthropic": { "has_key": true, "masked": "sk-ant...a1b2" },
    "openai": { "has_key": false, "masked": null },
    "gemini": { "has_key": false, "masked": null }
}
```

#### Save API Key

```
PUT /api/keys/{provider}
Content-Type: application/json
```

Validates and stores an API key. Supported providers: `anthropic`, `openai`, `gemini`.

**Request Body:**
```json
{
    "key": "sk-..."
}
```

#### Delete API Key

```
DELETE /api/keys/{provider}
```

Removes the stored API key for the specified provider.

### Google OAuth

#### Get Connection Status

```
GET /api/google/status
```

**Response:**
```json
{
    "connected": true,
    "email": "user@gmail.com",
    "auth_in_progress": false
}
```

#### Connect Google Account

```
POST /api/google/connect
```

Initiates the OAuth flow. Opens the system browser for login. Blocks until authentication completes or fails.

**Response:**
```json
{
    "success": true,
    "email": "user@gmail.com"
}
```

#### Disconnect Google Account

```
POST /api/google/disconnect
```

Revokes the OAuth token and removes stored credentials.

---

## WebSocket Protocol

All WebSocket messages use JSON with `type` and optional `content` fields:

```json
{
    "type": "message_type",
    "content": "string or JSON-stringified object"
}
```

### Client -> Server Messages

#### Submit a Query

```json
{
    "type": "submit_query",
    "content": "Your question here",
    "model": "qwen3-vl:8b-instruct"
}
```

Submits a user query. If screenshots are in context, they are automatically included. The `model` field can be a local Ollama model or a cloud model ID (e.g., `anthropic/claude-3-5-sonnet`).

#### Clear Context

```json
{
    "type": "clear_context"
}
```

Starts a new conversation. Clears chat history, screenshots, and resets state.

#### Stop Streaming

```json
{
    "type": "stop_streaming"
}
```

Interrupts the current AI response mid-stream.

#### Set Capture Mode

```json
{
    "type": "set_capture_mode",
    "mode": "fullscreen | precision | none"
}
```

Changes the screenshot capture behavior.

#### Remove Screenshot

```json
{
    "type": "remove_screenshot",
    "screenshot_id": "ss_1"
}
```

Removes a specific screenshot from the current context.

#### Get Conversations

```json
{
    "type": "get_conversations",
    "limit": 50,
    "offset": 0
}
```

Retrieves a paginated list of past conversations.

#### Load Conversation

```json
{
    "type": "load_conversation",
    "conversation_id": "uuid-string"
}
```

Loads a specific conversation's messages into the chat view.

#### Resume Conversation

```json
{
    "type": "resume_conversation",
    "conversation_id": "uuid-string"
}
```

Resumes a previous conversation, restoring full chat state.

#### Search Conversations

```json
{
    "type": "search_conversations",
    "query": "search terms"
}
```

Searches conversation titles and message content.

#### Delete Conversation

```json
{
    "type": "delete_conversation",
    "conversation_id": "uuid-string"
}
```

Permanently deletes a conversation.

#### Stop Recording

```json
{
    "type": "stop_recording"
}
```

Stops voice recording and triggers transcription.

---

### Server -> Client Messages

#### Ready

```json
{
    "type": "ready",
    "content": "Server ready..."
}
```

Sent on WebSocket connection.

#### Screenshot Added

```json
{
    "type": "screenshot_added",
    "content": "{\"id\": \"ss_1\", \"name\": \"screenshot.png\", \"thumbnail\": \"...\"}"
}
```

A screenshot has been captured and added.

#### Thinking Chunk

```json
{
    "type": "thinking_chunk",
    "content": "...partial reasoning..."
}
```

Streaming chunk of the model's thinking/reasoning process (Ollama DeepSeek/Qwen or Claude/OpenAI reasoning models).

#### Response Chunk

```json
{
    "type": "response_chunk",
    "content": "...partial response..."
}
```

Streaming chunk of the model's visible response.

#### Tool Call

```json
{
    "type": "tool_call",
    "content": "{\"name\": \"search_web_pages\", \"arguments\": {\"query\": \"news\"}, \"server\": \"websearch\"}"
}
```

An MCP tool has been invoked.

#### Tool Result

```json
{
    "type": "tool_result",
    "content": "{\"name\": \"search_web_pages\", \"result\": \"...\", \"server\": \"websearch\"}"
}
```

The result of an MCP tool execution.

#### Tool Calls Summary

```json
{
    "type": "tool_calls_summary",
    "content": "[{\"name\": \"add\", \"result\": \"100\", \"server\": \"demo\"}]"
}
```

Summary of all tool calls made during a response.

#### Token Update

```json
{
    "type": "token_update",
    "content": "{\"input\": 123, \"output\": 456, \"total\": 579}"
}
```

Token usage statistics.

#### Transcription Result

```json
{
    "type": "transcription_result",
    "content": "Transcribed text"
}
```

Result of voice-to-text transcription.

#### Error

```json
{
    "type": "error",
    "content": "Error message"
}
```

An error occurred during processing.
