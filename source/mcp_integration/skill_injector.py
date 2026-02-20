"""
Skill injection engine.

Determines which skills to inject into the system prompt for a given turn,
based on forced skills (from slash commands) and auto-detected dominant
tool category from the retriever output.
"""

from collections import Counter
from typing import List, Dict, Any


def get_skills_to_inject(
    retrieved_tools: List[Dict],
    forced_skills: List[Dict],
    db,
    mcp_manager=None,
) -> List[Dict]:
    """
    Returns ordered list of skill dicts to inject into the system prompt.

    Rules:
    - forced_skills are always included (from slash commands)
    - From retrieved tools, find the dominant category (most tools from one server)
    - If that category has a skill and it's not already in forced_skills, add it
    - Result: forced_skills + up to 1 auto-detected skill (deduplicated)

    Args:
        retrieved_tools: Tools returned by Top-K retriever (Ollama format)
        forced_skills: Skills from slash command parsing
        db: DatabaseManager instance
        mcp_manager: McpToolManager instance (for tool→server mapping)
    """
    all_skills = {s["skill_name"]: s for s in db.get_all_skills() if s["enabled"]}
    forced_names = {s["skill_name"] for s in forced_skills}

    # Count tools per server category
    category_counts: Counter = Counter()
    if mcp_manager and retrieved_tools:
        for tool in retrieved_tools:
            func = tool.get("function", {})
            tool_name = func.get("name", "")
            if tool_name:
                server = mcp_manager.get_tool_server_name(tool_name)
                if server:
                    category_counts[server] += 1

    # Auto-detect: pick the dominant server's skill if available
    auto_skill = None
    if category_counts:
        dominant_server = category_counts.most_common(1)[0][0]
        if dominant_server in all_skills and dominant_server not in forced_names:
            auto_skill = all_skills[dominant_server]

    result = list(forced_skills)
    if auto_skill:
        result.append(auto_skill)

    return result


def build_skills_prompt_block(skills: List[Dict]) -> str:
    """
    Formats skills into a system prompt block.
    Returns empty string if no skills.
    """
    if not skills:
        return ""

    blocks = [s["content"].strip() for s in skills]
    joined = "\n\n---\n\n".join(blocks)
    return f"\n\n## Active Skills\n\n{joined}\n"
