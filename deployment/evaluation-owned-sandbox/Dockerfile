FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN useradd --create-home --uid 10001 sandbox

COPY app.py /app/app.py

USER sandbox

EXPOSE 8080

CMD ["python", "/app/app.py"]
