# Imagen independiente de Aidoo Local, para ejecutar en CUALQUIER equipo con Docker
# (p. ej. si el 443 de tu Home Assistant ya lo usa Nginx Proxy Manager). Ver docker-compose.yml.
FROM python:3.12-alpine

RUN apk add --no-cache openssl
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY aidoo_local ./aidoo_local

ENV AIDOO_CERT=/data/cert.pem AIDOO_KEY=/data/key.pem AIDOO_PORT=443 PYTHONUNBUFFERED=1
VOLUME ["/data"]
CMD ["python", "-m", "aidoo_local"]
