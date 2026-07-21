"""Model provider switch — supports OpenAI, Ollama (local/free), and a mock.

Controlled by env vars:
    MODEL_PROVIDER = openai | ollama | mock   (default: mock)
    OPENAI_API_KEY = sk-...                    (for openai)
    OPENAI_MODEL   = gpt-4o-mini               (optional)
    OLLAMA_MODEL   = llama3.1                   (optional, must support tools)
    OLLAMA_BASE_URL= http://localhost:11434     (optional)

'mock' needs no API key or install and is used for offline demos/tests.
"""
from __future__ import annotations

import os


def get_model():
    provider = os.getenv("MODEL_PROVIDER", "mock").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
        )

    if provider == "ollama":
        # Requires: `ollama pull llama3.1` and a model that supports tool calling.
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )

    if provider == "mock":
        from mock_model import MockToolCallingModel
        return MockToolCallingModel()

    raise ValueError(f"Unknown MODEL_PROVIDER '{provider}' (use openai | ollama | mock)")
