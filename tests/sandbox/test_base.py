from __future__ import annotations

from falsegreen.sandbox.base import ExecResult


def test_stdout_tail_truncated_to_4096_bytes() -> None:
    long_output = "x" * 5000
    result = ExecResult(exit_code=0, stdout_tail=long_output, duration_ms=10, was_fork=True)
    assert len(result.stdout_tail.encode("utf-8")) <= 4096
    assert result.stdout_tail == long_output[-4096:]


def test_stdout_tail_under_limit_is_unchanged() -> None:
    output = "short output"
    result = ExecResult(exit_code=0, stdout_tail=output, duration_ms=10, was_fork=True)
    assert result.stdout_tail == output


def test_stdout_tail_truncates_by_bytes_not_chars_for_multibyte_text() -> None:
    long_output = "é" * 5000  # 2 bytes each in utf-8
    result = ExecResult(exit_code=0, stdout_tail=long_output, duration_ms=10, was_fork=True)
    assert len(result.stdout_tail.encode("utf-8")) <= 4096
