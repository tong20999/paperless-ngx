"""Run with Python on a machine with Docker Compose. No Docker daemon is needed."""

import json
import os
import subprocess
import unittest
from pathlib import Path


class TestTrueNASConfig(unittest.TestCase):
    def compose_config(self, *files, **env):
        command = ["docker", "compose"]
        for file in files:
            command.extend(["-f", file])
        return subprocess.run(
            [*command, "config", "--format", "json", "--no-path-resolution"],
            capture_output=True,
            cwd=Path(__file__).resolve().parents[2],
            env={
                **os.environ,
                "PAPERLESS_URL": "http://localhost:8000",
                "PAPERLESS_SECRET_KEY": "test-only",
                "PAPERLESS_DBPASS": "test-only",
                "PAPERLESS_ADMIN_PASSWORD": "test-only",
                **env,
            },
            text=True,
        )

    def test_nas_binds_replace_document_mounts(self):
        root = "/mnt/y/paperless"
        default = self.compose_config("compose.yaml", PAPERLESS_NAS_ROOT="")
        self.assertEqual(default.returncode, 0, default.stderr)
        override = self.compose_config(
            "compose.yaml",
            "compose.truenas.yaml",
            PAPERLESS_NAS_ROOT=root,
            USERMAP_UID="1350",
            USERMAP_GID="1351",
        )
        self.assertEqual(override.returncode, 0, override.stderr)
        default_services = json.loads(default.stdout)["services"]
        services = json.loads(override.stdout)["services"]
        self.assertEqual(services["db"]["volumes"], default_services["db"]["volumes"])
        self.assertEqual(
            services["broker"]["volumes"], default_services["broker"]["volumes"]
        )

        webserver = services["webserver"]
        environment = webserver["environment"]
        self.assertEqual(environment["PAPERLESS_CONSUMER_POLLING_INTERVAL"], "10")
        self.assertEqual(environment["USERMAP_UID"], "1350")
        self.assertEqual(environment["USERMAP_GID"], "1351")
        mounts = {mount["target"]: mount for mount in webserver["volumes"]}
        self.assertEqual(len(webserver["volumes"]), 4)
        self.assertEqual(mounts["/usr/src/paperless/data"]["source"], "data")
        for name in ("media", "consume", "export"):
            with self.subTest(directory=name):
                mount = mounts[f"/usr/src/paperless/{name}"]
                self.assertEqual(mount["type"], "bind")
                self.assertEqual(mount["source"], f"{root}/{name}")
                self.assertIs(mount["bind"]["create_host_path"], False)

    def test_nas_override_requires_a_root(self):
        result = self.compose_config(
            "compose.yaml", "compose.truenas.yaml", PAPERLESS_NAS_ROOT=""
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set PAPERLESS_NAS_ROOT", result.stderr)


if __name__ == "__main__":
    unittest.main()
