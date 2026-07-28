#!/usr/bin/env python3
"""Merge Authelia's SMTP notifier settings into the AffairsOS dotenv file."""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


def scalar(value):
    value = value.strip()
    if value[:1] in {"'", '"'}:
        try:
            return str(ast.literal_eval(value))
        except (SyntaxError, ValueError):
            pass
    return value.split(" #", 1)[0].strip()


def parse_smtp(text):
    values = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(username|password|address|sender):\s*(.+?)\s*$", line)
        if match:
            values[match.group(1)] = scalar(match.group(2))
    missing = [key for key in ("username", "password", "address", "sender") if not values.get(key)]
    if missing:
        raise SystemExit(f"Authelia SMTP configuration is missing: {', '.join(missing)}")
    return values


def dotenv_value(value):
    return json.dumps(str(value), ensure_ascii=False)


def merge_dotenv(path, updates):
    lines = path.read_text(encoding="utf-8").splitlines()
    seen = set()
    merged = []
    for line in lines:
        match = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if match and match.group(1) in updates:
            key = match.group(1)
            merged.append(f"{key}={dotenv_value(updates[key])}")
            seen.add(key)
        else:
            merged.append(line)
    if merged and merged[-1]:
        merged.append("")
    for key, value in updates.items():
        if key not in seen:
            merged.append(f"{key}={dotenv_value(value)}")

    temporary = path.with_name(f".{path.name}.email.tmp")
    temporary.write_text("\n".join(merged) + "\n", encoding="utf-8")
    os.chmod(temporary, path.stat().st_mode)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, type=Path)
    args = parser.parse_args()
    smtp = parse_smtp(sys.stdin.read())
    address = urlparse(smtp["address"])
    if not address.hostname:
        raise SystemExit("Authelia SMTP address is invalid")
    use_ssl = address.scheme in {"smtps", "submissions"}
    use_tls = address.scheme in {"submission", "smtp+starttls"}
    port = address.port or (465 if use_ssl else 587 if use_tls else 25)
    updates = {
        "EMAIL_NOTIFICATIONS_ENABLED": "true",
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_HOST": address.hostname,
        "EMAIL_PORT": str(port),
        "EMAIL_HOST_USER": smtp["username"],
        "EMAIL_HOST_PASSWORD": smtp["password"],
        "EMAIL_USE_TLS": str(use_tls).lower(),
        "EMAIL_USE_SSL": str(use_ssl).lower(),
        "EMAIL_TIMEOUT": "10",
        "DEFAULT_FROM_EMAIL": f"行政资产管理 <{smtp['sender']}>",
        "EMAIL_SUBJECT_PREFIX": "[盘清] ",
    }
    merge_dotenv(args.env, updates)
    print("Email environment configuration updated.")


if __name__ == "__main__":
    main()
