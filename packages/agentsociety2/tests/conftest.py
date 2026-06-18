import os


def _ensure_llm_env_for_tests() -> None:
    # Disable telemetry before any imports
    os.environ.setdefault("MEM0_TELEMETRY", "False")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

    if not (os.environ.get("AGENTSOCIETY_LLM_API_KEY") or "").strip():
        os.environ["AGENTSOCIETY_LLM_API_KEY"] = "test-key"
    if not (os.environ.get("AGENTSOCIETY_LLM_API_BASE") or "").strip():
        os.environ["AGENTSOCIETY_LLM_API_BASE"] = "https://api.openai.com/v1"
    # Use a synchronous trace writer under pytest so span reads are deterministic
    # (no need to flush a background thread before asserting on trace files).
    os.environ.setdefault("AGENTSOCIETY_TRACE_WRITER_ASYNC", "0")


_ensure_llm_env_for_tests()
