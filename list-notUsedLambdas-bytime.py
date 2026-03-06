#!/usr/bin/env python3
import boto3
import botocore
from datetime import datetime, timedelta, timezone
import sys

LOOKBACK_DAYS = 180 # days

def safe_get_tags(lambda_client, arn: str) -> dict:
    try:
        resp = lambda_client.list_tags(Resource=arn)
        return resp.get("Tags", {}) or {}
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        return {"__tag_error__": code}

def get_all_functions(lambda_client):
    paginator = lambda_client.get_paginator("list_functions")
    for page in paginator.paginate():
        for fn in page.get("Functions", []):
            yield fn

def get_invocations_last_6_months(cw_client, function_name: str, start_time, end_time) -> int:
    """
    Returns total Invocations in the time window.
    If no datapoints exist, returns 0.
    """
    try:
        resp = cw_client.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Invocations",
            Dimensions=[{"Name": "FunctionName", "Value": function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,  # 1 day
            Statistics=["Sum"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0

        total = 0
        for dp in datapoints:
            total += int(dp.get("Sum", 0))
        return total
    except botocore.exceptions.ClientError as e:
        print(f"WARNING: Could not read CloudWatch metric for {function_name}: {e}", file=sys.stderr)
        return -1  # indicate metric read issue

def fmt_row(cols, widths):
    return " | ".join(str(c).ljust(w) for c, w in zip(cols, widths))

def main():
    session = boto3.Session()
    region = session.region_name
    if not region:
        print("ERROR: No AWS region configured. Set AWS_REGION or configure a default region.", file=sys.stderr)
        sys.exit(1)

    lambda_client = session.client("lambda")
    cw_client = session.client("cloudwatch")

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=LOOKBACK_DAYS)

    rows = []

    for fn in get_all_functions(lambda_client):
        name = fn.get("FunctionName", "")
        runtime = fn.get("Runtime", "")
        arn = fn.get("FunctionArn", "")

        invocations = get_invocations_last_6_months(cw_client, name, start_time, end_time)

        # only show functions with zero invocations in the last 6 months
        if invocations != 0:
            continue

        tags = safe_get_tags(lambda_client, arn)

        rows.append((name, runtime, invocations))

    rows.sort(key=lambda r: r[0].lower())

    headers = ("Name", "Runtime", "Last6MonthsInvocations")
    all_rows = [headers] + rows

    widths = [
        max(len(str(r[0])) for r in all_rows),
        max(len(str(r[1])) for r in all_rows),
        max(len(str(r[2])) for r in all_rows),
        max(len(str(r[3])) for r in all_rows),
    ]

    print(f"Region: {region}")
    print(f"Window: {start_time.isoformat()} -> {end_time.isoformat()}")
    print(fmt_row(headers, widths))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt_row(r, widths))

if __name__ == "__main__":
    main()
