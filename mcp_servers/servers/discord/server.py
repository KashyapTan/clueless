"""
Discord MCP Server — PLACEHOLDER
==================================
TODO: Implement these tools yourself!

Suggested tools:
  - send_message(channel_id, content) -> str  : Send a message to a channel
  - read_messages(channel_id, limit) -> list  : Read recent messages
  - list_channels(guild_id) -> list           : List channels in a server
  - list_guilds() -> list                     : List servers the bot is in

Authentication:
  Discord uses Bot Tokens (simpler than OAuth for personal use).
  
  1. Go to https://discord.com/developers/applications
  2. Create a "New Application"
  3. Go to "Bot" tab -> "Add Bot"
  4. Copy the Bot Token
  5. Invite the bot to your server with proper permissions

  pip install discord.py   # or use raw HTTP requests

  IMPORTANT: Discord bots typically run as long-lived processes.
  For MCP tools, you'll want to use Discord's REST API directly
  (not the websocket gateway), so the tool can make a single HTTP
  request and return immediately.

  pip install aiohttp   # for async HTTP requests

Example skeleton (using REST API directly):
    import aiohttp

    DISCORD_TOKEN = "your-bot-token"
    BASE_URL = "https://discord.com/api/v10"
    
    @mcp.tool()
    async def send_message(channel_id: str, content: str) -> str:
        '''Send a message to a Discord channel.'''
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
                json={"content": content}
            ) as resp:
                data = await resp.json()
                return f"Message sent: {data['id']}"
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Discord Tools")

# ── YOUR TOOLS GO HERE ─────────────────────────────────────────────────


if __name__ == "__main__":
    mcp.run()
