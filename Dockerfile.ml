FROM python:3.12-slim

WORKDIR /app

COPY requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements-ml.txt

COPY . .

RUN chmod +x run_ml_demo.sh

CMD ["./run_ml_demo.sh"]
