"""Read one scoped page of Sentry issue metadata over HTTPS."""

import argparse
import json
import os
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class DeclineRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def next_cursor(link):
    for match in re.finditer(r'<([^>]+)>\s*((?:;[^,]+)*)', link):
        url, attributes = match.groups()
        if 'rel="next"' in attributes and 'results="true"' in attributes:
            return parse_qs(urlsplit(url).query).get("cursor", [None])[0]
    return None


def issue_summary(issue, project):
    actual = issue["project"]
    if project not in (str(actual.get("id")), actual.get("slug")):
        raise ValueError("Sentry returned an issue outside the requested project")
    return {key: issue[key] for key in ("id", "shortId", "level", "status", "firstSeen", "lastSeen")
            if key in issue and isinstance(issue[key], (str, int))}


def get_issues(args, token):
    origin = urlsplit(args.origin)
    if (origin.scheme != "https" or not origin.hostname or origin.username is not None
            or origin.path not in ("", "/") or origin.query or origin.fragment):
        raise ValueError("--origin must be a trusted HTTPS origin without credentials or path")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", args.organization):
        raise ValueError("--organization must be an ID or slug")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", args.project):
        raise ValueError("--project must specify one ID or slug")
    if not args.environment.strip() or not re.fullmatch(r"[1-9][0-9]*[dhmsw]", args.period):
        raise ValueError("Supply an environment and a positive period such as 24h")
    if not 1 <= args.limit <= 100:
        raise ValueError("--limit must be between 1 and 100")
    params = {"project": args.project, "environment": args.environment, "statsPeriod": args.period,
              "query": args.query, "sort": "date", "limit": args.limit}
    if args.cursor:
        params["cursor"] = args.cursor
    url = f"https://{origin.netloc}/api/0/organizations/{args.organization}/issues/?{urlencode(params)}"
    request = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                      method="GET")
    context = ssl.create_default_context(cafile=args.ca_file)
    with build_opener(DeclineRedirect(), HTTPSHandler(context=context)).open(request, timeout=15) as response:
        body_limit = 4 * 1024 * 1024
        payload = response.read(body_limit + 1)
        if len(payload) > body_limit:
            raise ValueError("Response exceeded 4 MiB; use a smaller --limit")
        data = json.loads(payload)
        if not isinstance(data, list):
            raise ValueError("Sentry reply is not an issue list")
        if len(data) > args.limit:
            raise ValueError("Sentry returned more items than requested")
        return {"issues": [issue_summary(issue, args.project) for issue in data],
                "next_cursor": next_cursor(", ".join(response.headers.get_all("Link", [])))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--period", default="24h")
    parser.add_argument("--query", default="is:unresolved")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--cursor")
    parser.add_argument("--ca-file", help="PEM CA bundle for a private Sentry installation")
    args = parser.parse_args()
    token = os.environ.get("SENTRY_AUTH_TOKEN", "").strip()
    if not token or any(char.isspace() for char in token):
        parser.error("SENTRY_AUTH_TOKEN must supply a single bearer token")
    try:
        print(json.dumps(get_issues(args, token), indent=2))
        return 0
    except HTTPError as error:
        print(f"Sentry request failed with HTTP {error.code}", file=sys.stderr)
    except (URLError, OSError):
        print("Sentry connection, TLS trust or timeout error", file=sys.stderr)
    except (KeyError, AttributeError, TypeError, json.JSONDecodeError, UnicodeError):
        print("Sentry returned unexpected issue data", file=sys.stderr)
    except ValueError as error:
        print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
