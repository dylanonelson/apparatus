"""
LLM connector using LiteLLM for flexible model provider support.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Coroutine,
    Dict,
    List,
    Optional,
    Tuple,
)

import litellm
import yaml
from fastmcp import Client as McpClient
from fastmcp import FastMCP
from litellm import ChatCompletionToolParam, acompletion
from litellm.cost_calculator import completion_cost
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import (
    Choices,
    Function,
    Message,
    ModelResponse,
    StreamingChoices,
)
from mcp.types import TextContent
from mcp.types import Tool as McpTool
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Span, SpanKind
from opentelemetry.trace.status import Status, StatusCode
from pydantic import BaseModel, JsonValue, model_validator

from app.mcp import (
    MCPToolName,
    call_mcp_server_with_api_auth,
    call_mcp_tool,
)
from app.request_context import RequestContext

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class ModelProfile(BaseModel):
    """A model profile configuration."""

    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ModelsConfig(BaseModel):
    """Configuration for model profiles loaded from models.yaml."""

    default: str
    profiles: Dict[str, ModelProfile]

    @model_validator(mode="after")
    def validate_default_exists(self) -> "ModelsConfig":
        if self.default not in self.profiles:
            raise ValueError(
                f"default profile '{self.default}' not found in profiles"
            )
        return self


def _load_model_profiles() -> ModelsConfig:
    """Load model profiles from the config/models.yaml file."""
    config_path = Path(__file__).parent.parent / "config" / "models.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Model profiles config not found: {config_path}"
        )
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    return ModelsConfig.model_validate(raw_config)


MAX_TOOL_CALL_ITERATIONS = 15


def mcp_tool_to_litellm(tool: McpTool) -> ChatCompletionToolParam:
    """
    Convert an MCP tool definition to LiteLLM's ChatCompletionToolParam format.

    Args:
        tool: An MCP Tool object from the MCP server.

    Returns:
        A ChatCompletionToolParam dict compatible with LiteLLM's tool calling API.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema
            or {"type": "object", "properties": {}},
        },
    }


class ModelConfig:
    """Configuration for LLM models loaded from config/models.yaml profiles."""

    def __init__(
        self,
        profile_name: Optional[str] = None,
    ):
        """
        Initialize model configuration from a named profile.

        Args:
            profile_name: Name of the profile to load from config/models.yaml.
                         If None, uses MODEL_PROFILE env var, defaulting to "default".
        """
        config = _load_model_profiles()

        requested_profile = profile_name or os.getenv(
            "MODEL_PROFILE", "default"
        )
        # Resolve "default" to the actual profile name from config
        resolved_profile_name = (
            config.default
            if requested_profile == "default"
            else requested_profile
        )
        if resolved_profile_name not in config.profiles:
            available = ", ".join(config.profiles.keys())
            raise ValueError(
                f"Unknown model profile '{resolved_profile_name}'. "
                f"Available profiles: {available}"
            )

        profile = config.profiles[resolved_profile_name]
        self.profile_name = resolved_profile_name
        self.default_model = profile.model
        self.temperature = profile.temperature
        self.max_tokens = profile.max_tokens

        logger.info(
            "Loaded model profile '%s': model=%s, temperature=%s, max_tokens=%s",
            self.profile_name,
            self.default_model,
            self.temperature,
            self.max_tokens,
        )

        # LiteLLM automatically looks for API key env vars:
        # - OPENAI_API_KEY
        # - ANTHROPIC_API_KEY
        # - GEMINI_API_KEY
        # - AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION

        # Optional: Set LiteLLM options
        litellm.drop_params = (
            True  # Drop unsupported params instead of erroring
        )

        litellm_verbose = (
            os.getenv("LITELLM_VERBOSE", "false").lower() == "true"
        )
        # set_verbose is present at runtime but missing from type hints; setattr avoids lint issues
        setattr(litellm, "set_verbose", litellm_verbose)


