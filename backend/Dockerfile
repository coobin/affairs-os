ARG PYTHON_BASE_IMAGE=python:3.13.3-slim
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.org/simple

USER root
RUN rm -rf /app/* \
    && (getent group app >/dev/null || addgroup --system app) \
    && (id app >/dev/null 2>&1 || adduser --system --ingroup app app)

COPY requirements.txt .
RUN pip install --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh && chown -R app:app /app

USER app
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
