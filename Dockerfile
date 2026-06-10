# THOR Enterprise — control-plane image (Manager :7100 · Dashboard :7080 · Sentinel :7140 ·
# Self-Audit :7150), run by tools/start_thor.py.
#
# The control plane provisions sealed Docker ROOMS on demand via the Docker SDK, so at run time it
# needs access to a Docker daemon (mount the host socket in compose, or a k8s-native provisioner —
# see DEPLOYMENT.md). Postgres is external (THOR_PG_DSN). Secrets (THOR_API_TOKEN, DB password) come
# from the environment / a secret store — never baked into the image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app

EXPOSE 7080 7100 7140 7150

# Liveness/readiness target for orchestrators: the Manager health endpoint.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7100/health',timeout=2).status==200 else 1)"

CMD ["python", "tools/start_thor.py"]
