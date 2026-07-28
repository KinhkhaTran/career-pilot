"""Visible, approval-bound assisted application worker.

Public surface:

* Legacy Greenhouse-style stop-before-submit worker (``AssistedApplicationWorker``).
* Supervised Workday runner with a token-gated single submit
  (``SupervisedApplicationRunner``) and its supporting adapter/classifier/approval
  modules.
"""

from .adapters import GenericMockATSAdapter, GreenhouseLikeAdapter
from .approval import (
    ApprovalBinding,
    ApprovalError,
    InMemoryTokenStore,
    TokenStore,
    issue_token,
    verify_and_consume,
)
from .classifier import PageSignals, classify_ats
from .fields import FieldCategory, FieldValue
from .pause import PauseReason, PauseSignal
from .runner import (
    BrowserRunRejected as SupervisedRunRejected,
)
from .runner import (
    InMemorySubmissionGuard,
    RunContext,
    RunnerConfig,
    SubmissionGuard,
    SupervisedApplicationRunner,
    SupervisedRunResult,
)
from .workday import WorkdayAdapter, WorkdayStep
from .worker import AssistedApplicationWorker, BrowserRunResult

__all__ = [
    # legacy stop-before-submit worker
    "AssistedApplicationWorker",
    "BrowserRunResult",
    "GenericMockATSAdapter",
    "GreenhouseLikeAdapter",
    # supervised Workday runner
    "SupervisedApplicationRunner",
    "SupervisedRunResult",
    "SupervisedRunRejected",
    "RunContext",
    "RunnerConfig",
    "SubmissionGuard",
    "InMemorySubmissionGuard",
    "WorkdayAdapter",
    "WorkdayStep",
    # classification + approval
    "PageSignals",
    "classify_ats",
    "ApprovalBinding",
    "ApprovalError",
    "InMemoryTokenStore",
    "TokenStore",
    "issue_token",
    "verify_and_consume",
    "FieldCategory",
    "FieldValue",
    "PauseReason",
    "PauseSignal",
]
