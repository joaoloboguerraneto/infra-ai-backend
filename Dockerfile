FROM python:3.12-slim

# ── Sistema + certificados CA ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip ca-certificates openssl git && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ── Terraform CLI ─────────────────────────────────────────────────────────
ARG TF_VERSION=1.9.5
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip" \
    -o /tmp/tf.zip && unzip /tmp/tf.zip -d /usr/local/bin/ && rm /tmp/tf.zip

# ── Provider AWS pre-baixado — zero download em runtime ──────────────────
ENV TF_PLUGIN_CACHE_DIR=/root/.terraform.d/plugin-cache
RUN mkdir -p /root/.terraform.d/plugin-cache

COPY providers.tf /tmp/tf-warm/main.tf
RUN cd /tmp/tf-warm && terraform init && \
    terraform providers mirror /usr/local/terraform-providers && \
    rm -rf /tmp/tf-warm

RUN printf 'provider_installation {\n  filesystem_mirror {\n    path    = "/usr/local/terraform-providers"\n    include = ["registry.terraform.io/*/*"]\n  }\n  direct {\n    exclude = ["registry.terraform.io/*/*"]\n  }\n}\n' > /root/.terraformrc

# ── App ───────────────────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# ── Uvicorn log level — silenciar health checks via filtro em main.py ────
ENV UVICORN_LOG_LEVEL=warning
ENV PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--log-level", "warning", "--access-log"]