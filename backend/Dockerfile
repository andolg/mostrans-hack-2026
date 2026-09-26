FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY ml_experiments/__init__.py ml_experiments/models.py ml_experiments/predict_saved.py /app/ml_experiments/

ENV PYTHONPATH=/app
CMD ["uvicorn", "backend.app.run:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
