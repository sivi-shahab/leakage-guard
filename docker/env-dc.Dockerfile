# Environment: deepchecks + ppscore + builtin (pins SPEC 3.3). Build from repo root of leakage-guard:
#   docker build -f docker/env-dc.Dockerfile -t leakage-guard-dc .
# Run with no network:  docker run --rm --network none -v $PWD/work:/work leakage-guard-dc run --config /work/guard.yaml --out /work/out
FROM python:3.11-slim AS build
RUN pip install --no-cache-dir uv==0.5.* && uv venv /opt/venv
COPY locks/dc.lock /tmp/dc.lock
RUN uv pip install --python /opt/venv/bin/python --require-hashes --no-deps -r /tmp/dc.lock
COPY pyproject.toml README.md /src/
COPY src /src/src
RUN uv pip install --python /opt/venv/bin/python --no-deps /src

FROM python:3.11-slim
COPY --from=build /opt/venv /opt/venv
RUN useradd --create-home --uid 10001 guard && mkdir /work && chown guard /work
USER guard
WORKDIR /work
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["leakage-guard"]
