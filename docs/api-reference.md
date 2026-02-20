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

### MCP Tools and Retrieval Settings

#### List MCP Servers and Tools

```
GET /api/mcp/servers
```

Returns a list of connected MCP servers and the tools they provide.

**Response:**
```json
[
    {
        "server": "filesystem",
        "tools": ["list_directory", "read_file", "write_file", ...]
    }
]
```

#### Get Tool Retrieval Settings

```
GET /api/settings/tools
```

Returns current tool retrieval settings.

**Response:**
```json
{
    "always_on": ["search_web_pages", "read_website"],
    "top_k": 5
}
```

#### Update Tool Retrieval Settings

```
PUT /api/settings/tools
Content-Type: application/json
```

**Request Body:**
```json
{
    "always_on": ["list_directory"],
    "top_k": 3
}
```

### System Prompt Settings

#### Get System Prompt

```
GET /api/settings/system-prompt
```

Returns the current custom system prompt template, or the default if none is saved.

**Response:**
```json
{
    "template": "You are Clueless...",
    "is_custom": false
}
```

#### Update System Prompt

```
PUT /api/settings/system-prompt
Content-Type: application/json
```

Updates the custom system prompt template. Send an empty string to reset to the default.

**Request Body:**
```json
{
    "template": "Your new custom prompt here"
}
```

### Skill Management

#### Get All Skills

```
GET /api/skills
```

Returns all skills (default and user-created).

#### Create Skill

```
POST /api/skills
```

#### Update Skill

```
PUT /api/skills/{skill_name}
```

#### Delete Skill

```
DELETE /api/skills/{skill_name}
```

#### Reset Skill

```
POST /api/skills/{skill_name}/reset
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

Submits a user query and creates a **RequestContext**. If screenshots are in context, they are automatically included. The `model` field can be a local Ollama model or a cloud model ID (e.g., `anthropic/claude-3-5-sonnet`).

**Slash Commands**: If the `content` contains recognized slash commands (e.g., `/fs`), the corresponding **Skills** are injected into the system prompt for that turn.

**Note**: Submitting a query while another is in progress will return an error.

#### Clear Context

```json
{
    "type": "clear_context"
}
```

Starts a new conversation. Clears chat history, screenshots, and resets state (including terminal session mode).

#### Stop Streaming

```json
{
    "type": "stop_streaming"
}
```

Interrupts the current AI response mid-stream by cancelling the active `RequestContext`. This triggers immediate cleanup of associated resources (e.g., killing running shell processes).

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

### Terminal Interaction Messages

#### Terminal Approval Response

```json
{
    "type": "terminal_approval_response",
    "request_id": "req_uuid",
    "approved": true,
    "remember": false
}
```

Sent by the client to approve or deny a command execution request.

#### Terminal Session Response

```json
{
    "type": "terminal_session_response",
    "approved": true
}
```

Sent by the client to approve or deny a request to enter autonomous session mode.

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

### Terminal Events

#### Terminal Approval Request

```json
{
    "type": "terminal_approval_request",
    "content": "{\"request_id\": \"...\", \"command\": \"...\", \"cwd\": \"...\"}"
}
```

The server is waiting for user approval before executing a command.

#### Terminal Output

```json
{
    "type": "terminal_output",
    "content": "{\"request_id\": \"...\", \"output\": \"...\"}"
}
```

Live stdout/stderr stream from an executing command.

#### Terminal Command Complete

```json
{
    "type": "terminal_command_complete",
    "content": "{\"request_id\": \"...\", \"exit_code\": 0, \"duration_ms\": 1234}"
}
```

A terminal command has finished executing.

#### Terminal Running Notice

```json
{
    "type": "terminal_running_notice",
    "content": "{\"request_id\": \"...\", \"command\": \"...\", \"elapsed_seconds\": 15}"
}
```

Sent every 10 seconds for long-running commands to keep the UI informed.
