"""Prompts for the agent."""
from typing import List
from src.agent.types import ToolSummary


def build_system_prompt() -> str:
    """Build the system prompt for the agent."""
    return """You are FinCode, an autonomous financial research agent. Your role is to analyze complex financial questions and provide data-backed answers.

You have access to the following tools:
- financial_search: Search for financial data about companies
- get_financials: Get financial statements (income, balance sheet, cash flow)
- web_search: Search the web for current information

Your approach:
1. Break down complex queries into research tasks
2. Use tools to gather relevant financial data
3. Analyze and synthesize the information
4. Provide clear, data-backed answers

When you need to use a tool, format it as:
<tool_call>{"tool": "tool_name", "args": {"param1": "value1", "param2": "value2"}}</tool_call>

Be thorough but efficient. Always cite your sources and data points."""


def build_iteration_prompt(
    query: str,
    scratchpad: str,
    summaries: List[ToolSummary],
) -> str:
    """Build the prompt for an iteration of the agent loop."""
    summaries_text = ""
    if summaries:
        summaries_text = "\n\nPrevious tool results:\n"
        for summary in summaries[-3:]:  # Last 3 summaries
            summaries_text += f"- {summary.tool}: {summary.result[:200]}...\n"

    return f"""Continue researching the following query:
{query}

Your work so far:
{scratchpad}
{summaries_text}

Next steps:
1. Analyze what information you still need
2. Use appropriate tools to gather missing data
3. If you have enough information, prepare your final answer

Remember to format tool calls as:
<tool_call>{{"tool": "tool_name", "args": {{"param": "value"}}}}</tool_call>

If you have gathered sufficient information to answer the query, respond with your analysis instead of calling more tools."""


def build_final_answer_prompt(
    query: str,
    scratchpad: str,
    summaries: List[ToolSummary],
    analysis: str,
) -> str:
    """Build the prompt for generating the final answer."""
    summaries_text = "\n\nData gathered:\n"
    for summary in summaries:
        summaries_text += f"- {summary.tool}: {summary.result[:300]}...\n"

    return f"""Based on your research, provide a comprehensive answer to:
{query}

Your research work:
{scratchpad}

Data gathered:
{summaries_text}

Your analysis so far:
{analysis}

Now provide a final, well-structured answer that:
1. Directly addresses the query
2. Cites specific data points and metrics
3. Includes relevant context and trends
4. Explains any limitations or caveats
5. Suggests next steps if needed

Format your answer clearly with sections and bullet points where appropriate."""


def build_tool_summary_prompt(tool_name: str, result: str) -> str:
    """Build a prompt for summarizing tool results."""
    return f"""Summarize the following {tool_name} result concisely:

{result}

Provide a 1-2 sentence summary highlighting the key information."""
