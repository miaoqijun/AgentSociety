"""
Segment parsing and template-ID mapping.

Parses FormatPrompt template strings into structured segments (static / var),
and maintains a reverse mapping from template-string → module-level constant
name for generating `template_id` values (e.g. "needs_block.INITIAL_NEEDS_PROMPT").
"""

import ast
import inspect
import os
import re
from typing import Any, Optional


# ── Template-ID registry ──────────────────────────────────────────────────
# Build by scanning block modules at import time.
# Maps template-string → "module.CONST_NAME"

_template_registry: dict[str, str] = {}
"""Global registry: full template string → 'module.CONSTANT_NAME'."""

_registry_initialized: bool = False


def _discover_template_constants(paths: Optional[list[str]] = None) -> None:
    """Scan Python files for UPPER_SNAKE_CASE constants whose value contains
    FormatPrompt-like placeholders ({...} or ${...}) and register them.

    This is called once at import time.  If *paths* is None, it auto-detects
    the cityagent blocks directory.
    """
    global _registry_initialized
    if _registry_initialized:
        return

    if paths is None:
        # Auto-detect the cityagent blocks directory relative to this file
        this_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.dirname(this_dir)  # agentsociety/
        paths = [
            os.path.join(base, "cityagent", "blocks"),
            os.path.join(base, "cityagent"),
            os.path.join(base, "agent"),
        ]

    for scan_dir in paths:
        if not os.path.isdir(scan_dir):
            continue
        for fname in sorted(os.listdir(scan_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            module_name = fname[:-3]  # strip ".py"
            fpath = os.path.join(scan_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    source = f.read()
            except Exception:
                continue
            try:
                tree = ast.parse(source, filename=fpath)
            except SyntaxError:
                continue
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            # Check if value is a string constant with placeholders
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                val: str = node.value.value
                                if "{" in val and ("{var}" not in val):
                                    _template_registry[val] = f"{module_name}.{target.id}"
                            elif isinstance(node.value, ast.JoinedStr):
                                # f-strings that contain placeholders — only record
                                # if they look like template patterns
                                val_parts = []
                                has_placeholder = False
                                for part in node.value.values:
                                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                                        val_parts.append(part.value)
                                    else:
                                        has_placeholder = True
                                if has_placeholder:
                                    _template_registry["<fstring>"] = f"{module_name}.{target.id}"

    _registry_initialized = True


def lookup_template_id(template: str) -> Optional[str]:
    """Return the template id for a template string, or None if unknown."""
    if not _registry_initialized:
        _discover_template_constants()
    for tmpl, tid in _template_registry.items():
        # Normalize by collapsing whitespace for comparison
        if _normalize(tmpl) == _normalize(template):
            return tid
    return None


def _normalize(s: str) -> str:
    """Collapse whitespace for fuzzy template matching."""
    return re.sub(r"\s+", " ", s).strip()


# ── Segment parsing ───────────────────────────────────────────────────────
# Patterns for the two placeholder syntaxes used by FormatPrompt:
#   {var}        → simple str.format variable
#   ${expr}      → expression evaluated against memory/context

VAR_PATTERN = re.compile(r"\{(\w+)\}")
EXPR_PATTERN = re.compile(r"\$\{([^}]+?)\}")


async def parse_template_to_segments(
    template: str,
    kwargs: dict[str, Any],
    context: Optional[dict] = None,
    memory_status: Any = None,
) -> list[dict]:
    """Parse a FormatPrompt template string into a list of segment dicts.

    Args:
        template: The raw template string (e.g. "Gender: {gender}, Age: {age}").
        kwargs: The keyword arguments passed to FormatPrompt.format().
        context: The context dict (if any) passed to FormatPrompt.format().
        memory_status: The memory.status object (for ${status.xxx} resolution).

    Returns:
        A list of segment dicts in the schema:
            {"kind": "static", "text": "..."}
            {"kind": "var", "source": str, "key": str, "text": str}
    """
    segments: list[dict] = []

    # We tokenize the template by splitting on both {var} and ${expr} patterns.
    # Combined regex: capture groups for both patterns
    combined_pattern = re.compile(r"(\$\{[^}]+\}|\{\w+\})")
    pos = 0

    for match in combined_pattern.finditer(template):
        # Static text before this placeholder
        if match.start() > pos:
            static_text = template[pos : match.start()]
            segments.append({"kind": "static", "text": static_text})

        # Placeholder
        placeholder = match.group(0)
        if placeholder.startswith("${"):
            # Expression placeholder
            expr = placeholder[2:-1].strip()
            source, key, text = await _resolve_expression(expr, context, memory_status)
            segments.append({
                "kind": "var",
                "source": source,
                "key": key,
                "text": text,
            })
        else:
            # Simple {var} placeholder
            var_name = placeholder[1:-1]
            text = kwargs.get(var_name, "")
            source, key = _classify_var(var_name)
            segments.append({
                "kind": "var",
                "source": source,
                "key": var_name,
                "text": str(text) if text is not None else "",
            })

        pos = match.end()

    # Trailing static text
    if pos < len(template):
        segments.append({"kind": "static", "text": template[pos:]})

    return segments


async def _resolve_expression(
    expr: str, context: Optional[dict], memory_status: Any
) -> tuple[str, str, str]:
    """Resolve a ${expr} placeholder to (source, key, text)."""
    # profile.xxx
    if expr.startswith("profile."):
        key = expr.split(".", 1)[1]
        source = "profile"
        text = await _safe_get(memory_status, key) if memory_status else ""
        return source, key, str(text) if text is not None else ""

    # status.xxx  or  memory.status.xxx
    if expr.startswith("status.") or expr.startswith("memory.status."):
        prefix = "status." if expr.startswith("status.") else "memory.status."
        key = expr.split(prefix, 1)[1]
        source = "memory.status"
        text = await _safe_get(memory_status, key) if memory_status else ""
        return source, key, str(text) if text is not None else ""

    # context.xxx
    if expr.startswith("context."):
        key = expr.split(".", 1)[1]
        source = "context"
        text = context.get(key, "") if context else ""
        return source, key, str(text) if text is not None else ""

    # Fallback — treat as context
    source = "context"
    key = expr
    text = context.get(expr, "") if context else ""
    return source, key, str(text) if text is not None else ""


def _classify_var(var_name: str) -> tuple[str, str]:
    """Classify a simple {var} into a source category."""
    # Common profile variable names in AgentSociety
    PROFILE_KEYS = {
        "gender", "age", "education", "occupation", "personality",
        "background_story", "income", "consumption", "race",
        "name", "marriage_status",
    }
    if var_name in PROFILE_KEYS:
        return "profile", var_name
    return "format_kwarg", var_name


async def _safe_get(obj: Any, key: str, default: Any = "") -> Any:
    """Safely get a dotted attribute from an object (which may be a dict)."""
    parts = key.split(".")
    current = obj
    for part in parts:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(part, default)
        elif hasattr(current, "get"):
            try:
                current = current.get(part, default)
                if inspect.isawaitable(current):
                    current = await current
            except Exception:
                return default
        else:
            return default
    return current


# ── Helper for inline f-string annotation ─────────────────────────────────


def make_segments(parts: list[tuple[str, Optional[dict]]]) -> list[dict]:
    """Build a segments list from annotated (text, meta) pairs.

    Used to annotate inline f-string sites (see §6.4 (a) of the design doc).

    Args:
        parts: A list of (text, meta) tuples where:
              - text: The rendered string fragment.
              - meta: None for static fragments, or a dict like
                      {"source": "memory.status", "key": "emotion"}
                      for variable fragments.

    Returns:
        A list of segment dicts.
    """
    return [
        {"kind": "static", "text": text}
        if meta is None
        else {"kind": "var", "text": text, **meta}
        for text, meta in parts
    ]
