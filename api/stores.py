"""Storage interfaces for asynchronous jobs, with in-memory and AWS implementations.

    JobRepository   job records        memory | DynamoDB
    ResultStore     result documents   memory | S3
    JobQueue        work messages      memory (SQS semantics) | SQS

Business logic (api/service.py, api/worker.py) talks only to these interfaces; boto3 appears in this file alone.
The in-memory queue reproduces the SQS behaviour the worker relies on: a visibility window after receive, a receive
count, visibility changes, receipt-handle deletes, and moving a message to a dead-letter queue once it has been
received more than max_receive times.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from api.jobmodel import Job, JobStatus


class ConflictError(Exception):
    """A conditional write lost (another writer changed the job first)."""


@dataclass
class Message:
    body: dict
    receipt: str
    receive_count: int
    raw: str = ""


class JobRepository(Protocol):
    def create(self, job: Job) -> None: ...
    def get(self, job_id: str) -> Job | None: ...
    def update(self, job_id: str, changes: dict, expect_status: set[str] | None = None) -> Job: ...


class ResultStore(Protocol):
    def exists(self, key: str) -> bool: ...
    def put(self, key: str, doc: dict) -> None: ...
    def get(self, key: str) -> dict | None: ...


class JobQueue(Protocol):
    def send(self, body: dict) -> str: ...
    def receive(self, wait_seconds: int = 20, visibility: int | None = None) -> Message | None: ...
    def delete(self, receipt: str) -> None: ...
    def change_visibility(self, receipt: str, seconds: int) -> None: ...


# ---------------------------------------------------------------------------------------------------- memory

class MemoryJobRepository:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, job: Job) -> None:
        with self._lock:
            if job.job_id in self._jobs:
                raise ConflictError(job.job_id)
            self._jobs[job.job_id] = job.to_dict()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            d = self._jobs.get(job_id)
            return Job.from_dict(dict(d)) if d else None

    def update(self, job_id: str, changes: dict, expect_status: set[str] | None = None) -> Job:
        with self._lock:
            d = self._jobs.get(job_id)
            if d is None:
                raise KeyError(job_id)
            if expect_status is not None and d["status"] not in expect_status:
                raise ConflictError(f"{job_id} is {d['status']}")
            d.update(changes)
            return Job.from_dict(dict(d))


class MemoryResultStore:
    def __init__(self):
        self._docs: dict[str, str] = {}

    def exists(self, key: str) -> bool:
        return key in self._docs

    def put(self, key: str, doc: dict) -> None:
        self._docs[key] = json.dumps(doc, default=str)

    def get(self, key: str) -> dict | None:
        raw = self._docs.get(key)
        return json.loads(raw) if raw is not None else None


class MemoryQueue:
    """SQS-like queue. `clock` is injectable so tests can move time forward."""

    def __init__(self, visibility: int = 300, max_receive: int = 3, clock=time.monotonic):
        self.visibility, self.max_receive, self.clock = visibility, max_receive, clock
        self._msgs: list[dict] = []
        self.dlq: list[dict] = []
        self._lock = threading.Lock()

    def send(self, body: dict) -> str:
        return self.send_raw(json.dumps(body))

    def send_raw(self, raw: str) -> str:
        mid = uuid.uuid4().hex
        with self._lock:
            self._msgs.append({"id": mid, "raw": raw, "count": 0, "visible_at": 0.0, "receipt": None})
        return mid

    def receive(self, wait_seconds: int = 0, visibility: int | None = None) -> Message | None:
        now = self.clock()
        with self._lock:
            for m in list(self._msgs):
                if m["visible_at"] > now:
                    continue
                if m["count"] >= self.max_receive:      # redrive: received max_receive times already
                    self._msgs.remove(m)
                    self.dlq.append(m)
                    continue
                m["count"] += 1
                m["receipt"] = uuid.uuid4().hex
                m["visible_at"] = now + (visibility if visibility is not None else self.visibility)
                try:
                    body = json.loads(m["raw"])
                except ValueError:
                    body = {}
                return Message(body=body if isinstance(body, dict) else {}, receipt=m["receipt"],
                               receive_count=m["count"], raw=m["raw"])
        if wait_seconds:
            time.sleep(min(wait_seconds, 0.2))   # a short pause instead of SQS long polling, so loops don't spin
        return None

    def _find(self, receipt: str) -> dict:
        for m in self._msgs:
            if m["receipt"] == receipt:
                return m
        raise KeyError("receipt handle is no longer valid")

    def delete(self, receipt: str) -> None:
        with self._lock:
            self._msgs.remove(self._find(receipt))

    def change_visibility(self, receipt: str, seconds: int) -> None:
        with self._lock:
            self._find(receipt)["visible_at"] = self.clock() + seconds

    def depth(self) -> int:
        return len(self._msgs)


# ---------------------------------------------------------------------------------------------------- AWS

def _to_dynamo(v):
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, dict):
        return {k: _to_dynamo(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_to_dynamo(x) for x in v]
    return v


def _from_dynamo(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: _from_dynamo(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_from_dynamo(x) for x in v]
    return v


class DynamoJobRepository:
    def __init__(self, table_name: str, client=None):
        import boto3

        self.table = (client or boto3.resource("dynamodb")).Table(table_name)

    def create(self, job: Job) -> None:
        from botocore.exceptions import ClientError

        try:
            self.table.put_item(Item=_to_dynamo({k: v for k, v in job.to_dict().items() if v is not None}),
                                ConditionExpression="attribute_not_exists(job_id)")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConflictError(job.job_id) from e
            raise

    def get(self, job_id: str) -> Job | None:
        item = self.table.get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item")
        return Job.from_dict(_from_dynamo(item)) if item else None

    def update(self, job_id: str, changes: dict, expect_status: set[str] | None = None) -> Job:
        from botocore.exceptions import ClientError

        names, values, sets, removes = {}, {}, [], []
        for i, (k, v) in enumerate(changes.items()):
            names[f"#f{i}"] = k
            if v is None:
                removes.append(f"#f{i}")
            else:
                values[f":v{i}"] = _to_dynamo(v)
                sets.append(f"#f{i} = :v{i}")
        expr = ("SET " + ", ".join(sets) if sets else "") + (" REMOVE " + ", ".join(removes) if removes else "")
        cond = "attribute_exists(job_id)"
        if expect_status:
            names["#st"] = "status"
            keys = []
            for j, s in enumerate(sorted(expect_status)):
                values[f":s{j}"] = s
                keys.append(f":s{j}")
            cond += f" AND #st IN ({', '.join(keys)})"
        try:
            out = self.table.update_item(Key={"job_id": job_id}, UpdateExpression=expr.strip(),
                                         ConditionExpression=cond, ExpressionAttributeNames=names,
                                         ExpressionAttributeValues=values or None, ReturnValues="ALL_NEW") \
                if values else \
                self.table.update_item(Key={"job_id": job_id}, UpdateExpression=expr.strip(),
                                       ConditionExpression=cond, ExpressionAttributeNames=names,
                                       ReturnValues="ALL_NEW")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConflictError(job_id) from e
            raise
        return Job.from_dict(_from_dynamo(out["Attributes"]))


class S3ResultStore:
    def __init__(self, bucket: str, client=None):
        import boto3

        self.bucket, self.s3 = bucket, client or boto3.client("s3")

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def put(self, key: str, doc: dict) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json.dumps(doc, default=str).encode(),
                           ContentType="application/json")

    def get(self, key: str) -> dict | None:
        from botocore.exceptions import ClientError

        try:
            return json.loads(self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read())
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise


class SqsJobQueue:
    def __init__(self, queue_url: str, client=None):
        import boto3

        self.url, self.sqs = queue_url, client or boto3.client("sqs")

    def send(self, body: dict) -> str:
        return self.sqs.send_message(QueueUrl=self.url, MessageBody=json.dumps(body))["MessageId"]

    def receive(self, wait_seconds: int = 20, visibility: int | None = None) -> Message | None:
        kw = {"QueueUrl": self.url, "MaxNumberOfMessages": 1, "WaitTimeSeconds": wait_seconds,
              "MessageSystemAttributeNames": ["ApproximateReceiveCount"]}
        if visibility is not None:
            kw["VisibilityTimeout"] = visibility
        msgs = self.sqs.receive_message(**kw).get("Messages") or []
        if not msgs:
            return None
        m = msgs[0]
        try:
            body = json.loads(m["Body"])
        except ValueError:
            body = {}
        return Message(body=body if isinstance(body, dict) else {}, receipt=m["ReceiptHandle"],
                       receive_count=int(m.get("Attributes", {}).get("ApproximateReceiveCount", "1")), raw=m["Body"])

    def delete(self, receipt: str) -> None:
        self.sqs.delete_message(QueueUrl=self.url, ReceiptHandle=receipt)

    def change_visibility(self, receipt: str, seconds: int) -> None:
        self.sqs.change_message_visibility(QueueUrl=self.url, ReceiptHandle=receipt, VisibilityTimeout=seconds)


# ---------------------------------------------------------------------------------------------------- wiring

@dataclass
class Backends:
    jobs: JobRepository
    results: ResultStore
    light_queue: JobQueue


def from_environment() -> Backends:
    """GTC_BACKEND=memory (default, local) or aws (DynamoDB + S3 + SQS from GTC_JOBS_TABLE / GTC_RESULTS_BUCKET /
    GTC_LIGHT_QUEUE_URL)."""
    import os

    if os.environ.get("GTC_BACKEND", "memory") == "aws":
        return Backends(DynamoJobRepository(os.environ["GTC_JOBS_TABLE"]),
                        S3ResultStore(os.environ["GTC_RESULTS_BUCKET"]),
                        SqsJobQueue(os.environ["GTC_LIGHT_QUEUE_URL"]))
    return Backends(MemoryJobRepository(), MemoryResultStore(), MemoryQueue())


TERMINAL = {JobStatus.SUCCEEDED.value, JobStatus.FAILED.value}
