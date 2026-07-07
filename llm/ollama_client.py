"""
llm/ollama_client.py

Wraps the local Ollama-hosted Gemma model as a LangChain chat model.
Everything downstream (create_react_agent, tool binding) works against
this the same way it would with any other LangChain chat model -- this
is the ONLY file you touch if you later switch providers.
"""

import yaml
from langchain_ollama import ChatOllama


def load_settings(path="./config/settings.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def get_llm(settings=None):
    settings = settings or load_settings()
    llm = ChatOllama(
        model=settings.get("model_tag", "gemma2:27b"),
        base_url=settings.get("ollama_host", "http://localhost:11434"),
        temperature=settings.get("temperature", 0),
    )
    return llm


def check_tool_calling_support(llm):
    """
    Quick sanity check to run once before trusting native tool-calling.
    Gemma via Ollama can be inconsistent here -- call this in a throwaway
    script against 2-3 real repos before relying on it in the full pipeline.
    """
    from langchain_core.tools import tool

    @tool
    def ping(x: str) -> str:
        """Echo back the input string."""
        return x

    bound = llm.bind_tools([ping])
    resp = bound.invoke("Call the ping tool with x='hello'.")
    has_tool_calls = bool(getattr(resp, "tool_calls", None))
    return {"tool_calls_detected": has_tool_calls, "raw_response": resp}
