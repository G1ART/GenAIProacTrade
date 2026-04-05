"""Operational run logging: success / warning / failed / empty_valid (queryable, not only prints)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from db import records as dbrec


class OperationalRunSession:
    """Start run on enter; call finish_* before exit or exception -> failed."""

    def __init__(
        self,
        client: Any,
        *,
        run_type: str,
        component: str,
        metadata_json: Optional[dict[str, Any]] = None,
        linked_external_id: Optional[str] = None,
    ) -> None:
        self.client = client
        self.run_type = run_type
        self.component = component
        self.metadata_json = metadata_json or {}
        self.linked_external_id = linked_external_id
        self._op_id: Optional[str] = None
        self._t0 = time.monotonic_ns()
        self._finished = False

    def __enter__(self) -> OperationalRunSession:
        self._op_id = dbrec.insert_operational_run_started(
            self.client,
            run_type=self.run_type,
            component=self.component,
            metadata_json=self.metadata_json,
            linked_external_id=self.linked_external_id,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._op_id is None:
            return
        if self._finished:
            return
        if exc_type is not None:
            dbrec.finalize_operational_run(
                self.client,
                operational_run_id=self._op_id,
                status="failed",
                duration_ms=self._duration_ms(),
                rows_read=None,
                rows_written=None,
                warnings_count=0,
                error_class="execution_error",
                error_code=exc_type.__name__,
                error_message_summary=str(exc)[:2000] if exc else "",
                trace_json={"exception": True},
            )
            dbrec.insert_operational_failure(
                self.client,
                operational_run_id=self._op_id,
                failure_category="execution_error",
                detail=str(exc)[:4000] if exc else "",
            )
            self._finished = True
            return
        dbrec.finalize_operational_run(
            self.client,
            operational_run_id=self._op_id,
            status="failed",
            duration_ms=self._duration_ms(),
            rows_read=None,
            rows_written=None,
            warnings_count=0,
            error_class="abandoned",
            error_code="no_finish_called",
            error_message_summary="OperationalRunSession exited without finish_*",
            trace_json={},
        )
        dbrec.insert_operational_failure(
            self.client,
            operational_run_id=self._op_id,
            failure_category="execution_error",
            detail="context exited without finish_success/finish_failed/empty_valid/warning",
        )
        self._finished = True

    @property
    def operational_run_id(self) -> Optional[str]:
        return self._op_id

    def _duration_ms(self) -> int:
        return int((time.monotonic_ns() - self._t0) / 1_000_000)

    def finish_success(
        self,
        *,
        rows_read: Optional[int],
        rows_written: Optional[int],
        warnings_count: int = 0,
        trace_json: Optional[dict[str, Any]] = None,
    ) -> None:
        assert self._op_id
        st = "warning" if warnings_count > 0 else "success"
        dbrec.finalize_operational_run(
            self.client,
            operational_run_id=self._op_id,
            status=st,
            duration_ms=self._duration_ms(),
            rows_read=rows_read,
            rows_written=rows_written,
            warnings_count=warnings_count,
            error_class=None,
            error_code=None,
            error_message_summary=None,
            trace_json=trace_json or {},
        )
        self._finished = True

    def finish_empty_valid(
        self,
        *,
        rows_read: Optional[int],
        trace_json: Optional[dict[str, Any]] = None,
    ) -> None:
        assert self._op_id
        dbrec.finalize_operational_run(
            self.client,
            operational_run_id=self._op_id,
            status="empty_valid",
            duration_ms=self._duration_ms(),
            rows_read=rows_read,
            rows_written=0,
            warnings_count=0,
            error_class=None,
            error_code=None,
            error_message_summary="zero_output_intentional_low_noise_or_no_matches",
            trace_json=trace_json or {},
        )
        self._finished = True

    def finish_warning(
        self,
        *,
        rows_read: Optional[int],
        rows_written: Optional[int],
        message: str,
        trace_json: Optional[dict[str, Any]] = None,
    ) -> None:
        assert self._op_id
        dbrec.finalize_operational_run(
            self.client,
            operational_run_id=self._op_id,
            status="warning",
            duration_ms=self._duration_ms(),
            rows_read=rows_read,
            rows_written=rows_written,
            warnings_count=1,
            error_class="heuristic_low_confidence",
            error_code="partial_errors",
            error_message_summary=message[:2000],
            trace_json=trace_json or {},
        )
        self._finished = True

    def finish_failed(
        self,
        *,
        error_class: str,
        error_code: str,
        message: str,
        failure_category: str = "execution_error",
    ) -> None:
        assert self._op_id
        dbrec.finalize_operational_run(
            self.client,
            operational_run_id=self._op_id,
            status="failed",
            duration_ms=self._duration_ms(),
            rows_read=None,
            rows_written=None,
            warnings_count=0,
            error_class=error_class,
            error_code=error_code,
            error_message_summary=message[:2000],
            trace_json={},
        )
        dbrec.insert_operational_failure(
            self.client,
            operational_run_id=self._op_id,
            failure_category=failure_category,
            detail=message[:4000],
        )
        self._finished = True
