import os


def models():
    default = os.getenv("LLM_MODEL", "gpt-4o-mini")
    return list(dict.fromkeys([default] + [m.strip() for m in os.getenv("LLM_MODELS", default).split(",") if m.strip()]))


