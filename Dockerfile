FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*

ARG TF_VERSION=1.9.5
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip" \
    -o /tmp/tf.zip && unzip /tmp/tf.zip -d /usr/local/bin/ && rm /tmp/tf.zip

# Criar mirror local do provider AWS — init funciona sem internet
COPY providers.tf /tmp/tf-warm/main.tf
RUN cd /tmp/tf-warm && terraform init && \
    terraform providers mirror /usr/local/terraform-providers && \
    rm -rf /tmp/tf-warm

# Configurar terraform para usar o mirror local em vez do registry
RUN cat > /root/.terraformrc << 'RCEOF'
provider_installation {
  filesystem_mirror {
    path    = "/usr/local/terraform-providers"
    include = ["registry.terraform.io/*/*"]
  }
  direct {
    exclude = ["registry.terraform.io/*/*"]
  }
}
RCEOF

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
