"""Report stack and runner evidence without running project code."""

import argparse
from collections import deque
import json
import os
from pathlib import Path
import re
import stat


MAX_DEPTH = 6
MAX_ENTRIES = 12000
MAX_ANCESTOR_ENTRIES = 3000
MAX_DIRECTORY_ENTRIES = 3000
MAX_MANIFESTS = 128
MAX_MANIFEST_BYTES = 256 * 1024
MAX_EVIDENCE_PATHS = 4
MAX_SCRIPT_MANIFESTS = 32
MAX_SCRIPT_KEYS = 24

SKIP_DIRECTORIES = {
    "__pycache__", "archive", "archives", "artifacts", "backup", "backups",
    "build-output", "coverage", "credentials", "dist", "node_modules", "obj",
    "out", "release", "releases", "secrets", "site-packages", "snapshot",
    "snapshots", "target", "vendor", "venv",
}
SNAPSHOT_DIRECTORY = re.compile(r"(?:^mac-transfer-|[-_](?:upload|candidate|draft|backup|snapshot)$)")
SKIP_FILE = re.compile(r"^(?:credentials?|secrets?|tokens?)(?:[._-]|$)")

LOCK_RUNNERS = {
    "bun.lock": "bun", "bun.lockb": "bun", "npm-shrinkwrap.json": "npm",
    "package-lock.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn",
}
FILE_SIGNALS = {
    "bunfig.toml": "node", "composer.lock": "php", "feeds.conf.default": "openwrt",
    "go.mod": "go", "go.work": "go", "index.htm": "web-static",
    "index.html": "web-static", "package.swift": "swift", "pipfile": "python",
    "pipfile.lock": "python", "pnpm-workspace.yaml": "node", "poetry.lock": "python",
    "setup.cfg": "python", "setup.py": "python", "tsconfig.json": "typescript",
    "uv.lock": "python",
}
FILE_RUNNERS = {
    ".actrc": "act", ".justfile": "just", ".mise.toml": "mise", "justfile": "just", "mise.toml": "mise",
    "noxfile.py": "nox", "nx.json": "nx", "taskfile.yml": "task", "taskfile.yaml": "task",
    "taskfile.dist.yml": "task", "taskfile.dist.yaml": "task", "uv.lock": "uv",
    "turbo.json": "turbo", "turbo.jsonc": "turbo",
    "phpunit.xml": "phpunit", "phpunit.xml.dist": "phpunit", "pytest.ini": "pytest",
    "pesterconfiguration.psd1": "pester",
}
EXTENSION_SIGNALS = {
    ".bash": "shell", ".bat": "windows-native", ".cmd": "windows-native",
    ".cs": "csharp", ".csproj": "csharp", ".cts": "typescript", ".fish": "shell",
    ".go": "go", ".js": "javascript", ".jsx": "javascript", ".cjs": "javascript",
    ".lua": "lua", ".mjs": "javascript", ".mts": "typescript", ".php": "php",
    ".ps1": "powershell", ".psd1": "powershell", ".psm1": "powershell",
    ".py": "python", ".pyi": "python", ".sh": "shell", ".sql": "sql",
    ".sqlite": "sqlite", ".sqlite3": "sqlite", ".swift": "swift", ".ts": "typescript",
    ".tsx": "typescript", ".vbs": "windows-native", ".webmanifest": "pwa", ".zsh": "shell",
}

