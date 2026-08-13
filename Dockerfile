FROM mcr.microsoft.com/playwright/python:v1.61.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md setup.py ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

EXPOSE 8000

CMD ["sh", "-c", "real-estate-monitor report-portal --host 0.0.0.0 --port ${PORT:-8000}"]
