FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY proposal_qwilr/ proposal_qwilr/
COPY cli/ cli/
COPY api/ api/
COPY scripts/ scripts/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
