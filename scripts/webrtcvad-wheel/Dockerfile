FROM python:3.14-slim-trixie AS builder

ARG WEBRTCVAD_VERSION=2.0.14
ARG WEBRTCVAD_SDIST_SHA256=5f59c8e291c6ef102d9f39532982fbf26a52ce2de6328382e2654b0960fea397

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN printf 'webrtcvad-wheels==%s --hash=sha256:%s\n' \
        "${WEBRTCVAD_VERSION}" "${WEBRTCVAD_SDIST_SHA256}" > /tmp/requirements.txt \
    && mkdir -p /out \
    && python -m pip wheel \
        --no-cache-dir \
        --no-binary=webrtcvad-wheels \
        --no-deps \
        --require-hashes \
        --wheel-dir /out \
        --requirement /tmp/requirements.txt

RUN python - <<'PY'
from pathlib import Path
from zipfile import ZipFile

wheels = list(Path('/out').glob('webrtcvad_wheels-*.whl'))
if len(wheels) != 1:
    raise SystemExit(f'expected one wheel, found: {wheels}')

with ZipFile(wheels[0]) as archive:
    if 'webrtcvad.py' not in set(archive.namelist()):
        raise SystemExit(f'wheel has no webrtcvad.py: {wheels[0]}')

print(wheels[0].name)
PY

FROM scratch

COPY --from=builder /out/ /
