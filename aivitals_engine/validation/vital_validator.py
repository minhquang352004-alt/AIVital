from collections.abc import Iterable, Sequence

from aivitals_engine.config.vitals_config import ValidationConfig
from aivitals_engine.contracts.result import IssueSeverity, ResultStatus, ValidationIssue
from aivitals_engine.validation.candidate import ValidationContext, ValidationOutcome, VitalCandidate
from aivitals_engine.validation.rules import ValidationRule, build_default_rules


def resolve_status(issues: Iterable[ValidationIssue]) -> ResultStatus:
    severities = {issue.severity for issue in issues}
    if IssueSeverity.ERROR in severities:
        return ResultStatus.INVALID
    if IssueSeverity.WARNING in severities:
        return ResultStatus.BAD
    return ResultStatus.OK


class VitalValidator:
    def __init__(self, config: ValidationConfig | None = None, rules: Sequence[ValidationRule] | None = None) -> None:
        self._config = config or ValidationConfig()
        self._rules = tuple(rules) if rules is not None else build_default_rules(self._config)

    @property
    def rules(self) -> tuple[ValidationRule, ...]:
        return self._rules

    def validate(self, candidate: VitalCandidate, context: ValidationContext | None = None) -> ValidationOutcome:
        context = context or ValidationContext()
        issues = tuple(issue for rule in self._rules for issue in rule.evaluate(candidate, context))
        return ValidationOutcome(status=resolve_status(issues), issues=issues)
