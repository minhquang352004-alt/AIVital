import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

MEASUREMENT_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(bpm|brpm|mmhg|ms\b|mili\s*giây|nhịp\s*thở\s*/\s*phút|nhịp\s*/\s*phút|lần\s*/\s*phút)",
    re.IGNORECASE,
)
DIAGNOSTIC_PHRASES = (
    "chẩn đoán",
    "bạn bị",
    "bạn mắc",
    "mắc bệnh",
    "bị bệnh",
    "rối loạn nhịp",
    "suy tim",
    "bệnh tim",
    "tăng huyết áp",
    "diagnos",
    "you have",
)
NEGATION_WORDS = ("không", "chưa", "not ", "no ")
NEGATION_LOOKBACK_CHARS = 30
NUMBER_TOLERANCE = 0.051


class GuardViolation(StrEnum):
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    UNVERIFIED_NUMBER = "UNVERIFIED_NUMBER"
    DIAGNOSTIC_CLAIM = "DIAGNOSTIC_CLAIM"


@dataclass(frozen=True)
class GuardResult:
    passed: bool
    violations: tuple[GuardViolation, ...]
    evidence: tuple[str, ...]


def parse_number(text: str) -> float:
    return float(text.replace(",", "."))


class OutputGuard:
    def check(self, text: str, allowed_numbers: Sequence[float]) -> GuardResult:
        if not text or not text.strip():
            return GuardResult(False, (GuardViolation.EMPTY_OUTPUT,), ())
        unverified = self._unverified_numbers(text, allowed_numbers)
        claims = self._diagnostic_claims(text)
        violations = []
        if unverified:
            violations.append(GuardViolation.UNVERIFIED_NUMBER)
        if claims:
            violations.append(GuardViolation.DIAGNOSTIC_CLAIM)
        return GuardResult(not violations, tuple(violations), tuple(unverified + claims))

    @staticmethod
    def _unverified_numbers(text: str, allowed_numbers: Sequence[float]) -> list[str]:
        unverified = []
        for match in MEASUREMENT_PATTERN.finditer(text):
            value = parse_number(match.group(1))
            if not any(abs(value - allowed) <= NUMBER_TOLERANCE for allowed in allowed_numbers):
                unverified.append(match.group(0))
        return unverified

    @staticmethod
    def _diagnostic_claims(text: str) -> list[str]:
        lowered = text.lower()
        claims = []
        for phrase in DIAGNOSTIC_PHRASES:
            for match in re.finditer(re.escape(phrase), lowered):
                context = lowered[max(0, match.start() - NEGATION_LOOKBACK_CHARS) : match.start()]
                if not any(word in context for word in NEGATION_WORDS):
                    claims.append(phrase)
        return claims
