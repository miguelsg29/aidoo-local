# App (add-on) de Aidoo Local para Home Assistant.
# Instala el código desde el repo publicado (no se duplica aquí).
# Para producción, fija AIDOO_REF a un tag de release (p. ej. v0.1.1).
FROM alpine:3.20

ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache python3 py3-pip openssl jq curl git

ARG AIDOO_REF=v0.1.1
RUN git clone --depth 1 --branch ${AIDOO_REF} https://github.com/miguelsg29/aidoo-local /app \
    && pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