NODE_SIGNALS = {
    "react": {"react", "react-dom"}, "next": {"next"}, "vite": {"vite"},
    "express": {"express"}, "typescript": {"typescript"},
    "nestjs": {"@nestjs/core"}, "prisma": {"prisma", "@prisma/client"},
    "redis": {"redis", "ioredis", "@redis/client"}, "bullmq": {"bullmq"},
    "tailwind": {"tailwindcss", "@tailwindcss/vite"}, "vinext": {"vinext"},
    "postgresql": {"pg", "postgres", "postgresql", "pg-promise", "@neondatabase/serverless"},
    "sqlite": {"sqlite", "sqlite3", "better-sqlite3", "@libsql/client"},
    "testcontainers": {"testcontainers", "@testcontainers/postgresql", "@testcontainers/redis", "@testcontainers/mysql"},
    "pwa": {"vite-plugin-pwa", "next-pwa", "@ducanh2912/next-pwa", "workbox-webpack-plugin"},
}
NODE_RUNNERS = {
    "jest": {"jest", "@jest/core", "ts-jest"}, "vitest": {"vitest"},
    "playwright": {"@playwright/test"}, "mocha": {"mocha"},
}
PHP_SIGNALS = {
    "laravel": {"laravel/framework"}, "postgresql": {"ext-pgsql", "ext-pdo_pgsql"},
    "sqlite": {"ext-sqlite3", "ext-pdo_sqlite"}, "redis": {"ext-redis", "predis/predis"},
}
PHP_RUNNERS = {"phpunit": {"phpunit/phpunit"}, "pest": {"pestphp/pest"}}
PYTHON_SIGNALS = {
    "fastapi": {"fastapi"}, "redis": {"redis"},
    "testcontainers": {"testcontainers"},
    "postgresql": {"asyncpg", "psycopg", "psycopg-binary", "psycopg2", "psycopg2-binary", "pg8000"},
    "sqlite": {"aiosqlite", "pysqlite3", "pysqlite3-binary", "apsw"},
}
PYTHON_RUNNERS = {"pytest": {"pytest"}, "testinfra": {"pytest-testinfra"}, "nox": {"nox"}}

REQUIREMENTS_NAME = re.compile(r"(?:requirements|constraints)(?:[.-][a-z0-9_.-]+)?\.(?:txt|in)$")
COMPOSE_NAME = re.compile(r"(?:docker-)?compose(?:\.[a-z0-9_-]+)*\.ya?ml$")
JS_CONFIG = re.compile(r"(next|vite|vitest|jest|playwright)\.config\.(?:[cm]?[jt]s)$")
TYPE_CONFIG = re.compile(r"tsconfig\.[a-z0-9_.-]+\.json$")
SAFE_SCRIPT = re.compile(
    r"(?:analyze|build|check|compile|dev|e2e|format|lint|preview|qa|smoke|start|test|type-?check|validate|verify)"
    r"(?:[-:][a-z0-9][a-z0-9._-]*(?::[a-z0-9][a-z0-9._-]*)*)?",
    re.ASCII,
)
PACKAGE_REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?=\s*$|[\s<>=!~\[;@])")
QUOTED_VALUE = re.compile(r"\"([^\"\n]*)\"|'([^'\n]*)'")
SECTION = re.compile(r"^\[([^\[\]]+)\]$")
ASSIGNMENT = re.compile(r"^([A-Za-z0-9_.-]+)\s*=\s*(.*)$")
NODE_TEST = re.compile(r"^\s*node\s+--test(?:\s|$)")
UNITTEST = re.compile(r"^\s*[@+\-]?(?:python(?:3(?:\.\d+)?)?|\$\(PYTHON\))\s+-m\s+unittest(?:\s|$)")
PYTEST = re.compile(r"^\s*(?:(?:uv|poetry)\s+run\s+)?(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?pytest(?:\s|$)")
WORKFLOW_RUN = re.compile(r"^(\s*(?:-\s+)?)run:\s*(.*)$")
ACTIONLINT = re.compile(r"^\s*actionlint(?:\s|$)")
WORKFLOW_RUNNERS = {"actionlint": ACTIONLINT, "node-test": NODE_TEST, "pytest": PYTEST, "unittest": UNITTEST}
COMPOSE_IMAGE = re.compile(
    r"^[ \t]+image:[ \t]*['\"]?(?:(?:docker\.io/)?library/|docker\.io/)?(postgres|redis)(?:[:@][\w.:@/-]+)?"
    r"['\"]?[ \t]*(?:#.*)?$", re.MULTILINE
)
OPENWRT_INCLUDE = re.compile(
    r"^\s*include\s+(?:\$\(TOPDIR\)/rules\.mk|\$\(INCLUDE_DIR\)/(?:package|kernel|host-build)\.mk|"
    r"(?:\.\./)+luci\.mk)\s*(?:#.*)?$", re.MULTILINE
)
WINDOWS_PROJECT = re.compile(
    r"<(?:UseWPF|UseWindowsForms)>\s*true\s*</(?:UseWPF|UseWindowsForms)>|"
    r"<TargetFrameworks?>[^<]*-windows(?:\d[\d.]*)?(?:\s|;|<)", re.IGNORECASE
)


