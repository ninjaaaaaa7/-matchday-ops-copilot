# Container image for deploying MatchDay Ops Copilot on Hugging Face Spaces.
# Hugging Face routes external traffic to port 7860 by default.

FROM python:3.12-slim

# Keep Python output unbuffered so logs appear in real time.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached between rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY . .

# Hugging Face Spaces expects the app to listen on 7860.
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
