"""Queue worker: `python -m api.worker` (same image as the API, different command).

For each SQS message {job_id, job_type, v}:
    load job -> already SUCCEEDED/FAILED? delete the message (redelivery is harmless)
             -> result already stored?   mark SUCCEEDED (cache hit), delete
             -> mark RUNNING (attempt = SQS receive count), heartbeat keeps the message invisible
             -> run the engine through api/engine_adapter (same call as the synchronous route)
             -> store result, mark SUCCEEDED, delete
    on error -> record error + attempt; before the last attempt: back to QUEUED, short visibility so SQS redelivers;
                on the last attempt: FAILED, visibility 0, and SQS moves the message to the DLQ on its next receive
    poison   -> unreadable message or unknown job: left alone, so SQS moves it to the DLQ after max_receive receives

Heartbeat: every HEARTBEAT seconds the worker extends the message's visibility by VISIBILITY seconds. If an extension
fails (the receipt is no longer valid), the lease is marked lost: the result is still written (identical bytes, same
key, so a concurrent redelivery is harmless) but the worker does not try to delete the message with a stale receipt.
SQS limits a message's total invisibility to 12 hours after it was received; the heartbeat stops extending past
LEASE_LIMIT (11.5 h) and logs it, which bounds the longest job this design supports.
"""
from __future__ import annotations

import os
import signal
import threading
import time

from api import identity
from api.engine_adapter import UnsupportedCharacter, run_team
from api.jobmodel import ENABLED_TYPES, JobStatus, JobType, utc_now
from api.logs import event, get_logger
from api.stores import Backends, ConflictError, Message, from_environment

log = get_logger("gtc.worker")

VISIBILITY = int(os.environ.get("GTC_VISIBILITY_SECONDS", "300"))
HEARTBEAT = int(os.environ.get("GTC_HEARTBEAT_SECONDS", "60"))
MAX_RECEIVE = int(os.environ.get("GTC_MAX_RECEIVE", "3"))
RETRY_DELAY = int(os.environ.get("GTC_RETRY_DELAY_SECONDS", "30"))
LEASE_LIMIT = 11.5 * 3600     # SQS: at most 12 h of invisibility after a receive


class Heartbeat:
    def __init__(self, queue, receipt: str, received_at: float, job_id: str, every: int = HEARTBEAT,
                 visibility: int = VISIBILITY, clock=time.monotonic):
        self.queue, self.receipt, self.received_at, self.job_id = queue, receipt, received_at, job_id
        self.every, self.visibility, self.clock = every, visibility, clock
        self.lost = False
        self.extensions = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t.start()
        return self

    def beat(self) -> bool:
        """One extension. Returns False once the lease is lost or the 12 h limit is near."""
        if self.clock() - self.received_at + self.visibility > LEASE_LIMIT:
            event(log, "lease_limit_reached", job_id=self.job_id)
            return False
        try:
            self.queue.change_visibility(self.receipt, self.visibility)
            self.extensions += 1
            return True
        except Exception as e:  # noqa: BLE001
            self.lost = True
            event(log, "lease_lost", job_id=self.job_id, error=type(e).__name__)
            return False

    def _run(self):
        while not self._stop.wait(self.every):
            if not self.beat():
                return

    def stop(self):
        self._stop.set()


