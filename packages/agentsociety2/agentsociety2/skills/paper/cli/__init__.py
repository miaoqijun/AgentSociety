"""CLI entry points for the paper-orchestrator harness.

Submodules are imported lazily to avoid forcing the full ``agentsociety2``
package initialization (which validates ``AGENTSOCIETY_LLM_API_KEY`` at
load time) when callers only want :func:`generate_paper.main` for
non-LLM work.
"""

__all__ = ["generate_paper", "interactive_meta"]
