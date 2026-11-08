# Environment: cleanlab[datalab]. Build from repo root of leakage-guard:
#   docker build -f docker/env-cl.Dockerfile -t leakage-guard-cl .
# Run with no network:  docker run --rm --network none -v $PWD/work:/work leakage-guard-cl run --config /work/guard.yaml --out /work/out
FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv==0.5.* && uv venv /opt/venv
COPY locks/cl.lock /tmp/cl.lock
RUN uv pip install --python /opt/venv/bin/python --require-hashes --no-deps -r /tmp/cl.lock
COPY pyproject.toml README.md /src/
COPY src /src/src
RUN uv pip install --python /opt/venv/bin/python --no-deps /src

FROM python:3.12-slim
COPY --from=build /opt/venv /opt/venv
RUN useradd --create-home --uid 10001 guard && mkdir /work && chown guard /work
USER guard
WORKDIR /work
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["leakage-guard"]
