FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY *.py .

# Cloud Run passes secrets via environment variables
# serviceAccount.json is mounted via Secret Manager at runtime
ENV FIREBASE_SERVICE_ACCOUNT=/secrets/serviceAccount.json

# Run all agents
CMD ["python", "run_all.py"]
