FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/models \
    XDG_CACHE_HOME=/opt/models

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 edlo \
    && mkdir -p /opt/models && chown edlo:edlo /opt/models

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[worker]"

USER edlo

# Bake the weights in. Adds ~550 MB, removes a 60-second cold start on every
# new task, and removes Hugging Face from the runtime dependency graph --
# their outage stops being our outage. A deliberate trade: image size for
# startup latency and availability.
RUN python -c "from faster_whisper import WhisperModel; \
               WhisperModel('small.en', device='cpu', compute_type='int8')"

COPY --chown=edlo:edlo edlo/ ./edlo/
COPY --chown=edlo:edlo apps/worker/ ./apps/worker/

CMD ["python", "-m", "apps.worker.main"]