def skip_directory(name):
    return name.startswith(".") or name in SKIP_DIRECTORIES or SNAPSHOT_DIRECTORY.search(name) is not None


def skip_file(name):
    return (name.startswith(".") and name not in FILE_RUNNERS) or SKIP_FILE.match(name) is not None


def is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def project_scope(project_path, target_path):
    requested_root = Path(os.path.abspath(Path(project_path).expanduser()))
    root = requested_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--project must be a readable directory")

    target = Path(target_path).expanduser() if target_path else Path(".")
    if ".." in target.parts:
        raise ValueError("--target must stay inside the project and contain no parent components")
    if target.is_absolute():
        for base in (requested_root, root):
            try:
                target = target.relative_to(base)
                break
            except ValueError:
                continue
        else:
            raise ValueError("--target must stay inside the project")
    elif target.anchor:
        raise ValueError("--target must stay inside the project")

    current = root
    for component in target.parts:
        current = current / component
        info = current.lstat()
        if is_link(info):
            raise ValueError("--target must contain no symbolic links or junctions")
        if stat.S_ISDIR(info.st_mode):
            excluded = skip_directory(current.name.casefold())
        elif stat.S_ISREG(info.st_mode):
            excluded = skip_file(current.name.casefold())
        else:
            excluded = True
        if excluded:
            raise ValueError("--target is outside the scannable scope")
    return root, current


def manifest_kind(path):
    name = path.name.casefold()
    exact = {
        "composer.json": "composer", "package.json": "package", "manifest.json": "web-manifest",
        "pyproject.toml": "pyproject", "pipfile": "pipfile", "setup.cfg": "python-config",
        "tox.ini": "python-config", "makefile": "makefile", "gnumakefile": "makefile",
    }
    if name in exact:
        return exact[name]
    if REQUIREMENTS_NAME.fullmatch(name) or (
        path.parent.name.casefold() == "requirements" and path.suffix.casefold() in {".txt", ".in"}
    ):
        return "requirements"
    if COMPOSE_NAME.fullmatch(name):
        return "compose"
    if path.suffix.casefold() == ".csproj":
        return "csproj"
    if path.suffix.casefold() in {".yml", ".yaml"} and path.parent.parts[-2:] == (".github", "workflows"):
        return "workflow"
    return None


def dict_value(value):
    return value if isinstance(value, dict) else {}


def dependency_names(data, sections):
    return {name.casefold() for section in sections for name in dict_value(data.get(section))}


def python_dependency_names(lines):
    names = set()
    for line in lines:
        match = PACKAGE_REQUIREMENT.match(line.strip())
        if match:
            names.add(re.sub(r"[-_.]+", "-", match[1].casefold()))
    return names


