#!/usr/bin/env python3
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

"""Verify effective runtime CA files in a never-started container."""

import argparse
import base64
import hashlib
import json
import posixpath
import re
import subprocess
import tarfile
import tempfile


BUNDLE = "etc/ssl/certs/ca-certificates.crt"
BUNDLE_SHA256 = "e9c7b63ee2623386e9b0a3ee32f499d01a8ea23dc83b8383ddff9f8e749543b7"
FORBIDDEN = {
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b",
    "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4",
}
ISRG_ROOT_X1 = "96bcec06264976f37460779acf28c5a7cfe8a3c0aae11a8ffcee05c0bddf08c6"
TRUST_PATHS = (
    "etc/ssl/",
    "usr/share/ca-certificates/",
    "usr/local/share/ca-certificates/",
    "etc/pki/",
)
PEM = re.compile(b"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", re.S)


def fingerprints(data):
    return {
        hashlib.sha256(base64.b64decode(b"".join(pem.split()), validate=True)).hexdigest()
        for pem in PEM.findall(data)
    }


def resolve(path, entries):
    for _ in range(40):
        entry = entries.get(path)
        if entry is None:
            raise ValueError("Missing or dangling trust path: " + path)
        kind, value = entry
        if kind == "file":
            return value
        path = posixpath.normpath(
            value.lstrip("/") if value.startswith("/") else
            posixpath.join(posixpath.dirname(path), value)
        )
    raise ValueError("Trust link cycle: " + path)


def verify(image, platform):
    config = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", image], text=True
    ))[0]
    target = platform.split("/")
    actual = [config["Os"], config["Architecture"]]
    if len(target) == 3:
        actual.append(config.get("Variant", ""))
    if target != actual:
        raise ValueError("Image platform does not match " + platform)
    env = dict(item.split("=", 1) for item in config["Config"].get("Env") or [])
    if env.get("SSL_CERT_FILE", "/" + BUNDLE) != "/" + BUNDLE:
        raise ValueError("Custom SSL_CERT_FILE requires separate verification")
    if env.get("SSL_CERT_DIR", "/etc/ssl/certs") != "/etc/ssl/certs":
        raise ValueError("Custom SSL_CERT_DIR requires separate verification")
    container = subprocess.check_output(
        ["docker", "create", "--platform", platform, "--entrypoint",
         "/not-executed", image], text=True
    ).strip()
    try:
        with tempfile.TemporaryFile() as archive:
            subprocess.run(["docker", "export", container], stdout=archive, check=True)
            archive.seek(0)
            entries = {}
            with tarfile.open(fileobj=archive, mode="r|") as rootfs:
                for member in rootfs:
                    name = member.name.removeprefix("./").lstrip("/")
                    if name == "busybox":
                        raise ValueError("Build-only cleanup tool leaked into image")
                    if not name.startswith(TRUST_PATHS):
                        continue
                    if member.isfile():
                        entries[name] = ("file", rootfs.extractfile(member).read())
                    elif member.issym():
                        entries[name] = ("link", member.linkname)
                    elif member.islnk():
                        entries[name] = ("link", "/" + member.linkname)
            bundle = resolve(BUNDLE, entries)
            if hashlib.sha256(bundle).hexdigest() != BUNDLE_SHA256:
                raise ValueError("Unexpected CA bundle SHA256")
            roots = fingerprints(bundle)
            if len(roots) != 148 or ISRG_ROOT_X1 not in roots or roots & FORBIDDEN:
                raise ValueError("Unexpected runtime trust roots")
            for name in entries:
                certs = fingerprints(resolve(name, entries))
                if certs & FORBIDDEN or certs - roots:
                    raise ValueError("Stale or additional trusted certificate: " + name)
            return {"image": image, "platform": platform, "image_id": config["Id"],
                    "bundle_sha256": BUNDLE_SHA256, "roots": len(roots),
                    "verified_trust_paths": len(entries)}
    finally:
        subprocess.run(["docker", "rm", container], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True)
    parser.add_argument("images", nargs="+")
    args = parser.parse_args()
    for image in args.images:
        print(json.dumps(verify(image, args.platform), sort_keys=True))
