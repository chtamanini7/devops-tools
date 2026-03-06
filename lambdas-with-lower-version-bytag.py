#!/usr/bin/env python3
import boto3
import botocore
import sys

PYTHON_RUNTIMES_LEQ_39 = {"python3.6", "python3.7", "python3.8", "python3.9"}

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

def fmt_row(cols, widths):
    return " | ".join(str(c).ljust(w) for c, w in zip(cols, widths))

def main():
    session = boto3.Session()
    region = session.region_name
    if not region:
        print("ERROR: No AWS region configured. In CloudShell, set AWS_REGION or configure default region.", file=sys.stderr)
        sys.exit(1)

    lambda_client = session.client("lambda")

    rows = []
    for fn in get_all_functions(lambda_client):
        name = fn.get("FunctionName", "")
        runtime = fn.get("Runtime", "")  # e.g. python3.9
        arn = fn.get("FunctionArn", "")

        if runtime not in PYTHON_RUNTIMES_LEQ_39:
            continue

        tags = safe_get_tags(lambda_client, arn)
        team = tags.get("Team", "")                  # change with value required

        # If tag read failed, show the error code in Team column so it’s obvious
        if "__tag_error__" in tags and not team:
            team = f"[tag_read_error:{tags['__tag_error__']}]"

        rows.append((name, runtime, team))

    # sort by runtime then name for readability
    rows.sort(key=lambda r: (r[1], r[0].lower()))

    headers = ("Name", "pythonVersion", "Team")
    all_rows = [headers] + rows

    widths = [
        max(len(str(r[0])) for r in all_rows) if all_rows else len(headers[0]),
        max(len(str(r[1])) for r in all_rows) if all_rows else len(headers[1]),
        max(len(str(r[2])) for r in all_rows) if all_rows else len(headers[2]),
    ]

    print(f"Region: {region}")
    print(fmt_row(headers, widths))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt_row(r, widths))


if __name__ == "__main__":
    main()
