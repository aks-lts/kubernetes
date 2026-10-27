# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import unittest
from unittest.mock import patch

import verify_ca_certificates as audit


class TrustPathTests(unittest.TestCase):
    def test_regular_file(self):
        self.assertEqual(audit.resolve("a", {"a": ("file", b"CA")}), b"CA")

    def test_absolute_link(self):
        entries = {"a": ("link", "/etc/root.pem"), "etc/root.pem": ("file", b"CA")}
        self.assertEqual(audit.resolve("a", entries), b"CA")

    def test_relative_link(self):
        entries = {"etc/certs/a": ("link", "../root.pem"),
                   "etc/root.pem": ("file", b"CA")}
        self.assertEqual(audit.resolve("etc/certs/a", entries), b"CA")

    def test_dangling_link(self):
        with self.assertRaisesRegex(ValueError, "dangling"):
            audit.resolve("a", {"a": ("link", "missing")})

    def test_link_cycle(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            audit.resolve("a", {"a": ("link", "b"), "b": ("link", "a")})

    def test_malformed_pem_is_rejected(self):
        with self.assertRaises(ValueError):
            audit.fingerprints(b"-----BEGIN CERTIFICATE-----!-----END CERTIFICATE-----")


class ImageConfigurationTests(unittest.TestCase):
    def check_rejected(self, config, platform, message):
        with patch.object(audit.subprocess, "check_output",
                          return_value=json.dumps([config])) as command:
            with self.assertRaisesRegex(ValueError, message):
                audit.verify("test-image", platform)
            self.assertEqual(command.call_count, 1)

    def test_wrong_platform_is_rejected(self):
        self.check_rejected({"Os": "linux", "Architecture": "amd64"},
                            "linux/arm64", "platform")

    def test_wrong_arm_variant_is_rejected(self):
        self.check_rejected({"Os": "linux", "Architecture": "arm", "Variant": "v6"},
                            "linux/arm/v7", "platform")

    def test_custom_certificate_file_is_rejected(self):
        self.check_rejected({"Os": "linux", "Architecture": "arm64",
                             "Config": {"Env": ["SSL_CERT_FILE=/custom.pem"]}},
                            "linux/arm64", "SSL_CERT_FILE")

    def test_custom_certificate_directory_is_rejected(self):
        self.check_rejected({"Os": "linux", "Architecture": "arm64",
                             "Config": {"Env": ["SSL_CERT_DIR=/custom"]}},
                            "linux/arm64", "SSL_CERT_DIR")


if __name__ == "__main__":
    unittest.main()
