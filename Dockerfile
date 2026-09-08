FROM python:3.12-slim

ARG GIT_SHA=unknown

ENV PYTHONUNBUFFERED=1 \ 
    PYTHONDONTWRITEBYTECODE=1 \ 
    PIP_NO_CACHE_DIR=1 \
    GIT_SHA=${GIT_SHA}

RUN useradd --create-home --uid 10001 edlo

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY --chown=edlo:edlo edlo/ ./edlo/ 
COPY --chown=edlo:edlo apps/api/ ./apps/api/

RUN mkdir -p /app/uploads && chown edlo:edlo /app/uploads

USER edlo 
EXPOSE 8000

CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]