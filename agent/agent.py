"""Core agent implementation with ReAct pattern."""
import json
import asyncio
from typing import AsyncGenerator, Optional, Any, Dict, List
from datetime import datetime
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent.types import (
    AgentConfig,
    AgentEvent,
    ToolStartEvent,
    ToolEndEvent,
    ToolErrorEvent,
    AnswerStartEvent,
    AnswerChunkEvent,
    DoneEvent,
    LogEvent,
    ToolSummary,
)
from model.llm import LLMProvider
from tools.financial_search import FinancialSearchTool, WebSearchTool
from agent.prompts import (
    build_system_prompt,
    build_iteration_prompt,
    build_final_answer_prompt,
)


class Agent:
    """ReAct-style agent for financial research."""

    DEFAULT_MAX_ITERATIONS = 10

    def __init__(
        self,
        config: AgentConfig,
        tools: List[StructuredTool],
        system_prompt: str,
    ):
        """Initialize the agent."""
        self.model = config.model or "gpt-4.1-mini"
        self.model_provider = config.model_provider or "openai"
        self.max_iterations = config.max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self.system_prompt = system_prompt
        self.signal = config.signal
        self.llm = LLMProvider.get_model(self.model, self.model_provider)

    @staticmethod
    def create(config: AgentConfig = None) -> "Agent":
        """Create a new Agent instance with tools."""
        if config is None:
            config = AgentConfig()

        # Initialize tools
        financial_tool = FinancialSearchTool()
        web_tool = WebSearchTool()

        tools = [
            StructuredTool(
                name="financial_search",
                description="Search for financial data about companies",
                func=financial_tool.search,
                args_schema=None,
            ),
            StructuredTool(
                name="get_financials",
                description="Get financial statements for a company",
                func=financial_tool.get_financials,
                args_schema=None,
            ),
        ]

        # Add web search if API key is available
        import os
        if os.getenv("TAVILY_API_KEY"):
            tools.append(
                StructuredTool(
                    name="web_search",
                    description="Search the web for information",
                    func=web_tool.search,
                    args_schema=None,
                )
            )

        system_prompt = build_system_prompt()
        return Agent(config, tools, system_prompt)

    async def run(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Run the agent and yield events for real-time UI updates.

        Args:
            query: The user's query
            chat_history: Optional conversation history

        Yields:
            AgentEvent instances for real-time updates
        """
        if not self.tools:
            yield DoneEvent(
                answer="No tools available. Please check your API key configuration.",
                tool_calls=[],
                iterations=0,
            )
            return

        all_tool_calls: List[Dict[str, Any]] = []
        all_summaries: List[ToolSummary] = []
        messages: List[Any] = []

        # Build initial messages
        messages.append(SystemMessage(content=self.system_prompt))

        if chat_history:
            for item in chat_history:
                if item.get("role") == "user":
                    messages.append(HumanMessage(content=item.get("content", "")))
                elif item.get("role") == "assistant":
                    messages.append(AIMessage(content=item.get("content", "")))

        messages.append(HumanMessage(content=query))

        iteration = 0
        scratchpad = f"Query: {query}\n"

        while iteration < self.max_iterations:
            iteration += 1

            # Check for abort signal
            if self.signal and self.signal.is_set():
                yield DoneEvent(
                    answer="Agent execution cancelled.",
                    tool_calls=all_tool_calls,
                    iterations=iteration,
                )
                return

            # Build iteration prompt
            iteration_prompt = build_iteration_prompt(
                query, scratchpad, all_summaries
            )
            messages[-1] = HumanMessage(content=iteration_prompt)

            # Call LLM
            yield LogEvent(message=f"Agent Thinking (Iteration {iteration})...", level="thought")
            try:
                response = await asyncio.to_thread(
                    self.llm.invoke, messages
                )
            except Exception as e:
                yield ToolErrorEvent(tool="llm", error=str(e))
                continue

            # Extract text and check for tool calls
            response_text = response.content if hasattr(response, "content") else str(response)
            messages.append(AIMessage(content=response_text))
            
            # Emit thought log
            yield LogEvent(message=response_text, level="thought")

            # Parse tool calls from response
            tool_calls = self._parse_tool_calls(response_text)

            if not tool_calls:
                # No more tool calls, generate final answer
                yield LogEvent(message="Gathered sufficient info. Generating final answer...", level="info")
                yield AnswerStartEvent()

                final_prompt = build_final_answer_prompt(
                    query, scratchpad, all_summaries, response_text
                )
                messages[-1] = HumanMessage(content=final_prompt)

                try:
                    final_response = await asyncio.to_thread(
                        self.llm.invoke, messages
                    )
                except Exception as e:
                    yield ToolErrorEvent(tool="final_answer", error=str(e))
                    yield DoneEvent(
                        answer=f"Error generating final answer: {str(e)}",
                        tool_calls=all_tool_calls,
                        iterations=iteration,
                    )
                    return

                final_answer = (
                    final_response.content
                    if hasattr(final_response, "content")
                    else str(final_response)
                )

                # Stream answer chunks
                for chunk in final_answer.split(" "):
                    yield AnswerChunkEvent(chunk=chunk + " ")

                yield DoneEvent(
                    answer=final_answer,
                    tool_calls=all_tool_calls,
                    iterations=iteration,
                )
                return

            # Execute tool calls
            for tool_call in tool_calls:
                tool_name = tool_call.get("tool", "")
                tool_args = tool_call.get("args", {})

                yield LogEvent(message=f"Planning to use {tool_name} with {json.dumps(tool_args)}", level="tool")
                yield ToolStartEvent(tool=tool_name, args=tool_args)

                if tool_name not in self.tool_map:
                    error_msg = f"Unknown tool: {tool_name}"
                    yield ToolErrorEvent(tool=tool_name, error=error_msg)
                    scratchpad += f"\nTool Error ({tool_name}): {error_msg}"
                    continue

                try:
                    tool = self.tool_map[tool_name]
                    result = await asyncio.to_thread(
                        tool.func, **tool_args
                    )

                    yield ToolEndEvent(tool=tool_name, result=str(result)[:500])
                    yield LogEvent(message=f"Tool {tool_name} returned {len(str(result))} characters", level="info")

                    # Record tool call
                    all_tool_calls.append(tool_call)

                    # Create summary
                    summary = ToolSummary(
                        tool=tool_name,
                        args=tool_args,
                        result=str(result)[:1000],
                        timestamp=datetime.now().isoformat(),
                    )
                    all_summaries.append(summary)

                    scratchpad += f"\nTool ({tool_name}): {json.dumps(tool_args)}\nResult: {str(result)[:500]}"

                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    yield ToolErrorEvent(tool=tool_name, error=error_msg)
                    scratchpad += f"\nTool Error ({tool_name}): {error_msg}"

        # Max iterations reached
        yield DoneEvent(
            answer="Maximum iterations reached. Unable to complete the research.",
            tool_calls=all_tool_calls,
            iterations=iteration,
        )

    def _parse_tool_calls(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response.

        Args:
            response_text: The LLM response text

        Returns:
            List of tool calls with name and arguments
        """
        tool_calls = []

        # Look for tool calls in format: <tool_call>{"tool": "name", "args": {...}}</tool_call>
        import re

        pattern = r"<tool_call>(.*?)</tool_call>"
        matches = re.findall(pattern, response_text, re.DOTALL)

        for match in matches:
            try:
                tool_call = json.loads(match)
                tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue

        return tool_calls
