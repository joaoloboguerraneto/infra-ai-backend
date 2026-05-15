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

# ── Provider AWS pre-baixado como filesystem mirror (read-only) ───────────
# Sem TF_PLUGIN_CACHE_DIR — evita conflito "text file busy" em runs paralelos.
# Cada workdir /tmp/tf-{uuid} copia o provider do mirror para seu proprio
# .terraform/providers/ — totalmente isolado.
COPY providers.tf /tmp/tf-warm/main.tf
RUN cd /tmp/tf-warm && terraform init && \
    terraform providers mirror /usr/local/terraform-providers && \
    rm -rf /tmp/tf-warm

# .terraformrc: usar SOMENTE o filesystem mirror, nunca baixar da internet
RUN printf 'provider_installation {\n\
  filesystem_mirror {\n\
    path    = "/usr/local/terraform-providers"\n\
    include = ["registry.terraform.io/*/*"]\n\
  }\n\
  direct {\n\
    exclude = ["registry.terraform.io/*/*"]\n\
  }\n\
}\n' > /root/.terraformrc

# ── App ───────────────────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--log-level", "warning", "--access-log"]