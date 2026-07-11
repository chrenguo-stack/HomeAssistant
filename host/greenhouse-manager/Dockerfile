FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system greenhouse \
    && useradd --system --gid greenhouse --create-home greenhouse \
    && mkdir -p /var/lib/greenhouse-manager \
    && chown greenhouse:greenhouse /var/lib/greenhouse-manager

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER greenhouse

ENTRYPOINT ["greenhouse-manager"]
