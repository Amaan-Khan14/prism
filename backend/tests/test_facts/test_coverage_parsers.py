"""Tests for coverage parsers (LCOV and Cobertura XML).

All tests are synchronous, require no database, no network, and no
real filesystem access.  Every input is authored inline for clarity.
"""
from __future__ import annotations

import textwrap

import pytest

from app.facts.coverage_parsers import (
    MAX_ARTIFACT_BYTES,
    ParseResult,
    parse_cobertura,
    parse_lcov,
)


# ===========================================================================
# LCOV parser
# ===========================================================================


MINIMAL_LCOV = textwrap.dedent("""\
    TN:
    SF:src/app.py
    DA:1,1
    DA:2,0
    DA:3,1
    LH:2
    LF:3
    end_of_record
""")

MULTI_FILE_LCOV = textwrap.dedent("""\
    TN:test_suite
    SF:src/alpha.py
    DA:10,5
    DA:11,0
    end_of_record
    SF:src/beta.py
    DA:1,0
    DA:2,0
    end_of_record
""")


class TestParseLcov:
    def test_minimal_returns_parse_result(self) -> None:
        result = parse_lcov(MINIMAL_LCOV)
        assert isinstance(result, ParseResult)
        assert result.format == "lcov"

    def test_covered_lines_extracted(self) -> None:
        result = parse_lcov(MINIMAL_LCOV)
        covered, uncovered = result.data["src/app.py"]
        assert 1 in covered
        assert 3 in covered
        assert 2 not in covered

    def test_uncovered_lines_extracted(self) -> None:
        result = parse_lcov(MINIMAL_LCOV)
        covered, uncovered = result.data["src/app.py"]
        assert 2 in uncovered
        assert 1 not in uncovered

    def test_multi_file(self) -> None:
        result = parse_lcov(MULTI_FILE_LCOV)
        assert "src/alpha.py" in result.data
        assert "src/beta.py" in result.data

    def test_all_uncovered_file(self) -> None:
        result = parse_lcov(MULTI_FILE_LCOV)
        covered, uncovered = result.data["src/beta.py"]
        assert covered == frozenset()
        assert uncovered == frozenset({1, 2})

    def test_accepts_bytes_input(self) -> None:
        result = parse_lcov(MINIMAL_LCOV.encode("utf-8"))
        assert "src/app.py" in result.data

    def test_missing_end_of_record_still_parsed(self) -> None:
        # Trace that lacks trailing end_of_record
        text = "SF:src/x.py\nDA:1,1\n"
        result = parse_lcov(text)
        assert "src/x.py" in result.data

    def test_path_normalized(self) -> None:
        # Leading ./ should be stripped
        text = "SF:./src/app.py\nDA:5,1\nend_of_record\n"
        result = parse_lcov(text)
        assert "src/app.py" in result.data

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="no parseable"):
            parse_lcov("")

    def test_no_da_lines_produces_empty_entry(self) -> None:
        # An SF record with no DA lines produces an empty (no covered/uncovered) entry.
        # The file is still included so callers know it appeared in the artifact.
        result = parse_lcov("SF:src/x.py\nend_of_record\n")
        covered, uncovered = result.data["src/x.py"]
        assert covered == frozenset()
        assert uncovered == frozenset()

    def test_oversized_input_raises(self) -> None:
        oversized = b"x" * (MAX_ARTIFACT_BYTES + 1)
        with pytest.raises(ValueError, match="too large"):
            parse_lcov(oversized)

    def test_malformed_da_line_skipped(self) -> None:
        text = "SF:src/x.py\nDA:not_a_number,1\nDA:2,1\nend_of_record\n"
        # Should not raise; line 2 is still captured
        result = parse_lcov(text)
        covered, _ = result.data["src/x.py"]
        assert 2 in covered

    def test_warnings_empty_on_clean_input(self) -> None:
        result = parse_lcov(MINIMAL_LCOV)
        assert result.warnings == []

    def test_line_number_zero_skipped_with_warning(self) -> None:
        # DA:0 is invalid (1-based)
        text = "SF:src/x.py\nDA:0,1\nDA:5,1\nend_of_record\n"
        result = parse_lcov(text)
        assert len(result.warnings) >= 1
        covered, _ = result.data["src/x.py"]
        assert 0 not in covered
        assert 5 in covered

    def test_returns_frozensets(self) -> None:
        result = parse_lcov(MINIMAL_LCOV)
        covered, uncovered = result.data["src/app.py"]
        assert isinstance(covered, frozenset)
        assert isinstance(uncovered, frozenset)


# ===========================================================================
# Cobertura XML parser
# ===========================================================================


MINIMAL_COBERTURA = textwrap.dedent("""\
    <?xml version="1.0" ?>
    <coverage>
      <packages>
        <package>
          <classes>
            <class filename="src/app.py">
              <lines>
                <line number="1" hits="1"/>
                <line number="2" hits="0"/>
                <line number="3" hits="2"/>
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
""")

MULTI_CLASS_SAME_FILE = textwrap.dedent("""\
    <?xml version="1.0" ?>
    <coverage>
      <packages>
        <package>
          <classes>
            <class filename="src/app.py">
              <lines>
                <line number="1" hits="1"/>
                <line number="2" hits="0"/>
              </lines>
            </class>
            <class filename="src/app.py">
              <lines>
                <line number="3" hits="0"/>
                <line number="4" hits="1"/>
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
""")

