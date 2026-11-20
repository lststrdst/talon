"""Prepare disposable Talon evaluation tasks and grade their actual outcomes."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile


ASSETS = Path(__file__).resolve().parents[1] / "assets"
GIT_TASK = "git-selective-commit"
RETRY_TASK = "sqlite-retry-regression"
VERSION = 1
MARKER = "evaluation.json"
TEST_FILE = "test_retry.py"
SERVICE_FILE = "retry_fixture.py"
BUGGY_SERVICE = ASSETS / "agent-eval/buggy_retry_fixture.py"
FIXED_SERVICE = ASSETS / "retry/example_store.py"
RETRY_RUNNER = ASSETS / "agent-eval/run_retry_tests.py"
IDENTITY = "Talon Eval <talon-eval@example.test>"
README_BASE = b"# Order desk\n\nNotes for the demo order desk.\n"
README_ADDITION = b"Run the checks with `python3 -m unittest discover`."
DRAFT_BASE = b"Draft: discuss the new queue.\n"
DRAFT_STAGED = DRAFT_BASE + b"Include the metrics proposal.\n"
DRAFT_WORKTREE = DRAFT_STAGED + b"Add an example after the meeting.\n"
SCRATCH = b"Temporary note for this fixture.\n"


class EvalError(Exception):
    """An evaluation could not start or could not collect valid results."""


def git_executable():
    # Omit relative PATH entries so a workspace cannot supply the judge's Git.
    search = os.pathsep.join(path for path in os.get_exec_path() if os.path.isabs(path))
    name = "git.exe" if os.name == "nt" else "git"
    executable = shutil.which(name, path=search)
    if executable is None or not os.path.isabs(executable):
        raise EvalError("git_unavailable")
    return executable


def git(repo, *args, allowed=(0,), data=None, worktree=False, allow_push=False):
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR") if key in os.environ}
    env.update(
        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
        GIT_ALLOW_PROTOCOL="file" if allow_push else "", GIT_TERMINAL_PROMPT="0",
        GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0",
        GIT_AUTHOR_DATE="2000-01-01T00:00:00Z", GIT_COMMITTER_DATE="2000-01-01T00:00:00Z",
        LC_ALL="C",
    )
    command = [git_executable(), "--no-pager", "-c", "core.hooksPath=/dev/null",
               "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false"]
    if worktree:
        command.extend((f"--git-dir={repo / '.git'}", f"--work-tree={repo}"))
    try:
        result = subprocess.run(
            [*command, *args], cwd=repo, env=env, input=data if data is not None else b"",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvalError("git_unavailable") from exc
    if result.returncode not in allowed:
        raise EvalError("git_command_failed")
    return result.stdout


def prepare_git(root, push):
    repo = root / "workspace"
    git(repo, "init", "-q", "--template=")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "config", "user.name", "Talon Eval")
    git(repo, "config", "user.email", "talon-eval@example.test")
    (repo / "README.md").write_bytes(README_BASE)
    (repo / "draft.txt").write_bytes(DRAFT_BASE)
    git(repo, "add", "--", "README.md", "draft.txt")
    git(repo, "commit", "-qm", "Seed fixture")
    base = git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    (repo / "draft.txt").write_bytes(DRAFT_STAGED)
    git(repo, "add", "--", "draft.txt")
    (repo / "draft.txt").write_bytes(DRAFT_WORKTREE)
    (repo / "scratch.txt").write_bytes(SCRATCH)

    prompt = """В этом временном репозитории добавь в конец `README.md` отдельный абзац:

Run the checks with `python3 -m unittest discover`.

Создай ровно один коммит в текущей ветке `main`, включив только README.
Используй локальный профиль `Talon Eval <talon-eval@example.test>` как автор и коммитер.
В `draft.txt` уже есть изменения в индексе и отдельные изменения в рабочем файле.
Сохрани и индексную, и рабочую версию черновика. Оставь `scratch.txt` без изменений и вне индекса.
"""
    if push:
        remote = root / "origin.git"
        remote.mkdir()
        git(remote, "init", "-q", "--bare", "--template=")
        git(repo, "remote", "add", "origin", "../origin.git")
        git(repo, "push", "-qu", "origin", "main", allow_push=True)
        prompt += "Отправь `main` в `origin`. Это локальный репозиторий `../origin.git`.\n"
    return {"base": base, "push": push}, prompt


def prepare_retry(root):
    shutil.copyfile(BUGGY_SERVICE, root / "workspace" / SERVICE_FILE)
    prompt = """В сервисе `retry_fixture.py` создание заказа использует SQLite. Если подтверждение
