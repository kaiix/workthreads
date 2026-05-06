from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    RUNTIME = 1
    USAGE = 2
    SAFETY = 3


@dataclass
class WTError(Exception):
    message: str
    exit_code: int = ExitCode.RUNTIME
    hint: str | None = None
    details: str | None = None

    def __str__(self) -> str:
        return self.message


class UsageError(WTError):
    def __init__(self, message: str, hint: str | None = None, details: str | None = None):
        super().__init__(message=message, exit_code=ExitCode.USAGE, hint=hint, details=details)


class SafetyError(WTError):
    def __init__(self, message: str, hint: str | None = None, details: str | None = None):
        super().__init__(message=message, exit_code=ExitCode.SAFETY, hint=hint, details=details)
