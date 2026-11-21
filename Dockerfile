FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python || true \
    && pip install --no-cache-dir --no-deps opencv-python-headless

COPY . .

CMD gunicorn e:app --bind 0.0.0.0:${PORT:-8000} --timeout 180 --workers 1
