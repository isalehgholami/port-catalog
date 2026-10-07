FROM python:3.12-slim
LABEL org.opencontainers.image.title="port-catalog" \
      org.opencontainers.image.description="Read-only catalog of listening and Docker-published ports" \
      org.opencontainers.image.licenses="MIT"
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
ENV PORTCATALOG_BIND=0.0.0.0 PORTCATALOG_PORT=9780
EXPOSE 9780
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.environ.get('PORTCATALOG_PORT','9780'),timeout=2)" || exit 1
CMD ["python", "-m", "app.main"]
