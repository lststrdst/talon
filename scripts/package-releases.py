"""Build the web and Agent Plugins archives from the Talon sources."""

import json
from pathlib import Path
import posixpath
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/talon"
PORTABLE = ROOT / "portable"
SKILL_ROOT = "skills/talon/"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
HARNESS_SKILLS = ("harness-hermes", "harness-opencode", "harness-openclaw", "harness-pi", "harness-deepseek")


def write_zip(path, entries):
    for name, content in entries.items():
        if not name.endswith(".md"):
            continue
        for link in re.findall(r"\]\(([^\s)]+)\)", content.decode("utf-8")):
            if link.startswith(("#", "mailto:")) or "://" in link:
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), link.split("#")[0]))
            if target not in entries:
                raise ValueError(f"Missing archive resource referenced by {name}: {link}")

    with ZipFile(path, "w") as archive:
        for name, content in sorted(entries.items()):
            member = ZipInfo(name)
            member.external_attr = 0o100644 << 16
            archive.writestr(member, content, compress_type=ZIP_DEFLATED, compresslevel=9)

    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"Invalid archive: {path}")
    print(f"{path.relative_to(ROOT)} ({len(entries)} files)")


def build_web():
    manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    capabilities = manifest["interface"]["capabilities"]
    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
        raise ValueError("interface.capabilities must be a list of strings")

    entries = {".codex-plugin/plugin.json": (PLUGIN / ".codex-plugin/plugin.json").read_bytes()}
    for directory in ("skills", "assets"):
        for path in (PLUGIN / directory).rglob("*"):
            relative = path.relative_to(PLUGIN)
            if path.is_file() and not any(part.startswith((".", "__")) for part in relative.parts):
                entries[relative.as_posix()] = path.read_bytes()
    return manifest, entries


def build_portable(web_manifest, web_entries):
    entries = {
        "README.md": (PORTABLE / "README.md").read_bytes(),
        "PROJECT-RULES.md": (PORTABLE / "PROJECT-RULES.md").read_bytes(),
        SKILL_ROOT + "SKILL.md": (PORTABLE / "talon/SKILL.md").read_bytes(),
        SKILL_ROOT + "references/agent-roles.md": (PORTABLE / "talon/references/agent-roles.md").read_bytes(),
    }
    manifest = {
        "$schema": SCHEMA,
        "name": web_manifest["name"],
        "version": web_manifest["version"],
        "description": "Разработка, Python, PowerShell, серверы, QA и память проекта",
        "author": web_manifest["author"],
        "repository": web_manifest["interface"]["websiteURL"],
    }
    entries["plugin.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    sources = {
        "feature-work.md": "build/references/feature-work.md",
        "powershell.md": "build/references/powershell.md",
        "python-scripts.md": "build/references/python-scripts.md",
        "remote-ssh.md": "build/references/remote-ssh.md",
        "windows-server.md": "build/references/windows-server.md",
        "linux-server.md": "build/references/linux-server.md",
        "graphify.md": "build/references/graphify.md",
        "failure-testing.md": "qa/references/failure-testing.md",
        "project-memory.md": "go/references/project-memory.md",
        "harness-routing.md": "go/references/harness-routing.md",
    }
    entries[SKILL_ROOT + "scripts/verify.py"] = (PLUGIN / "skills/build/scripts/verify.py").read_bytes()
    for filename, source in sources.items():
        content = (PLUGIN / "skills" / source).read_text(encoding="utf-8")
        content = content.replace("../../qa/references/failure-testing.md", "failure-testing.md")
        content = content.replace("../../qa/SKILL.md", "failure-testing.md")
        entries[SKILL_ROOT + "references/" + filename] = content.encode("utf-8")
    for name in HARNESS_SKILLS:
        entries[f"skills/{name}/SKILL.md"] = (PLUGIN / "skills" / name / "SKILL.md").read_bytes()
    for name, content in web_entries.items():
        if name.startswith(("skills/stack/", "skills/checks/", "skills/directory/", "skills/delivery/")) and "/agents/" not in name:
            entries[name] = content
    return entries


def main():
    manifest, web = build_web()
    version = manifest["version"]
    releases = ROOT / "releases"
    write_zip(releases / f"Talon-{version}-web.zip", web)
    write_zip(releases / f"Talon-{version}-agents.zip", build_portable(manifest, web))


if __name__ == "__main__":
    main()
