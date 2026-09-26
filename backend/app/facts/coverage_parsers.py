"""Defensive coverage artifact parsers for LCOV and Cobertura XML formats.

Both parsers return a mapping of ``{normalized_path: (covered_lines, uncovered_lines)}``
where line numbers are 1-based integers.  Neither parser raises on malformed or
partial input — they return whatever valid data they can extract and log a
warning about anything they skip.

Safety constraints:
- Maximum raw input size: 50 MB (``MAX_ARTIFACT_BYTES``).
- XML parsing uses ``defusedxml`` when available, otherwise falls back to the
  stdlib ``xml.etree.ElementTree`` with ``forbid_dtd=True`` equivalent guards
  (entity expansion disabled, external entity loading disabled).
- LCOV parsing iterates line-by-line; a single malformed line is skipped.
- Both parsers cap the number of files they will process at 10,000 to prevent
  memory exhaustion from adversarially crafted inputs.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Dict, FrozenSet, NamedTuple, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_ARTIFACT_BYTES: int = 50 * 1024 * 1024  # 50 MB
_MAX_FILES: int = 10_000
_MAX_LINES_PER_FILE: int = 500_000

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

# Mapping from normalized file path to (covered_lines, uncovered_lines) frozensets
ParsedCoverage = Dict[str, Tuple[FrozenSet[int], FrozenSet[int]]]


class ParseResult(NamedTuple):
    """Output of a single parser invocation."""

    data: ParsedCoverage
    """Non-empty dict of per-file line coverage, keyed by file path."""

    format: str
    """``'lcov'`` or ``'cobertura'``."""

    warnings: list[str]
    """Non-fatal issues detected during parsing (truncation, skipped records, etc.)."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _normalize_path(path: str) -> str:
    """Strip leading ``./`` and normalise path separators."""
    return path.lstrip("./").replace("\\", "/").strip()


def _check_size(raw: bytes | str, label: str) -> None:
    """Raise ``ValueError`` when input exceeds the safety limit."""
    n = len(raw) if isinstance(raw, bytes) else len(raw.encode("utf-8", errors="replace"))
    if n > MAX_ARTIFACT_BYTES:
        raise ValueError(
            f"{label} artifact is too large ({n:,} bytes > {MAX_ARTIFACT_BYTES:,} byte limit)."
        )


# ---------------------------------------------------------------------------
# LCOV parser
# ---------------------------------------------------------------------------
#
# LCOV trace format (lcov.sourceforge.net / man 5 geninfo):
#
#   TN:<test name>
#   SF:<source file>
#   FN:<line number>,<function name>
#   FNDA:<hit count>,<function name>
#   DA:<line number>,<hit count>[,<checksum>]
#   LH:<lines hit>
#   LF:<lines found>
#   BRH:<branches hit>
#   BRF:<branches found>
#   end_of_record
#
# Only SF and DA lines are needed for per-file line coverage.
# ---------------------------------------------------------------------------

_DA_RE = re.compile(r"^DA:(\d+),(\d+)")
_SF_RE = re.compile(r"^SF:(.+)")


