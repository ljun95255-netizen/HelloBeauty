FROM node:20-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        git \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/HelloBeauty

COPY . .

RUN python3 -m venv .venv \
    && . .venv/bin/activate \
    && python -m pip install --upgrade pip \
    && python -m pip install -e .

RUN npm ci

CMD ["bash", "scripts/reproduce_core.sh"]
