"""Collect a small, offline Git preflight for a working tree."""

import argparse
import json
import os
import re
import shutil
import subprocess


REPOSITORY_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CEILING_DIRECTORIES", "GIT_COMMON_DIR",
    "GIT_CONFIG", "GIT_DIR", "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_NAMESPACE", "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX", "GIT_QUARANTINE_PATH", "GIT_SHALLOW_FILE", "GIT_WORK_TREE",
}
IDENTITY = re.compile(rb"([^<>]*) <([^<>]*)> -?\d+ [+-]\d{4}\n")
DIVERGENCE = re.compile(rb"\+([0-9]+) -([0-9]+)")


class ContextError(Exception):
    """A fixed error code safe to return in the JSON result."""


def git_executable():
    if os.name != "nt":
        return shutil.which("git")
    # Python 3.9's shutil.which searches the current directory on Windows.
    for directory in os.get_exec_path():
        directory = directory.strip('"')
        if os.path.isabs(directory):
            executable = os.path.join(directory, "git.exe")
            if os.path.isfile(executable):
                return executable
    return None


def local_git_environment():
    env = {
        key: value for key, value in os.environ.items()
        if key not in REPOSITORY_ENV and not key.startswith("GIT_TRACE")
    }
    env.update(
        GIT_ALLOW_PROTOCOL="", GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0",
        GIT_TERMINAL_PROMPT="0",
    )
    return env


def run_git(command, env, *args):
    try:
        return subprocess.run(
            [*command, *args], env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ContextError("GitTimeout") from exc
    except OSError as exc:
        raise ContextError("GitUnavailable") from exc


def nul_records(output):
    if not output:
        return []
    if not output.endswith(b"\0"):
        raise ContextError("GitOutputInvalid")
    return output[:-1].split(b"\0")


def filter_options(command, env):
    # Git may call a clean filter while refreshing the index in memory.
    result = run_git(
        command, env, "config", "--null", "--name-only", "--get-regexp",
        r"^filter\..+\.(clean|process|required)$",
    )
    if result.returncode not in (0, 1):
        raise ContextError("GitConfigFailed")
    options = []
    for key in sorted(set(nul_records(result.stdout))):
        if b"=" in key:
            raise ContextError("GitFilterUnsupported")
        value = "false" if key.endswith(b".required") else ""
        options.extend(("-c", f"{os.fsdecode(key)}={value}"))
    return options


def parse_status(output):
    counts = dict(staged=0, unstaged=0, untracked=0)
    headers = {}
    records = iter(nul_records(output))
    for record in records:
        kind, _, body = record.partition(b" ")
        if kind == b"#":
            key, _, value = body.partition(b" ")
            headers[key] = value
        elif kind in (b"1", b"2", b"u"):
            pairs = body.partition(b" ")[0]
            if len(pairs) != 2:
                raise ContextError("GitOutputInvalid")
            counts["staged"] += pairs[:1] != b"."
            counts["unstaged"] += pairs[1:] != b"."
            if kind == b"2" and not next(records, None):
                raise ContextError("GitOutputInvalid")
        elif kind == b"?":
            counts["untracked"] += 1
        else:
            raise ContextError("GitOutputInvalid")

    branch = headers.get(b"branch.head")
    head = headers.get(b"branch.oid")
    if not branch or not head:
        raise ContextError("GitOutputInvalid")
    upstream = headers.get(b"branch.upstream")
    divergence = DIVERGENCE.fullmatch(headers.get(b"branch.ab", b""))
    detached = branch == b"(detached)"
    return {
        "branch": None if detached else os.fsdecode(branch), "detached": detached,
        "unborn": head == b"(initial)", "dirty": counts,
        "upstream": os.fsdecode(upstream) if upstream else None,
        "ahead": int(divergence[1]) if divergence else None,
        "behind": int(divergence[2]) if divergence else None,
    }


def resolve_identity(command, env):
    identity = {}
    missing = []
    for role in ("author", "committer"):
        result = run_git(command, env, "var", f"GIT_{role.upper()}_IDENT")
        match = IDENTITY.fullmatch(result.stdout) if result.returncode == 0 else None
        if not match:
            identity[role] = None
            missing.append(role)
            continue
        name, email = (value.decode("utf-8", errors="replace").strip() or None for value in match.groups())
        identity[role] = {"name": name, "email": email}
        missing.extend(f"{role}.{field}" for field, value in identity[role].items() if value is None)
    identity["missing"] = missing
    return identity


def collect(repo):
    executable = git_executable()
    if executable is None:
        raise ContextError("GitUnavailable")
    env = local_git_environment()
    command = [
        os.path.abspath(executable), "--no-pager", "-c", "core.fsmonitor=false",
        "-c", "status.submoduleSummary=false", "-C", os.path.abspath(repo),
    ]
    result = run_git(command, env, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise ContextError("GitWorktreeUnavailable")
    root = os.fsdecode(result.stdout.removesuffix(b"\n"))
    if not os.path.isabs(root):
        raise ContextError("GitOutputInvalid")
    command[-1] = root
    filters = filter_options(command, env)
    status = run_git(
        [*command, *filters], env, "status", "--porcelain=v2", "--branch", "-z",
        "--ahead-behind", "--untracked-files=all", "--ignore-submodules=dirty", "--find-renames",
    )
    if status.returncode != 0:
        raise ContextError("GitStatusFailed")
    summary = parse_status(status.stdout)
    if summary["detached"]:
        # A branch can have the same name as porcelain's detached marker.
        head = run_git(command, env, "symbolic-ref", "--quiet", "HEAD")
        if head.returncode == 0:
            summary.update(branch=os.fsdecode(head.stdout.removeprefix(b"refs/heads/").removesuffix(b"\n")),
                           detached=False)
        elif head.returncode != 1:
            raise ContextError("GitHeadUnavailable")
    return {
        "root": root, **summary,
        "external_filters_disabled": bool(filters), "identity": resolve_identity(command, env),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, metavar="DIR", help="Working tree or its subdirectory")
    parser.add_argument("--require-identity", action="store_true", help="Exit 2 if an identity is incomplete")
    args = parser.parse_args(argv)
    try:
        result = collect(args.repo)
    except ContextError as exc:
        print(json.dumps({"error": str(exc)}, separators=(",", ":")))
        return 1
    print(json.dumps(result, separators=(",", ":")))
    return 2 if args.require_identity and result["identity"]["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
