FROM python:3.11-slim

WORKDIR /app
COPY app.py /app/app.py
COPY templates /app/templates
COPY requirements.txt /app/requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends iw \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 18080
CMD ["python", "app.py"]
