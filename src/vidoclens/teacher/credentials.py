"""Runtime-only credential loading. Never returns file content to diagnostics/logs."""

import os
from pathlib import Path


def load_api_key(root: Path, env_file: Path | None = None) -> str:
    """Explicit --env-file reads only OPENAI_API_KEY; no eval, expansion or env mutation."""
    if env_file is None:
        value = os.environ.get("OPENAI_API_KEY", "").strip()
    else:
        path = root / env_file
        try:
            if path.stat().st_size > 65536:
                raise ValueError
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError, ValueError):
            raise ValueError("Credential file missing, unreadable or oversized") from None
        values = []
        for line in lines:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            name, separator, raw = line.partition("=")
            if not separator or name.strip() != "OPENAI_API_KEY":
                continue
            raw = raw.strip()
            if raw[:1] in {"'", '"'}:
                quote = raw[0]
                value, closing, suffix = raw[1:].partition(quote)
                if not closing or (suffix.strip() and not suffix.strip().startswith("#")):
                    raise ValueError("Malformed credential assignment; value omitted")
            else:
                value = raw.split(" #", 1)[0].strip()
            values.append(value)
        if len(values) != 1:
            raise ValueError("Credential file must define OPENAI_API_KEY exactly once")
        value = values[0]
    if not value or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError("API key missing or contains invalid whitespace; value omitted")
    return value
