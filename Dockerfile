FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YUNO_DATA_DIR=/data \
    YUNO_REQUIRE_PERSISTENT_VOLUME=1

WORKDIR /srv/yuno
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY deploy ./deploy

EXPOSE 8000
CMD ["python", "-m", "deploy.serve"]
