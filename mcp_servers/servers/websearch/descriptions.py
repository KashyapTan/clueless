SEARCH_WEB_PAGES_DESCRIPTION = """
**PRIMARY WEB DISCOVERY TOOL - START HERE FOR ONLINE INFORMATION**
Searches the web via DuckDuckGo to find relevant pages, articles, and resources.

MANDATORY WORKFLOW:
1. **Call this tool FIRST** when you need current information, recent news, or web-based resources.
2. **ALWAYS follow up with `read_website`** on the most relevant results. Search results contain only titles and brief snippets—you MUST read the full pages to provide accurate, detailed answers.

Use this tool to:
1. Find current events, breaking news, or time-sensitive information.
2. Locate authoritative sources (official documentation, research papers, company websites).
3. Discover multiple perspectives on a topic before synthesizing an answer.
4. Get recent information beyond your knowledge cutoff date.

CRITICAL WORKFLOW RULES:
- Search results are DISCOVERY ONLY—they provide URLs and snippets, not full content.
- Never answer solely from search snippets; always read the actual pages with `read_website`.
- If the first search doesn't yield good results, refine your query and search again.
- Prioritize official sources, primary sources, and authoritative domains.

CURRENT CONTEXT:
- Search results include: title, URL (href), and brief body snippet
- Typical workflow: search_web_pages → review results → read_website on top 2-3 URLs → synthesize answer
"""

READ_WEBSITE_DESCRIPTION = """
**CONTENT EXTRACTION TOOL - FOLLOW-UP TO SEARCH**
Fetches and extracts the full main content from a webpage in clean markdown format.

PREREQUISITES:
1. **Call `search_web_pages` FIRST** to discover relevant URLs. Do not guess or fabricate URLs.
2. **Verify the URL** from search results before reading (check it's relevant to the user's query).

Use this tool to:
1. Extract full article content, documentation, or webpage text after finding it via search.
2. Get detailed information that snippets don't provide (tables, code examples, step-by-step guides).
3. Read official documentation, research papers, blog posts, or news articles in full.
4. Verify and fact-check information from authoritative sources.

CRITICAL READING RULES:
- This tool returns the FULL CONTENT of a page—read strategically based on the user's needs.
- Uses stealth mode to bypass bot detection, but some sites may still block access.
- If a URL fails, try an alternative from your search results or search with different terms.
- Prioritize reading 2-3 high-quality sources over skimming many low-quality ones.

WORKFLOW EXAMPLE:
User asks: "What are the latest features in Python 3.13?"
1. Call search_web_pages(query="Python 3.13 new features release notes")
2. Review results, identify official Python.org release notes
3. Call read_website(url="https://docs.python.org/3.13/whatsnew/3.13.html")
4. Extract and summarize the key features from full content

CURRENT CONTEXT:
- Returns: Clean markdown content extracted from the main article/body
- On failure: Returns error message (invalid URL, blocked access, timeout)
"""