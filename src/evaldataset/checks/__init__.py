"""Quality checkers for CPT datasets."""

from evaldataset.checks.registry import get_all_checkers, get_checker, register

# Import checker modules to trigger registration
import evaldataset.checks.structural  # noqa: F401
import evaldataset.checks.text_quality  # noqa: F401
import evaldataset.checks.duplicates  # noqa: F401
# import evaldataset.checks.content  # noqa: F401  # TODO: P4で実装予定

__all__ = ["get_all_checkers", "get_checker", "register"]
