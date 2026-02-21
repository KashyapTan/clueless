SEARCH_EMAILS_DESCRIPTION = """
**EMAIL SEARCH TOOL — Find emails using Gmail search syntax**
Searches the user's Gmail inbox using Gmail's powerful query syntax and returns matching messages.

Use this tool to:
1. Find specific emails by sender, subject, keyword, or date range.
2. Look up recent communications with a particular person or about a topic.
3. Find emails with attachments or in specific folders.

QUERY EXAMPLES:
- "is:unread" — all unread emails
- "from:alice@example.com" — emails from Alice
- "subject:meeting" — emails with "meeting" in the subject
- "has:attachment" — emails with attachments
- "after:2025/01/01 before:2025/02/01" — emails from January 2025
- "is:starred" — starred emails
- "in:sent" — sent emails
- "label:work" — emails with the "work" label
- "newer_than:7d" — emails from the last 7 days

Returns: List of emails with id, threadId, subject, from, date, and snippet.
"""

READ_EMAIL_DESCRIPTION = """
**EMAIL READER — Get full content of a specific email**
Retrieves the complete content of a specific email by its message ID.

Use this tool to:
1. Read the full body of an email found via search_emails.
2. Get all details: subject, from, to, cc, date, and full body text.
3. Check attachment names and sizes.
4. Read replies and follow the conversation context.

WORKFLOW: Always call search_emails first to find the message ID, then use this tool to read the full content.

Returns: Full email details including subject, from, to, cc, date, body (plain text), and attachment list.
"""

SEND_EMAIL_DESCRIPTION = """
**EMAIL SENDER — Compose and send a new email**
Composes and sends a new email from the user's Gmail account.

Use this tool to:
1. Send a new email to one or more recipients.
2. Include CC and BCC recipients as needed.
3. Send plain text email messages.

IMPORTANT:
- Always confirm with the user before sending an email.
- Double-check recipient addresses for accuracy.
- The email is sent immediately and cannot be recalled.

Parameters: to (required), subject (required), body (required), cc (optional), bcc (optional).
Returns: Confirmation with the sent message ID.
"""

REPLY_TO_EMAIL_DESCRIPTION = """
**EMAIL REPLY — Reply to a specific email thread**
Sends a reply to an existing email, maintaining the conversation thread.

Use this tool to:
1. Reply to an email the user received.
2. Continue an existing email conversation.
3. Respond to messages found via search_emails.

WORKFLOW: Call search_emails or read_email first to get the message_id, then use this tool to reply.

IMPORTANT:
- Always confirm with the user before sending a reply.
- The reply is sent to the original sender by default.
- The reply appears in the same conversation thread.

Parameters: message_id (required), body (required).
Returns: Confirmation with the sent reply message ID.
"""

CREATE_DRAFT_DESCRIPTION = """
**DRAFT CREATOR — Create an email draft without sending**
Creates a draft email in the user's Gmail Drafts folder without sending it.

Use this tool to:
1. Prepare an email for the user to review before sending.
2. Save an email to send later.
3. When the user wants to compose but not immediately send.

Parameters: to (required), subject (required), body (required), cc (optional), bcc (optional).
Returns: Confirmation with the draft ID.
"""

TRASH_EMAIL_DESCRIPTION = """
**EMAIL TRASH — Move an email to trash**
Moves a specific email to the Gmail Trash folder.

Use this tool to:
1. Delete an unwanted email.
2. Clean up the user's inbox.
3. Remove spam or irrelevant messages.

IMPORTANT: Always confirm with the user before trashing an email. Trashed emails can be recovered within 30 days.

Parameters: message_id (required).
Returns: Confirmation that the email was trashed.
"""

LIST_LABELS_DESCRIPTION = """
**LABEL LISTER — List all Gmail labels/folders**
Retrieves all labels (folders) in the user's Gmail account.

Use this tool to:
1. Show the user their email organization structure.
2. Find label names before applying them with modify_labels.
3. List both system labels (INBOX, SENT, TRASH) and custom user labels.

Returns: List of labels with id, name, and type (system or user).
"""

MODIFY_LABELS_DESCRIPTION = """
**LABEL MODIFIER — Add or remove labels from an email**
Adds or removes labels (folders/tags) from a specific email message.

Use this tool to:
1. Organize emails by adding labels (e.g., "Work", "Important").
2. Move emails between folders by changing labels.
3. Mark emails as read (remove UNREAD label) or unread (add UNREAD label).
4. Archive emails (remove INBOX label).
5. Star/unstar emails (add/remove STARRED label).

COMMON OPERATIONS:
- Mark as read: remove_labels=["UNREAD"]
- Mark as unread: add_labels=["UNREAD"]
- Archive: remove_labels=["INBOX"]
- Star: add_labels=["STARRED"]

Parameters: message_id (required), add_labels (optional list), remove_labels (optional list).
Returns: Confirmation of label changes.
"""

GET_UNREAD_COUNT_DESCRIPTION = """
**UNREAD COUNTER — Get count of unread emails**
Returns the number of unread emails currently in the user's Gmail inbox.

Use this tool to:
1. Give the user a quick overview of their inbox status.
2. Check if there are new unread messages.
3. Provide inbox statistics.

Returns: The count of unread emails in the inbox.
"""

GET_EMAIL_THREAD_DESCRIPTION = """
**THREAD READER — Get all messages in a conversation thread**
Retrieves all messages in a Gmail conversation thread, showing the full back-and-forth.

Use this tool to:
1. Read an entire email conversation in chronological order.
2. Understand the full context of a discussion.
3. Follow up on multi-message threads.

WORKFLOW: Use search_emails to find a relevant email, note the threadId, then use this tool to get the full conversation.

Parameters: thread_id (required).
Returns: List of all messages in the thread with sender, date, and body content.
"""