class Worker:
    def __init__(self, backends: Backends, runner=run_team, max_receive: int = MAX_RECEIVE,
                 heartbeat_every: int = HEARTBEAT, visibility: int = VISIBILITY):
        self.b, self.runner, self.max_receive = backends, runner, max_receive
        self.heartbeat_every, self.visibility = heartbeat_every, visibility
        self.stopping = False

    # ------------------------------------------------------------------ one message
    def process(self, msg: Message) -> str:
        """Handle one message; returns the outcome (for logs and tests)."""
        job_id = msg.body.get("job_id") if isinstance(msg.body, dict) else None
        if not job_id:
            event(log, "poison_message", receive_count=msg.receive_count, body=msg.raw[:200])
            return "poison"
        job = self.b.jobs.get(job_id)
        if job is None:
            event(log, "poison_message", job_id=job_id, reason="unknown job", receive_count=msg.receive_count)
            return "poison"
        event(log, "job_received", job_id=job_id, job_type=job.job_type, receive_count=msg.receive_count,
              status=job.status)

        if job.status in (JobStatus.SUCCEEDED.value, JobStatus.FAILED.value):
            self._delete(msg, job_id)
            event(log, "duplicate_delivery", job_id=job_id, status=job.status)
            return "already_" + job.status.lower()

        if JobType(job.job_type) not in ENABLED_TYPES:
            self.b.jobs.update(job_id, {"status": JobStatus.FAILED.value, "completed_at": utc_now(),
                                        "error": {"type": "Disabled", "message": f"{job.job_type} is disabled"}})
            self._delete(msg, job_id)
            event(log, "job_failed", job_id=job_id, final=True, reason="disabled type")
            return "disabled"

        if self.b.results.exists(job.result_location):
            self.b.jobs.update(job_id, {"status": JobStatus.SUCCEEDED.value, "cache_hit": True,
                                        "completed_at": utc_now(), "status_message": "identical result reused"})
            self._delete(msg, job_id)
            event(log, "job_completed", job_id=job_id, cache_hit=True, seconds=0, engine_version=job.engine_version)
            return "reused"

        try:
            self.b.jobs.update(job_id, {"status": JobStatus.RUNNING.value, "attempt_count": msg.receive_count,
                                        "started_at": job.started_at or utc_now(), "status_message": "running"},
                               expect_status={JobStatus.QUEUED.value, JobStatus.RUNNING.value})
        except ConflictError:
            self._delete(msg, job_id)
            return "conflict"

        hb = Heartbeat(self.b.light_queue, msg.receipt, time.monotonic(), job_id, self.heartbeat_every,
                       self.visibility).start()
        t0 = time.perf_counter()
        event(log, "job_started", job_id=job_id, job_type=job.job_type, attempt=msg.receive_count,
              engine_version=job.engine_version)
        try:
            result = self.runner(self._compute_lineup(job))
            seconds = round(time.perf_counter() - t0, 1)
            result = {**result, "computed_seconds": seconds, "computed_by_job": job_id,
                      "engine_identity": identity.engine_identity()}
            self.b.results.put(job.result_location, result)
            self.b.jobs.update(job_id, {"status": JobStatus.SUCCEEDED.value, "completed_at": utc_now(),
                                        "duration_s": seconds, "status_message": "done", "error": None})
            if not hb.lost:
                self._delete(msg, job_id)
            event(log, "job_completed", job_id=job_id, job_type=job.job_type, seconds=seconds, dps=result.get("dps"),
                  attempt=msg.receive_count, engine_version=job.engine_version, cache_hit=False,
                  limit_hit=(result.get("search") or {}).get("limit_hit"), lease_lost=hb.lost)
            return "succeeded"
        except Exception as e:  # noqa: BLE001
            final = isinstance(e, UnsupportedCharacter) or msg.receive_count >= self.max_receive
            err = {"type": type(e).__name__, "message": str(e)[:300]}
            self.b.jobs.update(job_id, {"status": (JobStatus.FAILED if final else JobStatus.QUEUED).value,
                                        "error": err, "attempt_count": msg.receive_count,
                                        "completed_at": utc_now() if final else None,
                                        "status_message": "failed" if final else "retrying"})
            event(log, "job_failed", job_id=job_id, job_type=job.job_type, attempt=msg.receive_count, final=final,
                  error_type=err["type"], seconds=round(time.perf_counter() - t0, 1), exc_info=not final)
            if not hb.lost:
                try:   # final: visible now, so the next receive moves it to the DLQ; otherwise retry after a delay
                    self.b.light_queue.change_visibility(msg.receipt, 0 if final else RETRY_DELAY)
                except Exception:  # noqa: BLE001
                    pass
            return "failed_final" if final else "failed_retry"
        finally:
            hb.stop()

    @staticmethod
    def _compute_lineup(job) -> list[str]:
        return job.input["variant_lineup"] if job.job_type == JobType.TEAM_VARIANT.value else job.input["lineup"]

    def _delete(self, msg: Message, job_id: str) -> None:
        try:
            self.b.light_queue.delete(msg.receipt)
        except Exception as e:  # noqa: BLE001
            event(log, "delete_failed", job_id=job_id, error=type(e).__name__)

    # ------------------------------------------------------------------ loop
    def run_forever(self, wait_seconds: int = 20) -> None:
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self._on_sigterm)
        event(log, "worker_started", visibility=self.visibility, heartbeat=self.heartbeat_every,
              max_receive=self.max_receive, **identity.version_info())
        while not self.stopping:
            try:
                msg = self.b.light_queue.receive(wait_seconds=wait_seconds, visibility=self.visibility)
            except Exception:  # noqa: BLE001
                event(log, "receive_failed", exc_info=True)
                time.sleep(5)
                continue
            if msg is not None:
                self.process(msg)
        event(log, "worker_stopped")

    def _on_sigterm(self, *_):
        # ECS sends SIGTERM, then SIGKILL after stopTimeout: finish the current job if possible, take no new one
        self.stopping = True
        event(log, "sigterm_received")


def main() -> None:
    Worker(from_environment()).run_forever()


if __name__ == "__main__":
    main()