def python_metadata(text):
    """Read dependency declarations and runner tables shared across Python versions."""
    section = ""
    multiline = False
    dependencies = []
    runners = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        header = SECTION.fullmatch(line)
        if header:
            section = header[1].strip().casefold()
            multiline = False
            if section in {"pytest", "tool:pytest", "tool.pytest", "tool.pytest.ini_options"}:
                runners.add("pytest")
            if section == "tool.unittest":
                runners.add("unittest")
            continue
        if multiline:
            dependencies.extend(match[1] or match[2] for match in QUOTED_VALUE.finditer(line))
            multiline = not line.endswith("]")
            continue
        assignment = ASSIGNMENT.fullmatch(line)
        if not assignment:
            if (section.startswith("testenv") or section.startswith("tool.tox")) and UNITTEST.match(line):
                runners.add("unittest")
            continue
        key, value = assignment.groups()
        keyed_dependencies = section in {"packages", "dev-packages", "tool.poetry.dependencies",
                                        "tool.poetry.dev-dependencies"} or (
            section.startswith("tool.poetry.group.") and section.endswith(".dependencies")
        )
        if keyed_dependencies:
            dependencies.append(key)
        array_dependencies = (section, key) in {("project", "dependencies"), ("tool.uv", "dev-dependencies")} or (
            section in {"project.optional-dependencies", "dependency-groups", "tool.pdm.dev-dependencies"}
        )
        if array_dependencies and value.startswith("["):
            dependencies.extend(match[1] or match[2] for match in QUOTED_VALUE.finditer(value))
            multiline = not value.endswith("]")
        if section.startswith("testenv") or section.startswith("tool.tox"):
            if key.startswith("commands") and UNITTEST.match(value):
                runners.add("unittest")
    return python_dependency_names(dependencies), runners


def workflow_runners(content):
    runners = set()
    block_indent = None
    for line in content.splitlines():
        run = WORKFLOW_RUN.fullmatch(line)
        if run:
            command = run[2].strip().strip("\"'")
            block_indent = len(run[1]) if command.startswith(("|", ">")) else None
        elif block_indent is not None and len(line) - len(line.lstrip()) > block_indent:
            command = line.strip()
        elif not line.strip():
            continue
        else:
            block_indent = None
            continue
        for runner, pattern in WORKFLOW_RUNNERS.items():
            if pattern.match(command):
                runners.add(runner)
    return runners