потеряно между записью заказа и получением результата, повтор с тем же ключом может
создать дубль. Добавь регрессию в `test_retry.py` на стандартном `unittest`.

Смоделируй потерю подтверждения после записи через параметр `acknowledge` функции
`submit_order`. Подтверди сохранённые данные до повтора
через отдельное соединение. Повтори операцию с тем же ключом и данными. Проверь,
что в базе осталась одна запись с прежним идентификатором и ответ повтора содержит его же.
Проверь отдельным тестом, что два разных ключа с одинаковыми данными создают две записи.
Используй временную базу для каждого теста. Запусти `python3 -m unittest discover -v`
и укажи наблюдаемое падение. Оставь сервис без изменений.
"""
    return {}, prompt


def prepare(task, root, push):
    if push and task != GIT_TASK:
        raise EvalError("push_requires_git_task")
    root.mkdir()
    (root / "workspace").mkdir()
    details, prompt = prepare_git(root, push) if task == GIT_TASK else prepare_retry(root)
    (root / "PROMPT.md").write_text(prompt, encoding="utf-8")
    (root / MARKER).write_text(json.dumps({"task": task, "version": VERSION, **details}) + "\n",
                               encoding="utf-8")


def is_directory(path):
    return path.is_dir() and not path.is_symlink()


def read_regular(path, limit=131072):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        return None
    return path.read_bytes()


def readme_has_paragraph(content):
    pattern = re.escape(README_BASE) + rb"(?:[ \t]*\n)+" + re.escape(README_ADDITION) + rb"\n*"
    return re.fullmatch(pattern, content.replace(b"\r\n", b"\n")) is not None


def grade_git(root, marker):
    repo = root / "workspace"
    git_dir = repo / ".git"
    if (not is_directory(git_dir) or (git_dir / "commondir").exists()
            or (git_dir / "objects/info/alternates").exists()):
        raise EvalError("invalid_fixture_git_directory")
    base = marker.get("base")
    if not isinstance(base, str) or re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", base) is None:
        raise EvalError("invalid_fixture_base")
    if type(marker.get("push")) is not bool:
        raise EvalError("invalid_fixture_push_setting")

    def inspect(*args, **kwargs):
        return git(repo, *args, worktree=True, **kwargs)

    def blob(content):
        return inspect("hash-object", "--stdin", data=content).strip()

    head = inspect("rev-parse", "--verify", "HEAD").strip()
    commit = inspect("cat-file", "commit", "HEAD")
    headers = commit.split(b"\n\n", 1)[0].splitlines()
    parents = [line[7:] for line in headers if line.startswith(b"parent ")]
    author = [line for line in headers if line.startswith(b"author ")]
    committer = [line for line in headers if line.startswith(b"committer ")]
    identity = IDENTITY.encode("ascii")
    committed_readme = inspect("cat-file", "blob", "HEAD:README.md", allowed=(0, 128))
    readme, draft, staged_draft = (blob(content) for content in (committed_readme, DRAFT_BASE, DRAFT_STAGED))
    tree = inspect("ls-tree", "-rz", "HEAD")
    index = inspect("ls-files", "--stage", "-z").split(b"\0")[:-1]
    expected_tree = b"100644 blob " + readme + b"\tREADME.md\0" + b"100644 blob " + draft + b"\tdraft.txt\0"
    expected_readme_index = b"100644 " + readme + b" 0\tREADME.md"
    expected_draft_index = b"100644 " + staged_draft + b" 0\tdraft.txt"
    working_readme = read_regular(repo / "README.md")
    checks = {
        "branch_main": inspect("symbolic-ref", "-q", "HEAD", allowed=(0, 1)) == b"refs/heads/main\n",
        "one_new_commit": parents == [base.encode("ascii")],
        "readme_only_commit": tree == expected_tree and readme_has_paragraph(committed_readme),
        "fixture_identity": (len(author) == len(committer) == 1
                             and author[0].startswith(b"author " + identity + b" ")
                             and committer[0].startswith(b"committer " + identity + b" ")),
        "readme_final": (working_readme is not None and readme_has_paragraph(working_readme)
                         and working_readme.replace(b"\r\n", b"\n") == committed_readme.replace(b"\r\n", b"\n")
                         and expected_readme_index in index),
        "index_preserved": len(index) == 2 and expected_draft_index in index,
        "worktree_preserved": read_regular(repo / "draft.txt") == DRAFT_WORKTREE,
        "scratch_preserved": (read_regular(repo / "scratch.txt") == SCRATCH
                              and inspect("ls-files", "--others", "-z") == b"scratch.txt\0"),
    }
    evidence = {"head": head.decode("ascii")}
    if marker["push"]:
        remote = root / "origin.git"
        if (not is_directory(remote) or (remote / "commondir").exists()
                or (remote / "objects/info/alternates").exists()):
            raise EvalError("invalid_fixture_remote")
        remote_head = git(remote, "--git-dir=.", "rev-parse", "--verify", "refs/heads/main").strip()
        checks["pushed_to_local_origin"] = remote_head == head and head != base.encode("ascii")
        evidence["remote_head"] = remote_head.decode("ascii")
    return checks, evidence


def sandbox_command(replay, data, python_args):
    if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file():
        def rule(action, operation, kind, path):
            return f"({action} {operation} ({kind} {json.dumps(str(path), ensure_ascii=False)}))"

        executable = Path(sys.executable).resolve()
        runtime = Path(sys.base_prefix).resolve()
        framework_executable = runtime / "Resources/Python.app/Contents/MacOS/Python"
        if framework_executable.is_file():
            executable = framework_executable.resolve()
        profile = "\n".join((
            "(version 1)", "(deny default)", "(allow sysctl-read)",
            rule("allow", "process-exec", "literal", executable),
            rule("allow", "file-read*", "literal", "/"),
            rule("allow", "file-read*", "subpath", "/System/Library"),
            rule("allow", "file-read*", "subpath", "/usr/lib"),
            rule("allow", "file-read*", "literal", "/dev/null"),
            rule("allow", "file-read*", "literal", "/dev/urandom"),
            rule("allow", "file-read*", "literal", executable),
            rule("allow", "file-read*", "subpath", runtime / "lib"),
            rule("allow", "file-read*", "literal", runtime / "Python3"),
            rule("allow", "file-read*", "literal", runtime / "Python"),
            rule("allow", "file-read*", "subpath", replay),
            rule("allow", "file-write*", "subpath", data),
        ))
        return ["/usr/bin/sandbox-exec", "-p", profile, str(executable), *python_args]

    bwrap = shutil.which("bwrap") if sys.platform.startswith("linux") else None
    if bwrap:
        command = [bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--proc", "/proc", "--dev", "/dev"]
        for path in (Path("/usr"), Path("/lib"), Path("/lib64"), Path(sys.base_prefix).resolve()):
            if path.is_dir() and path != Path("/"):
                command.extend(("--ro-bind", str(path), str(path)))
        command.extend(("--ro-bind", str(replay), str(replay), "--bind", str(data), str(data),
                        "--chdir", str(data), str(Path(sys.executable).resolve())))
        return [*command, *python_args]
    raise EvalError("retry_sandbox_unavailable")


def require_linux_sandbox():
    """Check that the current Linux user can start the same isolated interpreter."""
    with tempfile.TemporaryDirectory(prefix="talon-eval-probe-") as directory:
        replay = Path(directory).resolve()
        data = replay / "data"
        data.mkdir()
        command = sandbox_command(replay, data, ["-IBS", "-c", "pass"])
        try:
            subprocess.run(command, cwd=data, env={"PATH": os.defpath, "LC_ALL": "C"},
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise EvalError("retry_sandbox_unavailable") from exc


def replay_retry(test, service, control="none"):
    with tempfile.TemporaryDirectory(prefix="talon-eval-retry-") as directory:
        replay = Path(directory).resolve()
        inputs, data = replay / "input", replay / "data"
        inputs.mkdir()
        data.mkdir()
        (inputs / TEST_FILE).write_bytes(test)
        shutil.copyfile(service, inputs / SERVICE_FILE)
        runner = inputs / RETRY_RUNNER.name
        shutil.copyfile(RETRY_RUNNER, runner)
        report = data / "result.json"
        command = sandbox_command(replay, data, ["-IBS", str(runner), str(report), control])
        env = {"HOME": str(data), "TMPDIR": str(data), "PATH": os.defpath, "LC_ALL": "C"}
        try:
            process = subprocess.run(command, cwd=data, env=env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     timeout=15, check=False)
        except subprocess.TimeoutExpired as exc:
            raise EvalError("retry_replay_timeout") from exc
        except OSError as exc:
            raise EvalError("retry_replay_unavailable") from exc
        content = read_regular(report)
        if process.returncode or content is None:
            raise EvalError("retry_replay_failed")
        try:
            result = json.loads(content)
        except ValueError as exc:
            raise EvalError("retry_replay_invalid_report") from exc
        if not isinstance(result, dict) or result.get("schema") != 1:
            raise EvalError("retry_replay_invalid_report")
        return result


def grade_retry(root, run_candidate_tests):
    repo = root / "workspace"
    test = read_regular(repo / TEST_FILE)
    checks = {"service_unchanged": read_regular(repo / SERVICE_FILE) == BUGGY_SERVICE.read_bytes(),
              "test_present": bool(test)}
    if not all(checks.values()):
        return checks, {}
    if not run_candidate_tests:
        raise EvalError("retry_execution_requires_opt_in")
    if sys.platform.startswith("linux"):
        require_linux_sandbox()
    red = replay_retry(test, BUGGY_SERVICE)
    green = replay_retry(test, FIXED_SERVICE)
    retry_ids = set(red["retry_duplicate"]) & set(red["failed_ids"]) & set(green["retry_kept_one"]) & set(green["passed_ids"])
    checks.update(
        buggy_retry_detected=(red["failures"] > 0 and red["errors"] == 0
                              and bool(set(red["retry_duplicate"]) & set(red["failed_ids"]))),
        corrected_retry_passes=(green["tests"] > 0 and green["failures"] == green["errors"] == 0
                                and bool(set(green["retry_kept_one"]) & set(green["passed_ids"]))),
        same_retry_test=bool(retry_ids),
        distinct_keys_pass=bool((set(red["distinct_keys"]) & set(red["passed_ids"]))
                                & (set(green["distinct_keys"]) & set(green["passed_ids"]))),
        no_skips=red["skipped"] == green["skipped"] == 0,
        same_tests=red["test_ids"] == green["test_ids"],
    )
    variants = {"buggy": red, "corrected": green}
    if all(checks.values()):
        for control, check in (("wrong_response_id", "checks_response_id"),
                               ("replaced_row_id", "checks_persisted_id")):
            outcome = replay_retry(test, FIXED_SERVICE, control)
            variants[control] = outcome
            checks[check] = (outcome["errors"] == outcome["skipped"] == 0
                             and outcome["test_ids"] == green["test_ids"]
                             and bool(retry_ids & set(outcome[control]) & set(outcome["failed_ids"])))
    keys = ("tests", "failures", "errors", "skipped")
    return checks, {variant: {key: report[key] for key in keys}
                    for variant, report in variants.items()}


def grade(task, root, run_candidate_tests):
    content = read_regular(root / MARKER)
    marker = json.loads(content) if content else None
    if (not isinstance(marker, dict) or marker.get("task") != task or marker.get("version") != VERSION
            or not is_directory(root / "workspace")):
        raise EvalError("invalid_fixture")
    if task == GIT_TASK:
        return grade_git(root, marker)
    return grade_retry(root, run_candidate_tests)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("prepare", help="Create a new disposable task directory")
    judge = commands.add_parser("grade", help="Grade an existing prepared task directory")
    for command in (make, judge):
        command.add_argument("task", choices=(GIT_TASK, RETRY_TASK))
        command.add_argument("directory", type=Path)
    make.add_argument("--push", action="store_true", help="Require a push to local origin (Git task)")
    judge.add_argument("--run-candidate-tests", action="store_true",
                       help="Replay SQLite candidate tests in a supported OS sandbox")
    args = parser.parse_args(argv)
    result = {"task": args.task, "version": VERSION}
    try:
        root = args.directory.resolve()
        if args.command == "prepare":
            prepare(args.task, root, args.push)
            result["status"] = "prepared"
        else:
            checks, evidence = grade(args.task, root, args.run_candidate_tests)
            result.update(status="pass" if all(checks.values()) else "fail", checks=checks, evidence=evidence)
    except (EvalError, OSError, ValueError, KeyError, TypeError) as exc:
        error = str(exc) if isinstance(exc, EvalError) else type(exc).__name__
        result.update(status="error", error=error)
    print(json.dumps(result, ensure_ascii=False))
    return {"prepared": 0, "pass": 0, "fail": 1, "error": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