MULTI_FILE_COBERTURA = textwrap.dedent("""\
    <?xml version="1.0" ?>
    <coverage>
      <packages>
        <package>
          <classes>
            <class filename="src/alpha.py">
              <lines>
                <line number="10" hits="5"/>
                <line number="11" hits="0"/>
              </lines>
            </class>
            <class filename="src/beta.py">
              <lines>
                <line number="1" hits="0"/>
                <line number="2" hits="0"/>
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
""")


class TestParseCobertura:
    def test_minimal_returns_parse_result(self) -> None:
        result = parse_cobertura(MINIMAL_COBERTURA)
        assert isinstance(result, ParseResult)
        assert result.format == "cobertura"

    def test_covered_lines_extracted(self) -> None:
        result = parse_cobertura(MINIMAL_COBERTURA)
        covered, uncovered = result.data["src/app.py"]
        assert 1 in covered
        assert 3 in covered

    def test_uncovered_lines_extracted(self) -> None:
        result = parse_cobertura(MINIMAL_COBERTURA)
        covered, uncovered = result.data["src/app.py"]
        assert 2 in uncovered

    def test_multi_file(self) -> None:
        result = parse_cobertura(MULTI_FILE_COBERTURA)
        assert "src/alpha.py" in result.data
        assert "src/beta.py" in result.data

    def test_multi_class_same_file_merged(self) -> None:
        result = parse_cobertura(MULTI_CLASS_SAME_FILE)
        covered, uncovered = result.data["src/app.py"]
        assert 1 in covered
        assert 4 in covered
        assert 2 in uncovered
        assert 3 in uncovered

    def test_covered_supersedes_uncovered_across_classes(self) -> None:
        # Line 2 is uncovered in class A, covered in class B — should be covered.
        xml = textwrap.dedent("""\
            <?xml version="1.0" ?>
            <coverage>
              <packages><package><classes>
                <class filename="src/x.py">
                  <lines><line number="2" hits="0"/></lines>
                </class>
                <class filename="src/x.py">
                  <lines><line number="2" hits="3"/></lines>
                </class>
              </classes></package></packages>
            </coverage>
        """)
        result = parse_cobertura(xml)
        covered, uncovered = result.data["src/x.py"]
        assert 2 in covered
        assert 2 not in uncovered

    def test_accepts_bytes_input(self) -> None:
        result = parse_cobertura(MINIMAL_COBERTURA.encode("utf-8"))
        assert "src/app.py" in result.data

    def test_path_normalized(self) -> None:
        xml = textwrap.dedent("""\
            <?xml version="1.0" ?>
            <coverage>
              <packages><package><classes>
                <class filename="./src/app.py">
                  <lines><line number="1" hits="1"/></lines>
                </class>
              </classes></package></packages>
            </coverage>
        """)
        result = parse_cobertura(xml)
        assert "src/app.py" in result.data

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_cobertura("")

    def test_wrong_root_element_raises(self) -> None:
        xml = "<report><packages/></report>"
        with pytest.raises(ValueError, match="coverage"):
            parse_cobertura(xml)

    def test_missing_filename_attr_skipped(self) -> None:
        xml = textwrap.dedent("""\
            <?xml version="1.0" ?>
            <coverage>
              <packages><package><classes>
                <class>
                  <lines><line number="1" hits="1"/></lines>
                </class>
                <class filename="src/ok.py">
                  <lines><line number="5" hits="1"/></lines>
                </class>
              </classes></package></packages>
            </coverage>
        """)
        result = parse_cobertura(xml)
        assert "src/ok.py" in result.data

    def test_no_class_elements_raises(self) -> None:
        xml = '<?xml version="1.0" ?><coverage><packages/></coverage>'
        with pytest.raises(ValueError, match="no <class>"):
            parse_cobertura(xml)

    def test_oversized_input_raises(self) -> None:
        oversized = b"x" * (MAX_ARTIFACT_BYTES + 1)
        with pytest.raises(ValueError, match="too large"):
            parse_cobertura(oversized)

    def test_malformed_xml_raises(self) -> None:
        with pytest.raises(ValueError, match="could not be parsed"):
            parse_cobertura("this is not xml <<<<")

    def test_doctype_rejected(self) -> None:
        evil = textwrap.dedent("""\
            <?xml version="1.0"?>
            <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
            <coverage><packages/></coverage>
        """)
        with pytest.raises((ValueError, Exception)):
            parse_cobertura(evil)

    def test_bad_line_number_skipped_with_warning(self) -> None:
        xml = textwrap.dedent("""\
            <?xml version="1.0" ?>
            <coverage>
              <packages><package><classes>
                <class filename="src/x.py">
                  <lines>
                    <line number="notanint" hits="1"/>
                    <line number="5" hits="1"/>
                  </lines>
                </class>
              </classes></package></packages>
            </coverage>
        """)
        result = parse_cobertura(xml)
        assert len(result.warnings) >= 1
        covered, _ = result.data["src/x.py"]
        assert 5 in covered

    def test_returns_frozensets(self) -> None:
        result = parse_cobertura(MINIMAL_COBERTURA)
        covered, uncovered = result.data["src/app.py"]
        assert isinstance(covered, frozenset)
        assert isinstance(uncovered, frozenset)

    def test_nested_coverage_root_accepted(self) -> None:
        """Parser accepts <coverage> nested one level inside another element."""
        xml = textwrap.dedent("""\
            <?xml version="1.0" ?>
            <report>
              <coverage>
                <packages><package><classes>
                  <class filename="src/x.py">
                    <lines><line number="1" hits="1"/></lines>
                  </class>
                </classes></package></packages>
              </coverage>
            </report>
        """)
        result = parse_cobertura(xml)
        assert "src/x.py" in result.data