class ModelConnector:
    """Main interface for LLM interactions."""

    def __init__(
        self,
        mcp_server: FastMCP,
        config: Optional[ModelConfig] = None,
    ):
        self.config = config or ModelConfig()
        self._mcp_server = mcp_server

    async def chat(
        self,
        messages: List[Message],
        request_context: RequestContext,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enabled_tools: Optional[List[str]] = None,
    ) -> AsyncIterator[str]:
        """
        Send chat messages to LLM and get response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello"}]
            model: Model to use. If None, uses default from config.
                  Examples: "gpt-4", "claude-3-5-sonnet-20241022", "ollama/llama2"
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            request_context: Optional contextual metadata for tracing/tooling

        Returns:
            Response string, or async iterator if stream=True
        """
        if enabled_tools:
            raise NotImplementedError(
                "Streaming chat with tools enabled is not supported."
            )

        model = model or self.config.default_model
        temperature = (
            temperature if temperature is not None else self.config.temperature
        )
        max_tokens = (
            max_tokens if max_tokens is not None else self.config.max_tokens
        )

        parent_context = request_context.otel_context
        span = tracer.start_span(
            "litellm.acompletion.stream",
            kind=SpanKind.CLIENT,
            context=parent_context,
        )
        self._set_llm_span_attributes(
            span,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tool_count=0,
        )

        token: Optional[object] = None
        try:
            span_context = trace.set_span_in_context(span, parent_context)
            token = context_api.attach(parent_context)
            completion_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            if temperature is not None:
                completion_kwargs["temperature"] = temperature
            if max_tokens is not None:
                completion_kwargs["max_tokens"] = max_tokens
            with trace.use_span(span, end_on_exit=False):
                response = await acompletion(**completion_kwargs)
            return self._stream_response(
                response,
                span,
                span_context,
            )
        except Exception as exc:
            self._record_span_exception(span, exc)
            span.end()
            raise RuntimeError(f"Error calling LLM: {str(exc)}") from exc
        finally:
            if token is not None:
                context_api.detach(token)

    async def chat_sync(
        self,
        messages: List[Message],
        request_context: RequestContext,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enabled_tools: Optional[List[MCPToolName]] = None,
    ) -> str:
        """
        Send chat messages to LLM and get response. Wrapper around chat() to get a synchronous response.
        """
        model = model or self.config.default_model
        temperature = (
            temperature if temperature is not None else self.config.temperature
        )
        max_tokens = (
            max_tokens if max_tokens is not None else self.config.max_tokens
        )
        tools = await self._resolve_tools(enabled_tools, request_context)

        if not tools:
            response_stream = await self.chat(
                messages,
                request_context,
                model,
                temperature,
                max_tokens,
                enabled_tools=None,
            )
            full_response = ""
            async for chunk in response_stream:
                full_response += chunk
            return full_response

        return await self._chat_sync_with_tools(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            request_context=request_context,
        )

    async def _resolve_tools(
        self,
        enabled_tools: Optional[List[MCPToolName]],
        request_context: RequestContext,
    ) -> List[ChatCompletionToolParam]:
        """
        Resolve enabled tools by fetching definitions from the MCP server.

        Args:
            enabled_tools: List of tool names to enable, or None/empty to disable tools.
            request_context: Request context containing auth info for MCP calls.

        Returns:
            List of LiteLLM-compatible tool definitions.
        """
        if not enabled_tools:
            return []

        if self._mcp_server is None:
            logger.warning(
                "MCP server not configured; cannot resolve tools: %s",
                enabled_tools,
            )
            return []

        # Use the MCP client to list available tools with forwarded auth context
        async with call_mcp_server_with_api_auth(
            request_context.auth_token, request_context.auth_claims
        ):
            async with McpClient(self._mcp_server) as client:
                all_tools = await client.list_tools()

        # Filter to only the enabled tools and convert to LiteLLM format
        enabled_tools_set = set([tool.value for tool in enabled_tools])
        resolved_tools: List[ChatCompletionToolParam] = []
        for tool in all_tools:
            if tool.name in enabled_tools_set:
                resolved_tools.append(mcp_tool_to_litellm(tool))
            elif tool.name not in enabled_tools_set:
                # Tool exists but not requested - skip silently
                pass

        # Warn about requested tools that weren't found
        found_tools = {tool.name for tool in all_tools}
        for tool_name in enabled_tools:
            if tool_name not in found_tools:
                logger.warning(
                    "Requested tool not found in MCP server: %s", tool_name
                )

        return resolved_tools

    async def _chat_sync_with_tools(
        self,
        messages: List[Message],
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
        tools: List[ChatCompletionToolParam],
        request_context: RequestContext,
    ) -> str:
        conversation: List[Message] = [message for message in messages]
        tool_iterations = 0

        while True:
            completion_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": conversation,
                "stream": False,
                "tools": tools,
                "tool_choice": "auto",
            }
            if temperature is not None:
                completion_kwargs["temperature"] = temperature
            if max_tokens is not None:
                completion_kwargs["max_tokens"] = max_tokens

            parent_context = request_context.otel_context
            span = tracer.start_span(
                "litellm.acompletion",
                kind=SpanKind.CLIENT,
                context=parent_context,
            )
            self._set_llm_span_attributes(
                span,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tool_count=len(tools),
            )

            token: Optional[object] = None
            try:
                if parent_context is not None:
                    token = context_api.attach(parent_context)
                with trace.use_span(span, end_on_exit=False):
                    response = await acompletion(**completion_kwargs)
            except Exception as exc:
                self._record_span_exception(span, exc)
                span.end()
                raise
            finally:
                if token is not None:
                    context_api.detach(token)

            if isinstance(response, CustomStreamWrapper):
                error = TypeError(
                    "Tool-enabled chat does not support streaming responses"
                )
                self._record_span_exception(span, error)
                span.end()
                raise error

            choice = self._get_first_choice(response)
            conversation.append(choice.message)

            tool_calls = self._get_tool_calls(choice)
            span.set_attribute(
                "gen_ai.response.tool_call_count", len(tool_calls)
            )
            span.end()
            logger.info("Number of tool calls: %s", len(tool_calls))
            if tool_calls:
                tool_iterations += len(tool_calls)
                if tool_iterations > MAX_TOOL_CALL_ITERATIONS:
                    raise RuntimeError(
                        "Tool call loop exceeded iteration limit"
                    )
                parent_context = request_context.otel_context
                batch_token = context_api.attach(parent_context)
                try:
                    with tracer.start_as_current_span(
                        "litellm.tool.batch",
                    ) as tool_batch_span:
                        tool_batch_span.set_attribute(
                            "gen_ai.tool_call.count", len(tool_calls)
                        )
                        tool_parent_context = trace.set_span_in_context(
                            tool_batch_span, parent_context
                        )
                        tool_tasks: List[
                            Coroutine[object, object, JsonValue]
                        ] = []
                        task_metadata: List[Tuple[str, str]] = []
                        for tool_call_id, function in tool_calls:
                            logger.info("Function: %s", function)
                            logger.info("Executing tool call: %s", tool_call_id)
                            tool_name = function.name
                            arguments_json = function.arguments
                            if not tool_name or not arguments_json:
                                raise ValueError(
                                    "Tool call is missing a name or arguments"
                                )
                            tool_tasks.append(
                                self._dispatch_tool(
                                    tool_name,
                                    arguments_json,
                                    tool_parent_context,
                                    request_context,
                                )
                            )
                            task_metadata.append((tool_call_id, tool_name))
                        results = await asyncio.gather(*tool_tasks)
                        for (tool_call_id, tool_name), result in zip(
                            task_metadata, results
                        ):
                            conversation.append(
                                Message(
                                    tool_call_id=tool_call_id,
                                    role="tool",
                                    name=tool_name,
                                    content=json.dumps(result),
                                )
                            )
                finally:
                    if batch_token is not None:
                        context_api.detach(batch_token)
            else:
                break

        logger.info("Conversation[-1].content: %s", conversation[-1].content)
        return self._extract_message_content(conversation[-1])

    async def _dispatch_tool(
        self,
        tool_name: str,
        arguments_json: str,
        parent_context: Context,
        request_context: RequestContext,
    ) -> JsonValue:
        token = context_api.attach(parent_context)

        try:
            with tracer.start_as_current_span(
                "litellm.tool.execute",
            ) as span:
                span.set_attribute("gen_ai.tool.name", tool_name)
                span.set_attribute("gen_ai.tool.arguments", arguments_json)
                publication_id = request_context.publication_id
                span.set_attribute("gen_ai.tool.publication_id", publication_id)
                try:
                    return await self._execute_tool(
                        tool_name,
                        arguments_json,
                        request_context,
                    )
                except Exception as exc:  # noqa: BLE001
                    self._record_span_exception(span, exc)
                    logger.exception("Tool %s failed: %s", tool_name, exc)
                    return {"error": str(exc)}
        finally:
            context_api.detach(token)

    def _get_first_choice(self, response: ModelResponse) -> Choices:
        if not response.choices:
            raise ValueError("Response choices sequence is empty")
        first_choice = response.choices[0]
        if isinstance(first_choice, StreamingChoices):
            raise TypeError(
                "Received streaming choice in non-streaming response context"
            )
        if not isinstance(first_choice, Choices):
            raise TypeError("Unexpected choice payload type in ModelResponse")
        return first_choice

    def _get_tool_calls(self, choice: Choices) -> List[Tuple[str, Function]]:
        """Extract tool calls from the model's response."""
        if not choice.message.tool_calls:
            return []
        return [
            (t.id, t.function)
            for t in choice.message.tool_calls
            if isinstance(t.function, Function) and t.function.name
        ]

    async def _execute_tool(
        self,
        tool_name: str,
        arguments_json: str,
        request_context: RequestContext,
    ) -> JsonValue:
        """
        Execute a tool via the MCP client with forwarded auth context.

        Args:
            tool_name: Name of the tool to execute.
            arguments_json: JSON string of tool arguments from the LLM.
            request_context: Request context containing auth info.

        Returns:
            The tool result as a JSON-serializable value.
        """
        if self._mcp_server is None:
            raise RuntimeError(
                f"MCP server not configured; cannot execute tool: {tool_name}"
            )

        # Parse the arguments JSON
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON arguments: {exc}") from exc

        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")

        # For search_publication, inject publication_id if not provided
        # This allows the tool to work without requiring the caller to specify it
        if tool_name == MCPToolName.SEARCH_PUBLICATION_TOOL.value:
            if (
                "publication_id" not in arguments
                or arguments["publication_id"] is None
            ):
                arguments["publication_id"] = request_context.publication_id

        # Execute the tool via MCP client with forwarded auth context
        result = await call_mcp_tool(
            request_context,
            self._mcp_server,
            MCPToolName(tool_name),
            arguments,
        )

        # Extract the result data from the MCP response
        # The result contains content blocks; we return the structured data
        if hasattr(result, "data") and result.data is not None:
            # Structured data from FastMCP
            return result.data
        elif result.content:
            # Fall back to text content
            first_content = result.content[0]
            if isinstance(first_content, TextContent):
                # Try to parse as JSON, otherwise return as string
                try:
                    return json.loads(first_content.text)
                except json.JSONDecodeError:
                    return {"result": first_content.text}
        return {"result": None}

    def _set_llm_span_attributes(
        self,
        span: Span,
        *,
        model: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
        stream: bool,
        tool_count: int,
    ) -> None:
        span.set_attribute("gen_ai.system", "litellm")
        span.set_attribute("gen_ai.request.model", model)
        if temperature is not None:
            span.set_attribute("gen_ai.request.temperature", temperature)
        if max_tokens is not None:
            span.set_attribute("gen_ai.request.max_output_tokens", max_tokens)
        span.set_attribute("gen_ai.request.stream", stream)
        span.set_attribute("gen_ai.request.tool_count", tool_count)
        span.set_attribute("gen_ai.request.has_tools", tool_count > 0)

    @staticmethod
    def _record_span_exception(span: Span, exc: Exception) -> None:
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))

    def _extract_message_content(self, message: Message) -> str:
        if not message.content:
            raise ValueError("Message content is empty")
        return message.content

    async def _stream_response(
        self,
        response,
        span: Optional[Span] = None,
        span_context: Optional[Context] = None,
    ) -> AsyncIterator[str]:
        """Helper to stream response chunks."""
        token: Optional[object] = None
        if span_context is not None:
            token = context_api.attach(span_context)
        try:
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            if span is not None:
                self._record_span_exception(span, exc)
            raise
        finally:
            if token is not None:
                context_api.detach(token)
            if span is not None:
                span.end()

    def get_cost(self, response) -> Optional[float]:
        """
        Calculate cost of a completion response.

        Args:
            response: Response object from acompletion()

        Returns:
            Cost in USD, or None if cost can't be calculated
        """
        try:
            return completion_cost(completion_response=response)
        except Exception:
            return None


# Singleton instance for convenience
_connector: Optional[ModelConnector] = None


def initialize_connector(
    mcp_server: FastMCP,
    config: Optional[ModelConfig] = None,
) -> ModelConnector:
    """
    Initialize the global ModelConnector instance with an MCP server.

    This should be called during application startup, after the MCP server
    has been created.

    Args:
        mcp_server: The FastMCP server instance for in-memory tool calls.
        config: Optional model configuration.

    Returns:
        The initialized ModelConnector instance.
    """
    global _connector
    _connector = ModelConnector(mcp_server, config=config)
    return _connector


def get_connector() -> ModelConnector:
    """
    Get the global ModelConnector instance.

    Raises:
        RuntimeError: If initialize_connector() has not been called.
    """
    if _connector is None:
        raise RuntimeError(
            "ModelConnector not initialized. Call initialize_connector() first."
        )
    return _connector