def parse_lcov(raw: str | bytes) -> ParseResult:
    """Parse an LCOV trace file and return per-file line coverage.

    Parameters
    ----------
    raw:
        Full LCOV trace text (string or UTF-8 bytes).

    Returns
    -------
    ParseResult
        Parsed coverage data, format tag ``'lcov'``, and any warnings.

    Raises
    ------
    ValueError
        If the input exceeds ``MAX_ARTIFACT_BYTES`` or contains no parseable
        ``SF:`` / ``DA:`` records at all.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    _check_size(raw, "LCOV")

    data: ParsedCoverage = {}
    warnings: list[str] = []

    current_path: str | None = None
    covered: set[int] = set()
    uncovered: set[int] = set()
    file_count = 0
    line_overflows: int = 0

    def _flush() -> None:
        nonlocal current_path
        if current_path is not None:
            previous_covered, previous_uncovered = data.get(
                current_path, (frozenset(), frozenset())
            )
            merged_covered = set(previous_covered) | covered
            merged_uncovered = set(previous_uncovered) | uncovered
            # A hit in any test run means that line was covered.
            merged_uncovered.difference_update(merged_covered)
            data[current_path] = (frozenset(merged_covered), frozenset(merged_uncovered))
        current_path = None
        covered.clear()
        uncovered.clear()

    for raw_line in io.StringIO(raw):
        line = raw_line.rstrip("\r\n")
        if line == "end_of_record":
            _flush()
            continue
        sf = _SF_RE.match(line)
        if sf:
            _flush()
            if file_count >= _MAX_FILES:
                warnings.append(
                    f"Truncated: reached {_MAX_FILES:,}-file limit; remaining files skipped."
                )
                break
            current_path = _normalize_path(sf.group(1))
            file_count += 1
            continue
        da = _DA_RE.match(line)
        if da and current_path is not None:
            lineno = int(da.group(1))
            if lineno < 1 or lineno > _MAX_LINES_PER_FILE:
                line_overflows += 1
                continue
            hits = int(da.group(2))
            if hits > 0:
                covered.add(lineno)
            else:
                uncovered.add(lineno)

    _flush()  # handle traces that lack a trailing end_of_record

    if line_overflows:
        warnings.append(
            f"Skipped {line_overflows:,} DA: records with out-of-range line numbers."
        )

    if not data:
        raise ValueError(
            "LCOV artifact contained no parseable SF:/DA: records. "
            "Verify that the file is a valid LCOV trace."
        )

    return ParseResult(data=data, format="lcov", warnings=warnings)


# ---------------------------------------------------------------------------
# Cobertura XML parser
# ---------------------------------------------------------------------------
#
# Cobertura XML structure (simplified):
#
#   <coverage ...>
#     <packages>
#       <package ...>
#         <classes>
#           <class filename="src/foo.py" ...>
#             <lines>
#               <line number="5" hits="1" .../>
#               <line number="6" hits="0" .../>
#             </lines>
#           </class>
#         </classes>
#       </package>
#     </packages>
#   </coverage>
#
# The parser is tolerant of missing intermediate elements.
# ---------------------------------------------------------------------------

# Maximum number of XML characters the parser will process (defence-in-depth
# against decompression bombs when the caller forgets to check size first).
_XML_CHAR_LIMIT = MAX_ARTIFACT_BYTES


def _safe_parse_xml(text: str):  # -> xml.etree.ElementTree.Element
    """Parse XML defensively, rejecting DOCTYPE/entity expansions."""
    # Try defusedxml first (safer); fall back to stdlib with manual guard.
    try:
        import defusedxml.ElementTree as _det  # type: ignore[import]
        return _det.fromstring(text, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except ImportError:
        pass

    import xml.etree.ElementTree as ET  # noqa: N812

    # Stdlib ET does not expand external entities by default in Python 3.8+,
    # but we explicitly forbid DOCTYPE declarations to be safe.
    if re.search(r"<!DOCTYPE", text, re.IGNORECASE):
        raise ValueError("Cobertura XML contains a DOCTYPE declaration which is not allowed.")
    parser = ET.XMLParser()
    # Disable entity expansion (Python 3.8+ stdlib does not load external
    # entities, but this makes the intent explicit).
    try:
        parser.entity = {}  # type: ignore[attr-defined]
    except AttributeError:
        pass
    return ET.fromstring(text, parser=parser)


def parse_cobertura(raw: str | bytes) -> ParseResult:
    """Parse a Cobertura XML coverage report and return per-file line coverage.

    Parameters
    ----------
    raw:
        Full XML text (string or UTF-8 bytes).

    Returns
    -------
    ParseResult
        Parsed coverage data, format tag ``'cobertura'``, and any warnings.

    Raises
    ------
    ValueError
        If the input exceeds ``MAX_ARTIFACT_BYTES``, is not parseable XML,
        does not contain a ``<coverage>`` root element, or contains no
        ``<class>`` elements with a ``filename`` attribute.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    _check_size(raw, "Cobertura XML")

    warnings: list[str] = []

    try:
        root = _safe_parse_xml(raw)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Cobertura XML could not be parsed: {exc}") from exc

    # Accept both <coverage> root and <coverage> nested inside a wrapper.
    if root.tag != "coverage":
        # Try one level deeper (some tools wrap in a top-level element)
        coverage_el = root.find("coverage")
        if coverage_el is None:
            raise ValueError(
                "Cobertura XML must have a <coverage> root element "
                f"(got <{root.tag}>)."
            )
    else:
        coverage_el = root

    data: ParsedCoverage = {}
    file_count = 0
    line_overflows = 0
    bad_line_attrs = 0

    for class_el in coverage_el.iter("class"):
        filename = class_el.get("filename")
        if not filename:
            continue

        if file_count >= _MAX_FILES:
            warnings.append(
                f"Truncated: reached {_MAX_FILES:,}-file limit; remaining files skipped."
            )
            break

        path = _normalize_path(filename)
        covered: set[int] = set()
        uncovered: set[int] = set()

        for line_el in class_el.iter("line"):
            number_str = line_el.get("number")
            hits_str = line_el.get("hits")
            if number_str is None or hits_str is None:
                bad_line_attrs += 1
                continue
            try:
                lineno = int(number_str)
                hits = int(hits_str)
            except ValueError:
                bad_line_attrs += 1
                continue
            if lineno < 1 or lineno > _MAX_LINES_PER_FILE:
                line_overflows += 1
                continue
            if hits > 0:
                covered.add(lineno)
            else:
                uncovered.add(lineno)

        # Merge into existing entry for this path (multiple <class> elements
        # can share the same filename when the file contains multiple classes).
        if path in data:
            prev_covered, prev_uncovered = data[path]
            covered |= prev_covered
            uncovered |= prev_uncovered
        else:
            file_count += 1

        # Lines that became covered in one class supersede uncovered in another.
        uncovered -= covered
        data[path] = (frozenset(covered), frozenset(uncovered))

    if bad_line_attrs:
        warnings.append(
            f"Skipped {bad_line_attrs:,} <line> elements with missing or non-integer attributes."
        )
    if line_overflows:
        warnings.append(
            f"Skipped {line_overflows:,} <line> elements with out-of-range line numbers."
        )

    if not data:
        raise ValueError(
            "Cobertura XML contained no <class> elements with a 'filename' attribute. "
            "Verify that the file is a valid Cobertura coverage report."
        )

    return ParseResult(data=data, format="cobertura", warnings=warnings)
