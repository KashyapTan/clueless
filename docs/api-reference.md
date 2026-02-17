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

### List Ollama Models

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

### Get Enabled Models

```
GET /api/models/enabled
```

Returns the list of models currently enabled in the UI.

**Response:**
```json
{
    "models": ["qwen3-vl:8b-instruct"]
}
```

### Update Enabled Models

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

**Response:**
```json
{
    "models": ["qwen3-vl:8b-instruct", "llama3:8b"]
}
```

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

Submits a user query. If screenshots are in context, they are automatically included. The `model` field selects which Ollama model to use.

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

Changes the screenshot capture behavior:
- `fullscreen` - Captures the entire screen automatically
- `precision` - Opens the region selector overlay
- `none` - Disables screenshot capture

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

Retrieves a paginated list of past conversations for the history page.

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

Resumes a previous conversation, restoring full chat state including thumbnails and token counts.

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

Permanently deletes a conversation and all its messages.

#### Stop Recording

```json
{
    "type": "stop_recording"
}
```

Stops voice recording and triggers transcription via faster-whisper.

---

### Server -> Client Messages

#### Ready

```json
{
    "type": "ready",
    "content": "Server ready..."
}
```

Sent on WebSocket connection. Indicates the server is ready to accept queries.

#### Screenshot Start

```json
{
    "type": "screenshot_start",
    "content": "Screenshot capture starting"
}
```

The screenshot capture process has begun. The UI should hide to avoid capturing itself.

#### Screenshot Added

```json
{
    "type": "screenshot_added",
    "content": "{\"id\": \"ss_1\", \"name\": \"screenshot.png\", \"thumbnail\": \"data:image/png;base64,...\"}"
}
```

A screenshot has been captured and added to the current context. Contains a base64 thumbnail for display.

#### Screenshot Removed

```json
{
    "type": "screenshot_removed",
    "content": "{\"id\": \"ss_1\"}"
}
```

A screenshot has been removed from context.

#### Screenshots Cleared

```json
{
    "type": "screenshots_cleared",
    "content": ""
}
```

All screenshots have been cleared from context (e.g., after being used in a query).

#### Screenshot Ready (Legacy)

```json
{
    "type": "screenshot_ready",
    "content": "Screenshot captured..."
}
```

Legacy message for backward compatibility.

#### Query Echo

```json
{
    "type": "query",
    "content": "User's question"
}
```

Echoes the user's query back for display in the chat.

#### Thinking Chunk

```json
{
    "type": "thinking_chunk",
    "content": "...partial reasoning..."
}
```

Streaming chunk of the model's thinking/reasoning process (for models that support it, like Qwen).

#### Thinking Complete

```json
{
    "type": "thinking_complete",
    "content": ""
}
```

The model has finished its thinking/reasoning phase.

#### Response Chunk

```json
{
    "type": "response_chunk",
    "content": "...partial response..."
}
```

Streaming chunk of the model's visible response.

#### Response Complete

```json
{
    "type": "response_complete",
    "content": ""
}
```

The model has finished its response. The full response has been persisted to the database.

#### Tool Call

```json
{
    "type": "tool_call",
    "content": "{\"name\": \"search_web_pages\", \"arguments\": {\"query\": \"latest news\"}, \"server\": \"websearch\"}"
}
```

An MCP tool has been invoked. Displays as a card in the UI.

#### Tool Result

```json
{
    "type": "tool_result",
    "content": "{\"name\": \"search_web_pages\", \"result\": \"[...results...]\", \"server\": \"websearch\"}"
}
```

The result of an MCP tool execution.

#### Tool Calls Summary

```json
{
    "type": "tool_calls_summary",
    "content": "[{\"name\": \"add\", \"arguments\": {\"a\": 42, \"b\": 58}, \"result\": \"100.0\", \"server\": \"demo\"}]"
}
```

Summary of all tool calls made during a response, sent after response completion.

#### Context Cleared

```json
{
    "type": "context_cleared",
    "content": "Context cleared..."
}
```

Confirmation that the conversation context has been reset.

#### Conversation Saved

```json
{
    "type": "conversation_saved",
    "content": "{\"conversation_id\": \"uuid-string\"}"
}
```

The conversation has been persisted to the database.

#### Conversations List

```json
{
    "type": "conversations_list",
    "content": "[{\"id\": \"uuid\", \"title\": \"...\", \"created_at\": 1234567890, \"updated_at\": 1234567890}]"
}
```

Response to `get_conversations`. Contains a JSON array of conversation metadata.

#### Conversation Loaded

```json
{
    "type": "conversation_loaded",
    "content": "{\"conversation_id\": \"uuid\", \"messages\": [...]}"
}
```

Response to `load_conversation` or `resume_conversation`. Contains the full message history.

#### Conversation Resumed

```json
{
    "type": "conversation_resumed",
    "content": "{\"conversation_id\": \"uuid\", \"messages\": [...], \"token_usage\": {...}}"
}
```

Full state restoration including messages and token counts.

#### Conversation Deleted

```json
{
    "type": "conversation_deleted",
    "content": "{\"conversation_id\": \"uuid\"}"
}
```

Confirmation that a conversation has been deleted.

#### Token Update

```json
{
    "type": "token_update",
    "content": "{\"input\": 123, \"output\": 456, \"total\": 579}"
}
```

Token usage statistics, sent after each response.

#### Transcription Result

```json
{
    "type": "transcription_result",
    "content": "Transcribed text from audio"
}
```

Result of voice-to-text transcription via faster-whisper.

#### Error

```json
{
    "type": "error",
    "content": "Error message describing what went wrong"
}
```

An error occurred during processing.
