from __future__ import annotations

import inspect

import pytest

from falsegreen import errors
from falsegreen.errors import FalseGreenError


def _all_error_classes() -> list[type[FalseGreenError]]:
    return [
        obj
        for _, obj in inspect.getmembers(errors, inspect.isclass)
        if issubclass(obj, FalseGreenError) and obj is not FalseGreenError
    ]


@pytest.mark.parametrize("error_cls", _all_error_classes(), ids=lambda c: c.__name__)
def test_error_has_nonempty_code(error_cls: type[FalseGreenError]) -> None:
    assert error_cls.code
    assert isinstance(error_cls.code, str)


@pytest.mark.parametrize("error_cls", _all_error_classes(), ids=lambda c: c.__name__)
def test_error_has_nonempty_remedy(error_cls: type[FalseGreenError]) -> None:
    assert error_cls.remedy
    assert isinstance(error_cls.remedy, str)


@pytest.mark.parametrize("error_cls", _all_error_classes(), ids=lambda c: c.__name__)
def test_error_has_exit_code(error_cls: type[FalseGreenError]) -> None:
    assert isinstance(error_cls.exit_code, int)


def test_all_codes_are_unique() -> None:
    codes = [cls.code for cls in _all_error_classes()]
    assert len(codes) == len(set(codes))


def test_guardrail_violation_exit_code_is_zero() -> None:
    assert errors.GuardrailViolation.exit_code == 0


def test_error_message_defaults_to_remedy() -> None:
    err = errors.MissingCredential()
    assert str(err) == errors.MissingCredential.remedy
