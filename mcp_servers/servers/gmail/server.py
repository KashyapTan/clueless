"""
Gmail MCP Server — PLACEHOLDER
================================
TODO: Implement these tools yourself!

Suggested tools:
  - read_mail(query, max_results) -> list   : Search and read emails
  - send_mail(to, subject, body) -> str     : Send an email
  - delete_mail(message_id) -> str          : Delete an email
  - label_mail(message_id, label) -> str    : Add a label to an email
  - list_labels() -> list                   : List all Gmail labels

Authentication:
  Gmail uses OAuth 2.0. You'll need:
  1. A Google Cloud project with Gmail API enabled
  2. OAuth 2.0 credentials (client_id, client_secret)
  3. The `google-auth` and `google-api-python-client` packages

  pip install google-auth google-auth-oauthlib google-api-python-client

  The OAuth flow:
  - First time: User visits a URL, grants permission, gets a code
  - Your server exchanges the code for tokens (access + refresh)
  - Store tokens in a file (e.g., token.json)
  - On subsequent runs, use the refresh token to get new access tokens

  See: https://developers.google.com/gmail/api/quickstart/python

Example skeleton:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    def get_gmail_service():
        creds = Credentials.from_authorized_user_file('token.json')
        return build('gmail', 'v1', credentials=creds)

    @mcp.tool()
    def read_mail(query: str = "is:unread", max_results: int = 10) -> str:
        '''Search Gmail and return matching messages.'''
        service = get_gmail_service()
        results = service.users().messages().list(
            userId='me', q=query, maxResults=max_results
        ).execute()
        # ... format and return results
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Gmail Tools")

# ── YOUR TOOLS GO HERE ─────────────────────────────────────────────────


if __name__ == "__main__":
    mcp.run()
