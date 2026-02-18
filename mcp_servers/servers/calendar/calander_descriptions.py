GET_EVENTS_DESCRIPTION = """
**CALENDAR VIEWER — Get upcoming events**
Retrieves upcoming calendar events for the next N days from the user's Google Calendar.

Use this tool to:
1. Show the user their schedule for today, this week, or upcoming days.
2. Check what meetings or events are coming up.
3. Help the user plan their time.
4. Answer questions like "What's on my calendar today?" or "Am I free tomorrow?"

Parameters: days_ahead (optional, default 7), max_results (optional, default 20), calendar_id (optional, default "primary").
Returns: List of events with title, start time, end time, location, description, and attendees.
"""

SEARCH_EVENTS_DESCRIPTION = """
**CALENDAR SEARCH — Find events by keyword**
Searches for calendar events matching a keyword query.

Use this tool to:
1. Find specific meetings or events by name.
2. Look up events with a particular person or topic.
3. Answer questions like "When is my dentist appointment?" or "Do I have a meeting with John?"

Parameters: query (required), days_ahead (optional, default 30), calendar_id (optional, default "primary").
Returns: List of matching events with title, start time, end time, location, and description.
"""

GET_EVENT_DESCRIPTION = """
**EVENT DETAILS — Get full information about a specific event**
Retrieves detailed information about a single calendar event by its ID.

Use this tool to:
1. Get full details of an event found via get_events or search_events.
2. Check attendees, descriptions, or meeting links for a specific event.
3. Get event metadata like recurrence rules or reminders.

Parameters: event_id (required), calendar_id (optional, default "primary").
Returns: Full event details including title, time, location, description, attendees, meet link, and recurrence info.
"""

CREATE_EVENT_DESCRIPTION = """
**EVENT CREATOR — Create a new calendar event**
Creates a new event on the user's Google Calendar.

Use this tool to:
1. Schedule a new meeting, appointment, or reminder.
2. Block time on the user's calendar.
3. Create events with specific times, locations, and descriptions.
4. Add attendees who will receive email invitations.

IMPORTANT:
- Always confirm event details with the user before creating.
- Times should be in ISO 8601 format (e.g., "2025-03-15T10:00:00-05:00").
- For all-day events, use date format (e.g., "2025-03-15").

Parameters: title (required), start (required), end (required), description (optional), location (optional), attendees (optional list of emails).
Returns: Confirmation with the created event ID and a link to the event.
"""

UPDATE_EVENT_DESCRIPTION = """
**EVENT UPDATER — Modify an existing calendar event**
Updates an existing event on the user's Google Calendar.

Use this tool to:
1. Reschedule a meeting to a different time.
2. Change the title, description, or location of an event.
3. Update event details after finding them via get_events or search_events.

IMPORTANT:
- Always confirm changes with the user before updating.
- Only specified fields will be updated; unspecified fields remain unchanged.

Parameters: event_id (required), title (optional), start (optional), end (optional), description (optional), location (optional), calendar_id (optional).
Returns: Confirmation of the updated event.
"""

DELETE_EVENT_DESCRIPTION = """
**EVENT DELETER — Remove a calendar event**
Deletes an event from the user's Google Calendar.

Use this tool to:
1. Cancel a meeting or appointment.
2. Remove events the user no longer needs.
3. Clean up the calendar.

IMPORTANT: Always confirm with the user before deleting. This action cannot be undone.

Parameters: event_id (required), calendar_id (optional, default "primary").
Returns: Confirmation that the event was deleted.
"""

QUICK_ADD_EVENT_DESCRIPTION = """
**QUICK EVENT — Create event from natural language**
Creates a calendar event from a natural language text string using Google's Quick Add feature.

Use this tool to:
1. Quickly create events from casual descriptions.
2. Parse natural language like "Lunch with Sarah tomorrow at noon" or "Team standup every Monday at 9am".
3. When the user describes an event informally and you want to let Google parse it.

EXAMPLES:
- "Dentist appointment on March 15 at 2pm"
- "Coffee with Alex next Tuesday 3-4pm"
- "Project deadline January 31"

Parameters: text (required — the natural language event description), calendar_id (optional).
Returns: The created event details.
"""

LIST_CALENDARS_DESCRIPTION = """
**CALENDAR LISTER — List all available calendars**
Retrieves all calendars the user has access to, including shared and subscribed calendars.

Use this tool to:
1. Show the user all their calendars (personal, work, shared).
2. Find a specific calendar's ID for use with other calendar tools.
3. Check which calendars are available for event creation.

Returns: List of calendars with id, name, description, and access role.
"""

GET_FREE_BUSY_DESCRIPTION = """
**FREE/BUSY CHECKER — Check availability for a time range**
Checks the free/busy status for one or more calendars within a specified time range.

Use this tool to:
1. Check if the user is available at a specific time.
2. Find free slots for scheduling a new meeting.
3. Answer questions like "Am I free on Friday afternoon?" or "When am I available this week?"

Parameters: time_min (required, ISO 8601), time_max (required, ISO 8601), calendar_ids (optional, default ["primary"]).
Returns: List of busy time blocks within the specified range.
"""
