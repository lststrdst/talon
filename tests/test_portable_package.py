import json
from pathlib import Path
import runpy
import unittest


class PortablePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        builder = runpy.run_path(str(root / "scripts/package-releases.py"))
        cls.web_manifest, cls.web = builder["build_web"]()
        cls.portable = builder["build_portable"](cls.web_manifest, cls.web)

    def test_claude_manifest_matches_portable_plugin_and_entry_skill(self):
        claude = json.loads(self.portable[".claude-plugin/plugin.json"])
        portable = json.loads(self.portable["plugin.json"])
        for key in ("name", "version", "author", "description"):
            self.assertEqual(claude[key], portable[key])
        self.assertEqual(claude["version"], self.web_manifest["version"])
        self.assertIn("skills/talon/SKILL.md", self.portable)

    def test_icons_resolve_in_both_packages(self):
        interface = self.web_manifest["interface"]
        image = self.web[interface["composerIcon"].removeprefix("./")]
        self.assertEqual(image, self.web[interface["logo"].removeprefix("./")])
        self.assertEqual(image, self.web["skills/go/assets/talon.png"])
        self.assertEqual(image, self.portable["assets/talon.png"])
        self.assertEqual(self.web["assets/talon.svg"], self.portable["assets/talon.svg"])
        self.assertIn(b'src="assets/talon.png"', self.portable["README.md"])
