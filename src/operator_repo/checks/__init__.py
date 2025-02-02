import importlib
import logging
from collections.abc import Callable, Iterable
from inspect import getmembers, isfunction
from typing import Any, Optional, Union

from .. import Bundle, Operator, Repo

log = logging.getLogger(__name__)


class CheckResult:
    """
    Generic result from a static check
    """

    severity: int = 0
    kind: str = "unknown"
    check: Optional[str]
    origin: Optional[Union[Repo, Operator, Bundle]]
    reason: str

    def __init__(
        self,
        reason: str,
        check: Optional[str] = None,
        origin: Optional[Union[Repo, Operator, Bundle]] = None,
    ):
        self.origin = origin
        self.check = check
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.kind}: {self.check}({self.origin}): {self.reason}"

    def __repr__(self) -> str:
        return f"{self.kind}({self.check}, {self.origin}, {self.reason})"

    def __int__(self) -> int:
        return self.severity

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (self.kind, self.reason, self.check, self.origin) == (
            other.kind,
            other.reason,
            other.check,
            other.origin,
        )

    def __ne__(self, other: Any) -> bool:
        return not self == other

    def __lt__(self, other: Any) -> bool:
        return int(self) < int(other)

    def __hash__(self) -> int:
        return hash((self.kind, self.reason, self.check, self.origin))


class Warn(CheckResult):
    """
    A non-fatal problem
    """

    # pylint: disable=too-few-public-methods
    severity = 40
    kind = "warning"


class Fail(CheckResult):
    """
    A critical problem
    """

    # pylint: disable=too-few-public-methods
    severity = 90
    kind = "failure"


SUPPORTED_TYPES = [("operator", Operator), ("bundle", Bundle)]
Check = Callable[[Union[Repo, Operator, Bundle]], Iterable[CheckResult]]


def get_checks(
    suite_name: str = "operator_repo.checks",
) -> dict[str, list[Check]]:
    """
    Return all the discovered checks in the given suite, grouped by resource type
    """
    result: dict[str, list[Check]] = {}
    for module_name, _ in SUPPORTED_TYPES:
        result[module_name] = []
        try:
            module = importlib.import_module(f"{suite_name}.{module_name}")
            for check_name, check in getmembers(module, isfunction):
                if check_name.startswith("check_"):
                    log.debug(
                        "Detected %s check with name %s in %s",
                        module_name,
                        check_name,
                        suite_name,
                    )
                    result[module_name].append(check)
        except ModuleNotFoundError:
            pass
    return result


def run_check(
    check: Check, target: Union[Repo, Operator, Bundle]
) -> Iterable[CheckResult]:
    """
    Run a check against a resource yielding all the problems found
    """
    log.debug("Running %s check on %s", check.__name__, target)
    for result in check(target):
        result.check = check.__name__
        result.origin = target
        yield result


def run_suite(
    targets: Iterable[Union[Repo, Operator, Bundle]],
    suite_name: str = "operator_repo.checks",
) -> Iterable[CheckResult]:
    """
    Run all the checks in a suite against a collection of resources
    """
    checks = get_checks(suite_name)
    for target in targets:
        for target_type_name, target_type in SUPPORTED_TYPES:
            if isinstance(target, target_type):
                for check in checks.get(target_type_name, []):
                    yield from run_check(check, target)
