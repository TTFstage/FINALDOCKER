FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rdp_optimizer.py stream_manager.py worker_consumer.py ./

CMD ["python", "worker_consumer.py"]
