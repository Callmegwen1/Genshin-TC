"""AWS adapters checked offline with botocore's Stubber: each call is validated against the real AWS API model
(parameter names and types), without network or credentials."""
from __future__ import annotations

import pytest

boto3 = pytest.importorskip("boto3")
from botocore.stub import ANY, Stubber  # noqa: E402

from api.jobmodel import Job  # noqa: E402
from api.stores import ConflictError, DynamoJobRepository, S3ResultStore, SqsJobQueue  # noqa: E402

REGION = {"region_name": "us-east-2", "aws_access_key_id": "x", "aws_secret_access_key": "x"}


def _job():
    return Job(job_id="j1", job_type="TEAM_EVALUATION", status="QUEUED", created_at="t", engine_version="fm",
               app_commit="c", input_hash="h", input={"lineup": ["A", "B", "C", "D"]}, result_location="results/fm/x.json",
               duration_s=1.5)


def test_dynamo_create_is_conditional_and_converts_floats():
    res = boto3.resource("dynamodb", **REGION)
    repo = DynamoJobRepository("gtc-jobs", client=res)
    with Stubber(res.meta.client) as st:
        st.add_response("put_item", {}, {"TableName": "gtc-jobs", "Item": ANY,
                                         "ConditionExpression": "attribute_not_exists(job_id)"})
        repo.create(_job())
        st.add_client_error("put_item", "ConditionalCheckFailedException")
        with pytest.raises(ConflictError):
            repo.create(_job())


def test_dynamo_update_with_status_condition_and_remove():
    res = boto3.resource("dynamodb", **REGION)
    repo = DynamoJobRepository("gtc-jobs", client=res)
    with Stubber(res.meta.client) as st:
        st.add_response("update_item", {"Attributes": {"job_id": {"S": "j1"}, "job_type": {"S": "TEAM_EVALUATION"},
                                                       "status": {"S": "RUNNING"}, "created_at": {"S": "t"},
                                                       "engine_version": {"S": "fm"}, "app_commit": {"S": "c"},
                                                       "input_hash": {"S": "h"}, "input": {"M": {}},
                                                       "result_location": {"S": "k"},
                                                       "attempt_count": {"N": "2"}}},
                        {"TableName": "gtc-jobs", "Key": {"job_id": "j1"},
                         "UpdateExpression": "SET #f0 = :v0, #f1 = :v1 REMOVE #f2",
                         "ConditionExpression": "attribute_exists(job_id) AND #st IN (:s0, :s1)",
                         "ExpressionAttributeNames": {"#f0": "status", "#f1": "attempt_count", "#f2": "error",
                                                      "#st": "status"},
                         "ExpressionAttributeValues": {":v0": "RUNNING", ":v1": 2, ":s0": "QUEUED", ":s1": "RUNNING"},
                         "ReturnValues": "ALL_NEW"})
        job = repo.update("j1", {"status": "RUNNING", "attempt_count": 2, "error": None},
                          expect_status={"QUEUED", "RUNNING"})
        assert job.status == "RUNNING" and job.attempt_count == 2


def test_s3_exists_treats_404_as_missing():
    s3 = boto3.client("s3", **REGION)
    store = S3ResultStore("gtc-results", client=s3)
    with Stubber(s3) as st:
        st.add_client_error("head_object", "404", http_status_code=404)
        assert store.exists("results/fm/x.json") is False
        st.add_response("head_object", {}, {"Bucket": "gtc-results", "Key": "results/fm/x.json"})
        assert store.exists("results/fm/x.json") is True


def test_sqs_receive_reads_receive_count():
    sqs = boto3.client("sqs", **REGION)
    q = SqsJobQueue("https://sqs.us-east-2.amazonaws.com/123456789012/gtc-light-queue", client=sqs)
    with Stubber(sqs) as st:
        st.add_response("receive_message",
                        {"Messages": [{"MessageId": "m", "ReceiptHandle": "r1", "Body": '{"job_id": "j1"}',
                                       "Attributes": {"ApproximateReceiveCount": "2"}}]},
                        {"QueueUrl": q.url, "MaxNumberOfMessages": 1, "WaitTimeSeconds": 20,
                         "MessageSystemAttributeNames": ["ApproximateReceiveCount"], "VisibilityTimeout": 300})
        m = q.receive(visibility=300)
        assert m.body == {"job_id": "j1"} and m.receipt == "r1" and m.receive_count == 2
        st.add_response("change_message_visibility", {}, {"QueueUrl": q.url, "ReceiptHandle": "r1",
                                                          "VisibilityTimeout": 300})
        q.change_visibility("r1", 300)
