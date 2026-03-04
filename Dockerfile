FROM python:3.11-slim

WORKDIR /app
COPY app.py /app/app.py

RUN apt-get update && apt-get install -y --no-install-recommends iw \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask psutil

EXPOSE 18080
CMD ["python", "app.py"]
