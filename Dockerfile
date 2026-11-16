FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY integracao/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home panel
COPY --chown=panel:panel integracao /app/integracao
COPY --chown=panel:panel fabrica /app/fabrica
USER panel
EXPOSE 8080
CMD ["python", "integracao/server.py"]
