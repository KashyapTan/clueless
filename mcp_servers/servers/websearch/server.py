from mcp.server.fastmcp import FastMCP
from ddgs import DDGS
import json

mcp = FastMCP("Web Search Tools")

# ------------------------------------------------------------------
# 1. Fetch website urls tool
# ------------------------------------------------------------------
@mcp.tool()
def search_web_pages(query:str):
    """
    Use this tool to fetch website urls and titles
    
    Also use this tool when the user asks you to search the web
    """
    results = DDGS().text(
        query=query,
        region='wt-wt', # us-en for US
        safesearch='off',
        max_results=10
    )

    results_json = json.dumps(results)
    return results_json

# import trafilatura

# url = 'https://www.cbsnews.com/news/winter-olympic-games-schedule-2026/'

# # Use the 'config' or 'headers' approach
# downloaded = trafilatura.fetch_url(url)

# if downloaded:
#     result = trafilatura.extract(downloaded, output_format='markdown')
#     print(result)
#     with open("output.txt", "w", encoding="utf-8") as f:
#         f.write(result)

#     print("Scraping complete. Check output.txt.")
# else:
#     print("Blocked or failed to fetch.")
