#!/usr/bin/env python3
"""Validate Agent class implementation.

Checks that an Agent file correctly implements the AgentBase interface.

Usage:
    $PYTHON_PATH .agentsociety/bin/ags.py create-agent --file custom/agents/my_agent.py
    $PYTHON_PATH .agentsociety/bin/ags.py create-agent --file custom/agents/my_agent.py --json
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_METHODS = ["ask", "step", "dump", "load"]
OPTIONAL_METHODS = ["init", "mcp_description", "get_system_prompt", "get_profile"]

# Subclass either one directly (PersonAgent subclasses AgentBase)
ALLOWED_DIRECT_BASES = frozenset({"AgentBase", "PersonAgent"})


def _base_names_from_expr(expr: ast.expr) -> set[str]:
    names: set[str] = set()
    if isinstance(expr, ast.Name):
        names.add(expr.id)
    elif isinstance(expr, ast.Attribute):
        names.add(expr.attr)
    elif isinstance(expr, ast.Subscript):
        names |= _base_names_from_expr(expr.value)
    return names


def _class_direct_agent_bases(class_def: ast.ClassDef) -> set[str]:
    out: set[str] = set()
    for base in class_def.bases:
        out |= _base_names_from_expr(base)
    return out & ALLOWED_DIRECT_BASES


def _audit_ask_env_calls(tree: ast.AST) -> list[str]:
    """Detect `ask_env(..., readonly=False, ..., template_mode=True)` pattern.

    This is the Pitfall P3 anti-pattern: stateful writes that engage the
    template cache (keyed on instruction-text similarity + variable names,
    NOT tool name) and can collide silently across writes.
    See references/pitfalls.md P3.
    """
    warnings_out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "ask_env"):
            continue
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        readonly_val = kw.get("readonly")
        template_val = kw.get("template_mode")
        if (
            isinstance(readonly_val, ast.Constant)
            and readonly_val.value is False
            and isinstance(template_val, ast.Constant)
            and template_val.value is True
        ):
            warnings_out.append(
                f"ask_env at line {node.lineno}: readonly=False with template_mode=True. "
                "This pattern caches a closure keyed on instruction-text similarity + "
                "argument names (NOT tool name) and can silently collide between writes. "
                "Default to template_mode=False for writes. See references/pitfalls.md P3."
            )
    return warnings_out


def validate_file(file_path: Path) -> dict[str, Any]:
    """Validate an Agent Python file.

    Returns a dict with:
    - valid: bool
    - errors: list of error messages
    - warnings: list of warning messages
    - class_name: str or None
    - has_mcp_description: bool
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "class_name": None,
        "has_mcp_description": False,
        "methods": {},
    }

    # Check file exists
    if not file_path.exists():
        result["valid"] = False
        result["errors"].append(f"File not found: {file_path}")
        return result

    # Check file is Python
    if file_path.suffix != ".py":
        result["valid"] = False
        result["errors"].append(f"Not a Python file: {file_path}")
        return result

    # Check not in examples directory
    if "examples" in file_path.parts:
        result["warnings"].append(
            "File is in 'examples' directory and will not be scanned for registration. "
            "Move it to custom/agents/ directly."
        )

    # Parse AST
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as e:
        result["valid"] = False
        result["errors"].append(f"Syntax error: {e}")
        return result

    # Find classes that directly extend AgentBase or PersonAgent
    agent_classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _class_direct_agent_bases(node):
            agent_classes.append(node)

    if not agent_classes:
        result["valid"] = False
        result["errors"].append(
            "No class inheriting from AgentBase or PersonAgent found "
            "(AST only recognizes direct bases named AgentBase or PersonAgent; "
            "if you use an alias, ensure the module imports and MRO still includes AgentBase)"
        )
        return result

    if len(agent_classes) > 1:
        result["warnings"].append(
            f"Multiple AgentBase subclasses found: {[c.name for c in agent_classes]}. "
            "Only the first will be validated."
        )

    # Validate first agent class
    agent_class = agent_classes[0]
    result["class_name"] = agent_class.name

    # Find methods
    methods = {}
    for node in agent_class.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods[node.name] = node

    result["methods"] = list(methods.keys())

    # Check required methods
    for method in REQUIRED_METHODS:
        if method not in methods:
            result["valid"] = False
            result["errors"].append(f"Missing required method: {method}")
        else:
            # Check if async
            method_node = methods[method]
            if not isinstance(method_node, ast.AsyncFunctionDef):
                result["valid"] = False
                result["errors"].append(f"Method '{method}' should be async")

    # Check mcp_description
    if "mcp_description" in methods:
        result["has_mcp_description"] = True
    else:
        result["warnings"].append(
            "No mcp_description() method. Agent will show generic description in module list."
        )

    # Pitfall P3 audit: template_mode=True with readonly=False
    for warn in _audit_ask_env_calls(tree):
        result["warnings"].append(warn)

    # Try to import and instantiate
    try:
        # Dynamic import
        module_name = f"validate_module_{id(file_path)}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find the class
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ == module_name and hasattr(obj, "__mro__"):
                    mro_names = [c.__name__ for c in obj.__mro__]
                    if "AgentBase" in mro_names and obj.__name__ == agent_class.name:
                        # Check it's not abstract
                        if inspect.isabstract(obj):
                            result["valid"] = False
                            result["errors"].append(
                                f"Class '{obj.__name__}' is abstract. "
                                "Implement all abstract methods."
                            )
                        break

            # Cleanup
            del sys.modules[module_name]
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"Could not import module: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate Agent implementation")
    parser.add_argument(
        "--file", "-f", type=str, required=True, help="Path to the Agent Python file"
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    file_path = Path(args.file)
    result = validate_file(file_path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Validation: {file_path}")
        print(f"{'='*60}")

        if result["class_name"]:
            print(f"\nClass: {result['class_name']}")

        if result["errors"]:
            print(f"\nErrors ({len(result['errors'])}):")
            for err in result["errors"]:
                print(f"  ✗ {err}")

        if result["warnings"]:
            print(f"\nWarnings ({len(result['warnings'])}):")
            for warn in result["warnings"]:
                print(f"  ⚠ {warn}")

        if result["valid"]:
            print(f"\n✓ Agent validation passed!")
            print("\nNext steps:")
            print("  1. Run VSCode command 'Scan Custom Modules'")
            print("  2. Run VSCode command 'Test Custom Modules'")
        else:
            print(f"\n✗ Validation failed. Fix the errors above.")

        print()

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
