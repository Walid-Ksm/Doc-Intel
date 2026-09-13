#!/usr/bin/env python3
"""Script to configure APISIX routes and OpenID Connect plugins via Admin API."""

import json
import os
import sys
import time
import urllib.error
import urllib.request

ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://[::1]:9180/apisix/admin/routes")
ADMIN_KEY = os.getenv("APISIX_ADMIN_KEY", "edd1c9f034335f136f87ad84b625c8f1")
CORE_UPSTREAM = os.getenv("CORE_UPSTREAM", "host.docker.internal:8000")
REPORTS_UPSTREAM = os.getenv("REPORTS_UPSTREAM", "host.docker.internal:8081")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:4200,http://localhost")

CORS_HEADERS = (
    "Authorization,Content-Type,Accept,Origin,User-Agent,DNT,Cache-Control,"
    "X-Mx-ReqToken,Keep-Alive,X-Requested-With,If-Modified-Since,"
    "Access-Control-Request-Method,Access-Control-Request-Headers"
)

ROUTES = [
    {
        "id": "1",
        "name": "doc-intelligence-core",
        "uri": "/*",
        "priority": 0,
        "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        "plugins": {
            "cors": {
                "allow_origins": CORS_ORIGINS,
                "allow_methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD",
                "allow_headers": CORS_HEADERS,
                "expose_headers": "Authorization,Content-Type",
                "allow_credential": False,
                "max_age": 3600,
            },
            "proxy-rewrite": {
                "regex_uri": ["^/(.*)", "/$1"],
            },
        },
        "upstream": {
            "nodes": {
                CORE_UPSTREAM: 1,
            },
            "type": "roundrobin",
        },
    },
    {
        "id": "2",
        "name": "doc-intelligence-reports",
        "uri": "/reports/*",
        "priority": 10,
        "methods": ["GET", "OPTIONS", "HEAD"],
        "plugins": {
            "cors": {
                "allow_origins": CORS_ORIGINS,
                "allow_methods": "GET,OPTIONS,HEAD",
                "allow_headers": CORS_HEADERS,
                "expose_headers": "Authorization,Content-Type",
                "allow_credential": False,
                "max_age": 3600,
            },
        },
        "upstream": {
            "nodes": {
                REPORTS_UPSTREAM: 1,
            },
            "type": "roundrobin",
        },
    },
]


def wait_for_apisix(max_attempts=15, delay=2):
    """Wait for APISIX admin API to be responsive."""
    probe_url = ADMIN_URL
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(
                probe_url,
                headers={"X-API-KEY": ADMIN_KEY},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    print(f"APISIX Admin API ready (attempt {attempt})")
                    return True
        except urllib.error.HTTPError as e:
            if e.code == 200:
                print(f"APISIX Admin API ready (attempt {attempt})")
                return True
            print(f"Waiting for APISIX at {probe_url}... HTTP {e.code} ({attempt}/{max_attempts})")
            time.sleep(delay)
        except Exception as e:
            print(f"Waiting for APISIX at {probe_url}... {e} ({attempt}/{max_attempts})")
            time.sleep(delay)
    return False


def configure():
    print(f"Configuring APISIX at {ADMIN_URL}")
    print(f"Core Upstream:    {CORE_UPSTREAM}")
    print(f"Reports Upstream: {REPORTS_UPSTREAM}")
    print(f"CORS Origins:     {CORS_ORIGINS}")

    wait_for_apisix()

    for route in ROUTES:
        route_id = route["id"]
        url = f"{ADMIN_URL}/{route_id}"
        payload = {k: v for k, v in route.items() if k != "id"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "X-API-KEY": ADMIN_KEY,
                "Content-Type": "application/json",
            },
            method="PUT",
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"APISIX route '{route['name']}' (id: {route_id}) configured! Status: {resp.status}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            print(f"Error configuring route '{route['name']}' (HTTP {e.code}): {err_body}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"Connection error to APISIX for route '{route['name']}': {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    configure()


