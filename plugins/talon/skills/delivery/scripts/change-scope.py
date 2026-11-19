"""Summarize local Git changes and, optionally, changes since a common ancestor."""

import argparse
import json
import os
import re
import shutil
import subprocess


DEFAULT_LIMIT = 60
MAX_LIMIT = 1000
GIT_TIMEOUT = 30
CHANGE_KINDS = ("staged", "unstaged", "untracked", "committed")
WORKTREE_FIELDS = {b"1": 8, b"2": 9, b"u": 10}
REPOSITORY_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CEILING_DIRECTORIES", "GIT_COMMON_DIR",
    "GIT_CONFIG", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_DIR",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_GRAFT_FILE", "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE", "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY", "GIT_PREFIX", "GIT_QUARANTINE_PATH",
    "GIT_SHALLOW_FILE", "GIT_WORK_TREE",
}


class ScopeError(Exception):
    """A fixed error code without raw Git output."""


def git_executable():
    if os.name != "nt":
        return shutil.which("git")
    # Older Python versions search the current directory first on Windows.
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
    env.update(GIT_ALLOW_PROTOCOL="", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    return env


def run_git(command, args, env, error, accepted_codes=(0,)):
    try:
        result = subprocess.run(
            [*command, *args], env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScopeError("GitTimeout") from exc
    except OSError as exc:
        raise ScopeError("GitUnavailable") from exc
    if result.returncode not in accepted_codes:
        raise ScopeError(error)
    return result.stdout


def decode_path(value):
    if not value:
        raise ScopeError("GitOutputInvalid")
    return value.decode("utf-8", errors="surrogateescape")


def oid(value):
    if not re.fullmatch(rb"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
        raise ScopeError("GitOutputInvalid")
    return value.decode("ascii")


def nul_fields(output):
    if not output:
        return []
    if not output.endswith(b"\0"):
        raise ScopeError("GitOutputInvalid")
    return output[:-1].split(b"\0")


def filter_options(command, env):
    # Git can use a clean filter to compare a worktree file with the index.
    keys = run_git(
        command, ("config", "--null", "--name-only", "--get-regexp",
                  r"^filter\..+\.(clean|process|required)$"),
        env, "GitConfigFailed", accepted_codes=(0, 1),
    )
    options = []
    for key in sorted(set(nul_fields(keys))):
        if b"=" in key:
            raise ScopeError("GitFilterUnsupported")
        value = "false" if key.endswith(b".required") else ""
        options.extend(("-c", f"{decode_path(key)}={value}"))
    return options


def add_change(changes, status, path, old_path=None):
    change = {"path": decode_path(path), "status": status.decode("ascii")}
    if old_path is not None:
        change["old_path"] = decode_path(old_path)
    changes.append(change)


def parse_worktree(output, summary):
    records = iter(nul_fields(output))
    has_head = False
    for record in records:
        kind, _, body = record.partition(b" ")
        if kind == b"#":
            if body.startswith(b"branch.oid "):
                value = body[len(b"branch.oid "):]
                summary["head"] = None if value == b"(initial)" else oid(value)
                has_head = True
        elif kind == b"?":
            add_change(summary["untracked"], b"?", body)
        elif kind in WORKTREE_FIELDS:
            field_count = WORKTREE_FIELDS[kind]
            fields = record.split(b" ", field_count)
            if len(fields) != field_count + 1 or not re.fullmatch(rb"[.MTADRCU]{2}", fields[1]):
                raise ScopeError("GitOutputInvalid")
            index_status, worktree_status = fields[1][:1], fields[1][1:]
            path = fields[-1]
            if kind == b"u":
                summary["conflicts"].append(decode_path(path))
                continue
            old_path = next(records, b"") if kind == b"2" else None
            for layer, status in (("staged", index_status), ("unstaged", worktree_status)):
                if status in (b"R", b"C") and not old_path:
                    raise ScopeError("GitOutputInvalid")
                if status != b".":
                    add_change(summary[layer], status, path, old_path if status in (b"R", b"C") else None)
        else:
            raise ScopeError("GitOutputInvalid")
    if not has_head:
        raise ScopeError("GitOutputInvalid")


def parse_committed(output, changes):
    fields = iter(nul_fields(output))
    for status in fields:
        if not re.fullmatch(rb"(?:[TADUXB]|M[0-9]*|[RC][0-9]+)", status):
            raise ScopeError("GitOutputInvalid")
        if status.startswith((b"R", b"C")):
            old_path = next(fields, b"")
            add_change(changes, status[:1], next(fields, b""), old_path)
        else:
            add_change(changes, status[:1], next(fields, b""))


def collect(project, base, summary):
    executable = git_executable()
    if executable is None:
        raise ScopeError("GitUnavailable")
    env = local_git_environment()
    command = [
        os.path.abspath(executable), "--no-pager", "--no-optional-locks",
        "-c", "core.fsmonitor=", "-c", "status.submoduleSummary=false",
    ]
    selected = [*command, "-C", os.path.abspath(project)]
    root_output = run_git(selected, ("rev-parse", "--show-toplevel"), env, "GitWorktreeUnavailable")
    root = decode_path(root_output.removesuffix(b"\n"))
    summary["project_root"] = root
    command.extend(("-C", root))
    filters = filter_options(command, env)
    summary["external_filters_disabled"] = bool(filters)
    status = run_git(
        [*command, *filters],
        ("status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all",
         "--ignore-submodules=dirty", "--find-renames"),
        env, "GitStatusFailed",
    )
    parse_worktree(status, summary)
    if base is None:
        return
    if not summary["head"]:
        raise ScopeError("GitHeadUnborn")
    base_output = run_git(
        command, ("rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"),
        env, "GitBaseUnavailable",
    )
    summary["base"] = oid(base_output.rstrip(b"\n"))
    merge_output = run_git(
        command, ("merge-base", "--all", summary["base"], summary["head"]),
        env, "GitMergeBaseUnavailable",
    )
    merge_bases = merge_output.splitlines()
    if len(merge_bases) != 1:
        raise ScopeError("GitMergeBaseAmbiguous")
    summary["merge_base"] = oid(merge_bases[0])
    committed = run_git(
        command, ("diff", "--name-status", "-z", "--no-ext-diff", "--no-textconv",
                  "--find-renames", "--ignore-submodules=dirty",
                  summary["merge_base"], summary["head"], "--"),
        env, "GitDiffFailed",
    )
    parse_committed(committed, summary["committed"])


def limit_changes(summary, limit):
    paths = set(summary["conflicts"])
    for kind in CHANGE_KINDS:
        for change in summary[kind]:
            paths.add(change["path"])
            if "old_path" in change:
                paths.add(change["old_path"])
    summary["path_count"] = len(paths)
    summary["truncated"] = len(paths) > limit
    summary["paths"] = sorted(paths)[:limit]
    visible = set(summary["paths"])
    summary["conflicts"] = sorted(visible.intersection(summary["conflicts"]))
    for kind in CHANGE_KINDS:
        summary[kind] = sorted(
            (change for change in summary[kind]
             if change["path"] in visible or change.get("old_path") in visible),
            key=lambda change: (change["path"], change["status"], change.get("old_path", "")),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Directory inside the intended Git worktree")
    parser.add_argument("--base", help="Local commit ref for an optional merge-base comparison")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum distinct paths shown")
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_LIMIT:
        parser.error(f"--limit must be between 1 and {MAX_LIMIT}")
    if args.base == "":
        parser.error("--base cannot be empty")

    summary = {
        "project_root": None,
        "head": None,
        "base": None,
        "merge_base": None,
        "conflicts": [],
        "external_filters_disabled": False,
        **{kind: [] for kind in CHANGE_KINDS},
    }
    try:
        collect(args.project, args.base, summary)
    except ScopeError as error:
        summary["error"] = str(error)
    limit_changes(summary, args.limit)
    print(json.dumps(summary))
    return 1 if "error" in summary else 0


if __name__ == "__main__":
    raise SystemExit(main())
