"""A scanned repository is untrusted: it can not block a read or smuggle terminal escapes into a report."""

from __future__ import annotations

import os
from pathlib import Path

from prism_ai_lint import _runtime
from prism_ai_lint.report import Report, printable


def test_regular_file_is_read(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    assert _runtime.read_text(f) == "hello"


def test_symlink_to_a_device_is_not_read(tmp_path):
    link = tmp_path / "zero.yml"
    link.symlink_to("/dev/zero")
    assert _runtime.read_text(link) is None


def test_fifo_is_not_read(tmp_path):
    fifo = tmp_path / "pipe.yml"
    os.mkfifo(fifo)
    assert _runtime.read_text(fifo) is None


def test_oversized_file_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(_runtime, "MAX_READ_BYTES", 10)
    f = tmp_path / "big.txt"
    f.write_text("x" * 11, encoding="utf-8")
    assert _runtime.read_text(f) is None


def test_printable_replaces_escapes_and_keeps_text_layout():
    assert printable("a\x1b[31mred\x1b[0m\x07b") == "a?[31mred?[0m?b"
    assert printable("two\nlines\tand tab") == "two\nlines\tand tab"
    assert printable("accents é and 日本") == "accents é and 日本"


def test_report_add_neutralises_escapes_in_message_and_path():
    rep = Report()
    rep.add("warn", "X", Path("a\x1b]0;title\x07.yml"), "name \x1b[2J here")
    finding = rep.findings[0]
    assert "\x1b" not in finding.message and "\x1b" not in finding.path
    assert "\x07" not in finding.path