class Detection:
    def __init__(self, root, scope):
        self.root = root
        self.scope = scope
        self.signals = {}
        self.runners = {}
        self.scripts = {}
        self.entries = 0
        self.manifests = 0
        self.truncated = False

    def result(self):
        result = {
            "scope": self.scope.relative_to(self.root).as_posix(),
            "signals": {label: sorted(paths) for label, paths in self.signals.items()},
            "runners": {label: sorted(paths) for label, paths in self.runners.items()},
            "scripts": self.scripts,
        }
        if self.truncated:
            result["truncated"] = True
        return result

    def add(self, bucket, label, path):
        if not label:
            return
        evidence = bucket.setdefault(label, [])
        relative = path.relative_to(self.root).as_posix()
        if relative in evidence:
            return
        evidence.append(relative)
        if len(evidence) > MAX_EVIDENCE_PATHS:
            evidence.sort(key=evidence_priority)
            evidence.pop()

    def add_dependencies(self, names, signals, runners, path):
        for label, supported in signals.items():
            if names & supported:
                self.add(self.signals, label, path)
        for label, supported in runners.items():
            if names & supported:
                self.add(self.runners, label, path)

    def add_scripts(self, data, path, kind):
        items = dict_value(data.get("scripts"))
        names = sorted(
            name for name, command in items.items()
            if len(name) <= 80 and SAFE_SCRIPT.fullmatch(name)
            and (isinstance(command, str) or (kind == "composer" and isinstance(command, list)
                                             and all(isinstance(item, str) for item in command)))
        )
        if not names:
            return
        if len(self.scripts) >= MAX_SCRIPT_MANIFESTS:
            self.truncated = True
            return
        if len(names) > MAX_SCRIPT_KEYS:
            self.truncated = True
        self.scripts[path.relative_to(self.root).as_posix()] = names[:MAX_SCRIPT_KEYS]

    def read_manifest(self, path):
        if self.manifests >= MAX_MANIFESTS:
            self.truncated = True
            return ""
        self.manifests += 1
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            with open(path, "rb", opener=lambda name, mode: os.open(name, mode | flags)) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or is_link(info):
                    return ""
                if info.st_size > MAX_MANIFEST_BYTES:
                    self.truncated = True
                    return ""
                content = stream.read(MAX_MANIFEST_BYTES + 1)
        except OSError:
            return ""
        if len(content) > MAX_MANIFEST_BYTES:
            self.truncated = True
            return ""
        return content.decode("utf-8-sig", errors="replace")

    def inspect_json(self, kind, path, content):
        try:
            data = dict_value(json.loads(content))
        except (ValueError, RecursionError):
            return
        if kind == "web-manifest":
            if isinstance(data.get("start_url"), str) and any(k in data for k in ("name", "short_name", "display")):
                self.add(self.signals, "pwa", path)
            return
        self.add_scripts(data, path, kind)
        if kind == "composer":
            names = dependency_names(data, ("require", "require-dev"))
            self.add_dependencies(names, PHP_SIGNALS, PHP_RUNNERS, path)
            return
        names = dependency_names(data, ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"))
        self.add_dependencies(names, NODE_SIGNALS, NODE_RUNNERS, path)
        if isinstance(dict_value(data.get("engines")).get("vscode"), str):
            self.add(self.signals, "vscode-extension", path)
        manager = data.get("packageManager")
        if isinstance(manager, str):
            name, delimiter, version = manager.partition("@")
            if delimiter and version and name in {"npm", "pnpm", "yarn", "bun"}:
                self.add(self.runners, name, path)
        scripts = dict_value(data.get("scripts"))
        if any(key.startswith("test") and isinstance(value, str) and NODE_TEST.match(value) for key, value in scripts.items()):
            self.add(self.runners, "node-test", path)

    def inspect_manifest(self, kind, path):
        if kind in {"pyproject", "pipfile", "requirements"}:
            self.add(self.signals, "python", path)
        content = self.read_manifest(path)
        if not content:
            return
        if kind in {"package", "composer", "web-manifest"}:
            self.inspect_json(kind, path, content)
        elif kind in {"pyproject", "pipfile", "python-config", "requirements"}:
            if kind == "requirements":
                names = python_dependency_names(content.splitlines())
            else:
                names, runners = python_metadata(content)
                for runner in runners:
                    self.add(self.runners, runner, path)
            self.add_dependencies(names, PYTHON_SIGNALS, PYTHON_RUNNERS, path)
        elif kind == "compose":
            for image in COMPOSE_IMAGE.findall(content):
                self.add(self.signals, {"postgres": "postgresql", "redis": "redis"}[image], path)
        elif kind == "csproj" and WINDOWS_PROJECT.search(content):
            self.add(self.signals, "windows-native", path)
        elif kind == "workflow":
            for runner in workflow_runners(content):
                self.add(self.runners, runner, path)
        elif kind == "makefile":
            if OPENWRT_INCLUDE.search(content):
                self.add(self.signals, "openwrt", path)
            if any(line.startswith("\t") and UNITTEST.match(line) for line in content.splitlines()):
                self.add(self.runners, "unittest", path)

    def inspect_file(self, path):
        name = path.name.casefold()
        extension = path.suffix.casefold()
        self.add(self.signals, EXTENSION_SIGNALS.get(extension), path)
        self.add(self.signals, FILE_SIGNALS.get(name), path)
        self.add(self.runners, FILE_RUNNERS.get(name), path)
        if name == "molecule.yml" and path.parent.parent.name.casefold() == "molecule":
            self.add(self.runners, "molecule", path)
        manager = LOCK_RUNNERS.get(name)
        if manager or name == "package.json":
            self.add(self.signals, "node", path)
            self.add(self.runners, manager, path)
        if name == "composer.json":
            self.add(self.signals, "php", path)
            self.add(self.runners, "composer", path)
        if name == "dockerfile" or name.startswith("dockerfile.") or COMPOSE_NAME.fullmatch(name):
            self.add(self.signals, "docker", path)
        if TYPE_CONFIG.fullmatch(name):
            self.add(self.signals, "typescript", path)
        config = JS_CONFIG.fullmatch(name)
        if config:
            if config[1] in {"next", "vite"}:
                self.add(self.signals, config[1], path)
            else:
                self.add(self.runners, config[1], path)
        if name.endswith(".tests.ps1"):
            self.add(self.runners, "pester", path)
        elif name.startswith("test-") and extension == ".ps1":
            self.add(self.runners, "powershell-test", path)
        if name.endswith("_test.go"):
            self.add(self.runners, "go-test", path)
        if extension == ".swift" and "Tests" in path.relative_to(self.root).parts[:-1]:
            self.add(self.runners, "swift-test", path)
        if extension == ".bats":
            self.add(self.signals, "shell", path)
            self.add(self.runners, "bats", path)
        if extension in {".sln", ".slnx", ".csproj", ".fsproj", ".vbproj"}:
            self.add(self.runners, "dotnet", path)
        kind = manifest_kind(path)
        if kind:
            self.inspect_manifest(kind, path)

    def children(self, directory, manifests_only=False, entry_limit=MAX_ENTRIES, workflows=True):
        children = []
        try:
            with os.scandir(directory) as entries:
                for index, entry in enumerate(entries):
                    if index >= MAX_DIRECTORY_ENTRIES or self.entries >= entry_limit:
                        self.truncated = True
                        break
                    self.entries += 1
                    name = entry.name.casefold()
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if is_link(info):
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        if workflows and entry.name == ".github":
                            self.inspect_workflows(Path(entry.path), entry_limit)
                        elif not manifests_only and not skip_directory(name):
                            children.append((Path(entry.path), True))
                    elif stat.S_ISREG(info.st_mode) and not skip_file(name):
                        path = Path(entry.path)
                        if not manifests_only or ancestor_marker(path):
                            children.append((path, False))
        except OSError:
            return children
        return sorted(children)

    def inspect_workflows(self, github, entry_limit):
        workflows = github / "workflows"
        try:
            info = workflows.lstat()
        except OSError:
            return
        if not stat.S_ISDIR(info.st_mode) or is_link(info):
            return
        for path, _ in self.children(workflows, manifests_only=True, entry_limit=entry_limit, workflows=False):
            if manifest_kind(path) == "workflow":
                self.inspect_file(path)

    def scan(self):
        directory = self.scope
        while directory != self.root:
            directory = directory.parent
            for path, _ in self.children(directory, manifests_only=True, entry_limit=MAX_ANCESTOR_ENTRIES):
                if path != self.scope:
                    self.inspect_file(path)

        if self.scope.is_file():
            self.inspect_file(self.scope)
        else:
            queue = deque([(self.scope, 0)])
            while queue and self.entries < MAX_ENTRIES:
                directory, depth = queue.popleft()
                for path, is_directory in self.children(directory):
                    if not is_directory:
                        self.inspect_file(path)
                    elif depth < MAX_DEPTH:
                        queue.append((path, depth + 1))
                    else:
                        self.truncated = True
            if queue:
                self.truncated = True


def ancestor_marker(path):
    name = path.name.casefold()
    return (
        name in LOCK_RUNNERS or name in FILE_RUNNERS or (name in FILE_SIGNALS and name not in {"index.htm", "index.html"})
        or JS_CONFIG.fullmatch(name) or TYPE_CONFIG.fullmatch(name)
        or name == "dockerfile" or name.startswith("dockerfile.")
        or path.suffix.casefold() in {".sln", ".slnx", ".csproj", ".fsproj", ".vbproj"}
        or manifest_kind(path)
    )


def evidence_priority(relative):
    path = Path(relative)
    return (not ancestor_marker(path), len(path.parts), relative)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="project directory")
    parser.add_argument("--target", help="scope within the project, relative to its root or absolute")
    args = parser.parse_args(argv)
    try:
        root, scope = project_scope(args.project, args.target)
    except ValueError as error:
        parser.error(str(error))
    except (OSError, RuntimeError):
        parser.error("the project or target cannot be accessed")
    detection = Detection(root, scope)
    detection.scan()
    print(json.dumps(detection.result(), ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
