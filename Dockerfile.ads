FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN chmod +x run_ads_lab.sh
CMD ["./run_ads_lab.sh"]
