"""Python static dependency analysis via the stdlib ``ast`` module.

For each ``.py`` file that was **changed** by the PR, this module parses
the file's *current content* (if available) and extracts all top-level
import statements.  Only files whose source is explicitly provided are
analysed — no filesystem access is performed by default, making the
engine safe to run in any context.

Design constraints (from codedocket ``review.pipeline``):
- Results must be deterministic and reproducible.
- No LLM inference; only standard-library AST walking.
- Missing source → no edges emitted for that file (never inferred).
"""
from __future__ import annotations

import ast
import logging
from typing import Mapping

from app.facts.models import DependencyEdge, ImportKind

logger = logging.getLogger(__name__)


def _ast_imports(source: str, file_path: str) -> list[DependencyEdge]:
    """Walk the AST of *source* and return all import edges.

    Handles both ``import X`` and ``from X import Y`` forms, including
    relative imports (``from . import util``, ``from ..base import Foo``).

    Parse errors are logged and return an empty list — they must not
    propagate as exceptions.
    """
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        logger.warning(
            "python_deps: skipping %r — syntax error at line %s: %s",
            file_path,
            exc.lineno,
            exc.msg,
        )
        return []

    edges: list[DependencyEdge] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # ``import foo, bar.baz``
            for alias in node.names:
                edges.append(
                    DependencyEdge(
                        from_file=file_path,
                        imported_module=alias.name,
                        import_kind=ImportKind.absolute,
                        lineno=node.lineno,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            # ``from foo import bar``  or  ``from . import baz``
            level = node.level or 0  # number of leading dots for relative imports
            module = node.module or ""
            if level > 0:
                kind = ImportKind.relative
                if module:
                    # ``from .models import Foo``  →  ".models"
                    dotted = "." * level + module
                    edges.append(
                        DependencyEdge(
                            from_file=file_path,
                            imported_module=dotted,
                            import_kind=kind,
                            lineno=node.lineno,
                        )
                    )
                else:
                    # ``from . import name1, name2``  — no module, emit one edge
                    # per imported name so callers know which symbols are imported.
                    for alias in node.names:
                        edges.append(
                            DependencyEdge(
                                from_file=file_path,
                                imported_module="." * level + alias.name,
                                import_kind=kind,
                                lineno=node.lineno,
                            )
                        )
            else:
                if module:
                    edges.append(
                        DependencyEdge(
                            from_file=file_path,
                            imported_module=module,
                            import_kind=ImportKind.absolute,
                            lineno=node.lineno,
                        )
                    )

    return edges


def extract_python_deps(
    changed_py_files: list[str],
    file_source_map: Mapping[str, str],
) -> tuple[DependencyEdge, ...]:
    """Return import edges for all Python files in *changed_py_files*.

    Parameters
    ----------
    changed_py_files:
        List of file paths (e.g. ``["app/models.py", "tests/test_foo.py"]``)
        that were touched by the PR.  Only ``.py`` files are analysed.
    file_source_map:
        Mapping from file path to source text.  Files absent from this
        mapping are skipped — no edges are emitted for them, and no
        ``unknown`` placeholder is synthesised.  This is deliberate: the
        engine never fabricates dependency information.

    Returns
    -------
    tuple[DependencyEdge, ...]
        All edges found, in file-path order then line-number order within
        each file.
    """
    all_edges: list[DependencyEdge] = []
    for path in changed_py_files:
        if not path.endswith(".py"):
            continue
        source = file_source_map.get(path)
        if source is None:
            logger.debug(
                "python_deps: no source provided for %r — skipping dependency analysis",
                path,
            )
            continue
        edges = _ast_imports(source, path)
        all_edges.extend(edges)

    return tuple(all_edges)
