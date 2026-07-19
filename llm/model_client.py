"""
llm/model_client.py

Wraps the organization's internal LLM gateway (custom auth headers,
/openapi/chat/v1/messages endpoint) as a LangChain BaseChatModel, so
everything downstream (create_react_agent, graph nodes) keeps working
unchanged -- this is the ONLY file that changes when swapping providers.

IMPORTANT CAVEAT -- read before relying on this in the pipeline:
The gateway's request body (modelIds, contents, llmConfig, isStream,
systemPrompt) has no native "tools"/function-calling parameter. So this
wrapper SIMULATES tool calling: it appends tool descriptions into the
system prompt and instructs the model to respond with a specific JSON
shape when it wants to call a tool, then parses that JSON back into
LangChain's AIMessage.tool_calls format.

This is a well-established pattern for non-native-tool-calling APIs, but
it is less reliable than real function-calling. Validate it against 2-3
real repos (same advice as for raw Ollama) before trusting it at scale --
if the model doesn't consistently emit the exact JSON shape, tighten the
instructions further or reduce how many tools are offered per call.

ASSUMPTION TO VERIFY WITH YOUR GATEWAY OWNERS: the "contents" field's
multi-turn behavior isn't visible from the screenshot (it was a single
string in a list). This wrapper concatenates prior turns into that list
as a best-effort approximation -- confirm the real multi-turn contract
and adjust _build_contents() if it differs.
"""

import json
import os
import uuid
from typing import Any, List, Optional

import requests
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

load_dotenv()

TOOL_CALL_INSTRUCTIONS = """
You have access to the following tools. When you need to call one, respond
with ONLY a single JSON object in exactly this shape and nothing else
(no markdown fences, no extra text):

{{"tool_call": {{"name": "<tool name>", "arguments": {{...}}}}}}

When you are done and have a final answer for the user, respond with plain
text only -- do not wrap it in JSON.

Available tools:
{tool_descriptions}
"""


def _describe_tools(tools) -> str:
    lines = []
    for t in tools:
        name = getattr(t, "name", None) or t.get("name")
        desc = getattr(t, "description", None) or t.get("description", "")
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


def _build_contents(messages: List[BaseMessage]) -> List[str]:
    """
    Best-effort flattening of LangChain message history into the gateway's
    flat `contents: [str, ...]` shape. Verify against the real API contract
    -- this assumes the gateway just wants a linear transcript of turns.
    """
    contents = []
    for m in messages:
        if isinstance(m, SystemMessage):
            continue  # handled separately via systemPrompt
        elif isinstance(m, HumanMessage):
            contents.append(str(m.content))
        elif isinstance(m, AIMessage):
            contents.append(f"[assistant]: {m.content}")
        elif isinstance(m, ToolMessage):
            contents.append(f"[tool result for {m.tool_call_id}]: {m.content}")
        else:
            contents.append(str(m.content))
    return contents


class InternalGatewayChatModel(BaseChatModel):
    """LangChain chat model wrapping the internal generative-ai gateway."""

    client_key: str
    pass_key: str
    endpoint_url: str
    model_id: str
    email: str
    llm_config: dict = {}
    base_system_prompt: str = "Hello, please answer the user's question kindly."
    bound_tools: Optional[list] = None

    @property
    def _llm_type(self) -> str:
        return "internal-gateway"

    def bind_tools(self, tools, **kwargs):
        """
        The gateway has no native tools param, so binding just stores the
        tool list -- _generate() injects tool descriptions into systemPrompt
        and parses the response for the simulated tool-call JSON shape.
        """
        new_instance = self.__class__(**{**self._identifying_params, **{
            "client_key": self.client_key,
            "pass_key": self.pass_key,
            "endpoint_url": self.endpoint_url,
            "model_id": self.model_id,
            "email": self.email,
            "llm_config": self.llm_config,
            "base_system_prompt": self.base_system_prompt,
        }})
        new_instance.bound_tools = tools
        return new_instance

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        system_prompt = self.base_system_prompt
        explicit_system = next((m.content for m in messages if isinstance(m, SystemMessage)), None)
        if explicit_system:
            system_prompt = explicit_system

        if self.bound_tools:
            system_prompt = system_prompt + "\n\n" + TOOL_CALL_INSTRUCTIONS.format(
                tool_descriptions=_describe_tools(self.bound_tools)
            )

        headers = {
            "x-generative-ai-client": self.client_key,
            "x-openapi-token": self.pass_key,
            "x-generative-ai-user-email": self.email,
        }
        body = {
            "modelIds": [self.model_id],
            "contents": _build_contents(messages),
            "llmConfig": self.llm_config,
            "isStream": False,
            "systemPrompt": system_prompt,
        }

        response = requests.post(self.endpoint_url, headers=headers, json=body, timeout=120)
        response.raise_for_status()
        data = response.json()

        # NOTE: adjust this extraction to match your gateway's real response
        # shape -- placeholder assumes a `.get("content")`-style field.
        raw_text = data.get("content") or data.get("text") or json.dumps(data)

        ai_message = self._parse_response_text(raw_text)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def _parse_response_text(self, raw_text: str) -> AIMessage:
        stripped = raw_text.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and "tool_call" in parsed:
                call = parsed["tool_call"]
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": call["name"],
                        "args": call.get("arguments", {}),
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                    }],
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        # Not a tool call -- treat as the final answer.
        return AIMessage(content=raw_text)


def load_settings(path="./config/settings.yaml"):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def get_llm(settings=None):
    """
    Same signature as before (llm/ollama_client.get_llm) -- this is why
    nothing else in the codebase needs to change. Credentials come from
    the .env file, matching your existing message_api.py convention.
    """
    settings = settings or load_settings()
    return InternalGatewayChatModel(
        client_key=os.getenv("CLIENT_KEY"),
        pass_key=os.getenv("PASS_KEY"),
        endpoint_url=f"{os.getenv('ENDPOINT_URL')}/openapi/chat/v1/messages",
        model_id=os.getenv("MODEL_ID_GEMMA4"),
        email=os.getenv("EMAIL"),
        llm_config={
            "max_new_tokens": settings.get("max_new_tokens", 2024),
            "seed": settings.get("seed", None),
            "top_k": settings.get("top_k", 14),
            "top_p": settings.get("top_p", 0.94),
            "temperature": settings.get("temperature", 0.4),
            "repetition_penalty": settings.get("repetition_penalty", 1.04),
        },
    )


def check_tool_calling_support(llm):
    """
    Run this against 2-3 real repos before trusting the pipeline with it.
    Since tool calling here is simulated via prompted JSON, reliability
    will vary more than with a native function-calling API.
    """
    from langchain_core.tools import tool

    @tool
    def ping(x: str) -> str:
        """Echo back the input string."""
        return x

    bound = llm.bind_tools([ping])
    resp = bound.invoke([HumanMessage(content="Call the ping tool with x='hello'.")])
    has_tool_calls = bool(getattr(resp, "tool_calls", None))
    return {"tool_calls_detected": has_tool_calls, "raw_response": resp}
