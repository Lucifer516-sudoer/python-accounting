# syntax=docker/dockerfile:1

# python-accounting is a library, so this image is not a service: the `smoke`
# target installs the built wheel into a clean interpreter and exercises it the
# way an end user would (relevant because config.toml is resolved from the root
# of site-packages), and the `drivers` target adds the optional MySQL/Postgres
# extras so docker-compose can run the same round-trip against real servers.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

WORKDIR /src
# Only the files the wheel build reads: hatchling packages python_accounting/
# and force-includes config.toml at the wheel root (see pyproject.toml).
COPY pyproject.toml README.md LICENSE config.toml ./
COPY python_accounting ./python_accounting

RUN uv build --wheel --out-dir /dist

FROM python:${PYTHON_VERSION}-slim AS smoke
RUN useradd --create-home --uid 10001 app
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl
COPY --chown=app:app scripts/smoke_install.py /home/app/smoke_install.py

USER app
WORKDIR /home/app

CMD ["python", "smoke_install.py"]

FROM smoke AS drivers
# mysqlclient and psycopg2 compile against system headers. The toolchain stays
# in the image because this target exists to run tests, not to be minimal.
USER root
COPY --from=builder /dist /dist
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    libpq-dev \
    pkg-config; \
    rm -rf /var/lib/apt/lists/*; \
    cp /dist/*.whl /tmp/pkg.whl; \
    pip install --no-cache-dir "/tmp/pkg.whl[mysql,postgres]"

USER app
