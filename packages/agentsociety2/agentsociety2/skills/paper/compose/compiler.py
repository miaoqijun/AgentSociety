"""Run ``latexmk`` and surface a structured :class:`CompileResult`.

Plan rule (Phase 2):

    subprocess.run([latexmk, -pdf, -interaction=nonstopmode,
                    -bibtex-cond, -outdir=out, main.tex],
                   cwd=compose_dir)

When ``shutil.which('latexmk')`` is ``None`` the function raises
:class:`CompileError` with explicit guidance to run inside the
agentsociety Docker image (where Phase 0 added ``latexmk biber
texlive-bibtex-extra`` to the apt list).

Returns a :class:`CompileResult` populated with:

- ``pdf_path`` - resolved path to ``out/<stem>.pdf`` if it exists
- ``log_path`` - path to ``out/<stem>.log``
- ``success`` - ``True`` iff exit code is 0, the PDF exists, and the log
  contains no release-blocking warnings such as undefined references or an
  empty bibliography
- ``errors`` - lines from latexmk stderr / log when the PDF is missing or
  the log contains release-blocking warnings
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

from agentsociety2.skills.paper.models import CompileResult


_LATEXMK_GUIDANCE = (
    "latexmk not found. Run inside agentsociety Docker image, "
    "or install TeX Live + latexmk + biber locally."
)


class CompileError(RuntimeError):
    """Raised when latexmk is unavailable or compilation cannot start."""


def _default_args(main_tex_name: str, *, out_dir: str = "out") -> List[str]:
    return [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
        "-bibtex-cond",
        f"-outdir={out_dir}",
        main_tex_name,
    ]


def compile(
    compose_dir: Path | str,
    *,
    main_tex: str = "main.tex",
    out_subdir: str = "out",
    timeout: Optional[float] = 600.0,
    extra_args: Optional[Sequence[str]] = None,
) -> CompileResult:
    """Compile ``main_tex`` inside ``compose_dir`` via latexmk.

    Raises :class:`CompileError` immediately when ``latexmk`` is missing
    from ``PATH``.  Subprocess failures are captured as
    :class:`CompileResult` instances so the orchestrator can decide how
    to react (vs. tearing down the whole skill on a transient TeX error).
    """

    if shutil.which("latexmk") is None:
        raise CompileError(_LATEXMK_GUIDANCE)

    compose_path = Path(compose_dir)
    main_tex_path = compose_path / main_tex
    if not main_tex_path.exists():
        raise CompileError(f"main TeX not found: {main_tex_path}")

    args = _default_args(main_tex, out_dir=out_subdir)
    if extra_args:
        args.extend(extra_args)

    proc = subprocess.run(
        args,
        cwd=str(compose_path),
        capture_output=True,
        # Capture as bytes; TeX logs are not always UTF-8 clean (latexmk
        # mixes its own log lines with TeX engine output, which may include
        # non-UTF-8 bytes).  We decode with errors="replace" downstream.
        text=False,
        timeout=timeout,
    )

    stderr_text = (proc.stderr or b"").decode("utf-8", errors="replace")

    out_dir = compose_path / out_subdir
    pdf_stem = Path(main_tex).stem
    pdf_path = out_dir / f"{pdf_stem}.pdf"
    log_path = out_dir / f"{pdf_stem}.log"

    log_text = ""
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")

    blockers = _extract_log_blockers(log_text)
    success = proc.returncode == 0 and pdf_path.exists() and not blockers
    errors: List[str] = []
    if not success:
        if stderr_text:
            errors.extend(line for line in stderr_text.splitlines() if line.strip())
        if log_text:
            errors.extend(_extract_log_errors(log_text))
            errors.extend(blockers)
        if not pdf_path.exists() and proc.returncode == 0:
            errors.append(
                "latexmk reported success but the PDF is missing at "
                f"{pdf_path}"
            )

    return CompileResult(
        pdf_path=str(pdf_path) if pdf_path.exists() else None,
        log_path=str(log_path) if log_path.exists() else None,
        success=success,
        errors=errors,
    )


def _extract_log_errors(log_text: str, *, max_lines: int = 25) -> List[str]:
    """Pull ``! ...`` error lines and the next line of context out of a TeX log."""

    out: List[str] = []
    lines = log_text.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith("!"):
            continue
        chunk = [line]
        if idx + 1 < len(lines):
            chunk.append(lines[idx + 1])
        out.append(" / ".join(chunk).strip())
        if len(out) >= max_lines:
            break
    return out


def _extract_log_blockers(log_text: str) -> List[str]:
    """Return release-blocking warnings from a TeX log.

    ``latexmk`` can exit with code 0 while still producing a manuscript with
    broken figure references or an empty bibliography.  Those cases are fatal
    for the paper harness and should block the compile stage.
    """

    if not log_text:
        return []

    blockers: List[str] = []
    for line in log_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "LaTeX Warning: Empty bibliography" in stripped:
            blockers.append(stripped)
        elif "LaTeX Warning: There were undefined references." in stripped:
            blockers.append(stripped)
        elif "LaTeX Warning: Citation `" in stripped and " undefined" in stripped:
            blockers.append(stripped)
        elif "LaTeX Warning: Reference `" in stripped and " undefined" in stripped:
            blockers.append(stripped)

    deduped: List[str] = []
    seen: set[str] = set()
    for item in blockers:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


__all__ = [
    "CompileError",
    "compile",
]
