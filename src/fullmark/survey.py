"""`serve_survey`: serve a survey page once and return the answers (library entry point)."""

from __future__ import annotations

import io
import json
import os
from argparse import Namespace
from collections.abc import Callable
from pathlib import Path

from .build import build_html
from .serve import default_out, serve_loop
from .validate import load_quiz


class SurveyError(Exception):
    """The survey could not be built, served or read back."""


class SurveyTimeout(SurveyError):
    """No answers arrived before the timeout."""


def serve_survey(
    md_path: str | os.PathLike,
    *,
    out: str | os.PathLike | None = None,
    timeout: int = 1800,
    open_browser: bool = True,
    on_url: Callable[[str], None] | None = None,
    port: int | None = None,
) -> dict:
    """Do what `quiz serve FILE --once --out OUT --timeout T [--open]` does, and return
    the parsed results JSON. `timeout` is in seconds; 0 waits forever. Prints nothing."""
    path = Path(md_path)
    if not path.is_file():
        raise SurveyError(f"no such file: {path}")
    try:
        quiz, findings, _ = load_quiz(path)
        if findings.has_errors or quiz is None:
            lines = [f.format() for f in findings.sorted()]
            raise SurveyError("fix the survey errors first:\n" + "\n".join(lines))
        result = build_html(quiz, path.parent)
    except (OSError, UnicodeDecodeError) as exc:
        raise SurveyError(f"cannot read {path}: {exc}") from exc
    if result.errors:
        raise SurveyError("cannot build the survey:\n" + "\n".join(result.errors))
    target = Path(out) if out else default_out(path, quiz.id)
    args = Namespace(
        once=True, timeout=timeout, open=open_browser, port=port or 0, autosave=None
    )
    try:
        server, status = serve_loop(
            result.html,
            quiz.id,
            target,
            args,
            io.StringIO(),
            ready=on_url,
            quiz_hash=quiz.source_hash,
        )
    except OSError as exc:
        raise SurveyError(f"cannot listen on 127.0.0.1:{port or 0}: {exc}") from exc
    if not server.paths:
        raise SurveyTimeout(f"no answers arrived within {timeout} s")
    try:
        return json.loads(server.paths[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SurveyError(f"cannot read the results: {exc}") from exc
