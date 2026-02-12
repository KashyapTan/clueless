"""
Canvas LMS MCP Server — PLACEHOLDER
=====================================
TODO: Implement these tools yourself!

Suggested tools:
  - get_courses() -> list                           : List your enrolled courses
  - get_assignments(course_id) -> list              : Get assignments for a course
  - get_upcoming_due(days_ahead) -> list            : Get assignments due soon
  - get_grades(course_id) -> list                   : Get your grades
  - get_announcements(course_id) -> list            : Get course announcements

Authentication:
  Canvas uses API Access Tokens (much simpler than OAuth!).

  1. Log into your Canvas instance (e.g., https://your-university.instructure.com)
  2. Go to Account -> Settings
  3. Scroll down to "Approved Integrations"
  4. Click "+ New Access Token"
  5. Give it a name, click "Generate Token"
  6. Copy the token (you only see it once!)

  pip install requests

  The Canvas REST API is straightforward:
    Base URL: https://your-university.instructure.com/api/v1
    Auth: Bearer token in the Authorization header

Example skeleton:
    import requests

    CANVAS_URL = "https://your-university.instructure.com"
    CANVAS_TOKEN = "your-access-token"
    HEADERS = {"Authorization": f"Bearer {CANVAS_TOKEN}"}

    @mcp.tool()
    def get_courses() -> str:
        '''Get all your enrolled courses.'''
        resp = requests.get(
            f"{CANVAS_URL}/api/v1/courses",
            headers=HEADERS,
            params={"enrollment_state": "active"}
        )
        courses = resp.json()
        return "\\n".join(f"- {c['name']} (ID: {c['id']})" for c in courses)

    @mcp.tool()
    def get_upcoming_due(days_ahead: int = 7) -> str:
        '''Get assignments due in the next N days.'''
        # Use the /api/v1/users/self/upcoming_events endpoint
        # or iterate courses and check assignment due dates
        ...
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Canvas LMS Tools")

# ── YOUR TOOLS GO HERE ─────────────────────────────────────────────────


if __name__ == "__main__":
    mcp.run()
