FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Only the runtime requirements: test and lint tools never enter the image. The ranker file holds
# LightGBM and NumPy, which the learned ranking and the model training need.
COPY requirements.txt requirements-ranker.txt ./
RUN pip install -r requirements.txt -r requirements-ranker.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"

# libgomp1 is the OpenMP runtime that LightGBM loads.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

# Mount point of the model volume. A new named volume copies the owner of this directory, so
# the unprivileged user can write the artifact there (the API mounts the volume read-only).
RUN mkdir -p /var/lib/ranker && chown app:app /var/lib/ranker

WORKDIR /srv
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

USER app
EXPOSE 8000
# The server access log would print raw paths and query strings; the application writes its own.
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-server-header"]
