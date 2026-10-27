# Copyright 2018 The Kubernetes Authors.
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

ARG RUNNERIMAGE
FROM --platform=linux/amd64 mcr.microsoft.com/aks/devinfra/base-os-runtime-static:master.261022.1@sha256:e02b47e25b8436429ab911010459e80df6abf3b99a7dc5d115a1ac49462df0cd AS ca-bundle
FROM --platform=$BUILDPLATFORM docker.io/library/python:3.13.6-slim-bullseye@sha256:e98b521460ee75bca92175c16247bdf7275637a8faaeb2bcfa19d879ae5c4b9a AS runtime-ca
COPY --from=ca-bundle /etc/ssl/certs/ca-certificates.crt /trust/etc/ssl/certs/ca-certificates.crt
RUN python3 -c 'import hashlib, pathlib, re; root = pathlib.Path("/trust"); bundle = (root / "etc/ssl/certs/ca-certificates.crt").read_bytes(); assert hashlib.sha256(bundle).hexdigest() == "e9c7b63ee2623386e9b0a3ee32f499d01a8ea23dc83b8383ddff9f8e749543b7"; certs = re.findall(b"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", bundle, re.S); assert len(certs) == 148; [(root / "etc/ssl/certs" / ("%03d.pem" % n)).write_bytes(cert + b"\n") for n, cert in enumerate(certs)]' \
    && openssl rehash /trust/etc/ssl/certs
FROM docker.io/library/busybox:1.37.0-musl@sha256:5cec3fc171c87218698e85a52af7087de727372aae264a787b8112901a5b0092 AS ca-cleanup

FROM ${RUNNERIMAGE}
RUN --mount=type=bind,from=ca-cleanup,source=/bin/busybox,target=/busybox,ro \
    ["/busybox", "rm", "-rf", "/etc/ssl/certs", "/usr/share/ca-certificates", "/usr/local/share/ca-certificates", "/etc/pki/tls/certs", "/etc/ssl/cert.pem", "/etc/ssl/ca-bundle.pem", "/etc/pki/tls/cacert.pem", "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"]
COPY --from=runtime-ca /trust/etc/ssl/certs/ /etc/ssl/certs/

COPY cluster /kubernetes/cluster
COPY ginkgo /usr/local/bin/
COPY e2e.test /usr/local/bin/
COPY kubectl /usr/local/bin/
COPY gorunner /usr/local/bin/kubeconformance

# Legacy executables -- deprecated
COPY gorunner /run_e2e.sh
COPY gorunner /gorunner

ENV E2E_FOCUS="\[Conformance\]"
ENV E2E_SKIP=""
ENV E2E_PROVIDER="local"
ENV E2E_PARALLEL="1"
ENV E2E_VERBOSITY="4"
ENV RESULTS_DIR="/tmp/results"
ENV KUBECONFIG=""

ENTRYPOINT [ "kubeconformance" ]
