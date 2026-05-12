"""
Envio de e-mail via AWS SES (usa as credenciais AWS já no pod)
ou SMTP (configurado via variáveis de ambiente).
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ── Config via env ────────────────────────────────────────────────────────────
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "ses")   # "ses" ou "smtp"
EMAIL_FROM     = os.getenv("EMAIL_FROM", "noreply@unicred.com.br")

# SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

# AWS SES (usa as credenciais AWS já presentes no pod)
SES_REGION = os.getenv("SES_REGION", os.getenv("AWS_REGION", "us-east-1"))


def send_approval_email(
    to:          str,
    repo_name:   str,
    org:         str,
    project:     str,
    requester:   str,
    request_id:  str,
    token:       str,
    expires_min: int,
) -> None:
    """Envia e-mail de aprovação para o arquiteto."""

    subject = f"[Aprovação Necessária] Criar repositório '{repo_name}' no Azure DevOps"

    html = f"""\
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
  <div style="background:#0a0a0a;color:#e4e4e4;border-radius:10px;padding:28px">
    <h2 style="color:#00ff88;margin:0 0 8px">Solicitação de Aprovação</h2>
    <p style="color:#888;font-size:13px;margin:0 0 24px">aiterraform · Unicred DevOps</p>

    <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
      <tr><td style="color:#666;padding:6px 0;font-size:13px">Repositório</td>
          <td style="color:#fff;font-weight:700">{repo_name}</td></tr>
      <tr><td style="color:#666;padding:6px 0;font-size:13px">Organização</td>
          <td style="color:#ccc">{org}</td></tr>
      <tr><td style="color:#666;padding:6px 0;font-size:13px">Projeto</td>
          <td style="color:#ccc">{project}</td></tr>
      <tr><td style="color:#666;padding:6px 0;font-size:13px">Solicitado por</td>
          <td style="color:#ccc">{requester}</td></tr>
    </table>

    <p style="color:#888;font-size:12px;margin-bottom:12px">
      Encaminhe o token abaixo para o solicitante para que o repositório seja criado:
    </p>

    <div style="background:#111;border:1px solid #222;border-radius:8px;padding:16px;margin-bottom:20px">
      <div style="font-size:11px;color:#555;font-family:monospace;letter-spacing:0.1em;margin-bottom:6px">
        REQUEST ID
      </div>
      <div style="font-size:14px;color:#ffaa00;font-family:monospace;word-break:break-all">
        {request_id}
      </div>
      <div style="font-size:11px;color:#555;font-family:monospace;letter-spacing:0.1em;margin:12px 0 6px">
        TOKEN DE APROVAÇÃO
      </div>
      <div style="font-size:18px;color:#00ff88;font-family:monospace;font-weight:700;letter-spacing:0.1em;word-break:break-all">
        {token}
      </div>
    </div>

    <p style="color:#555;font-size:11px;font-family:monospace">
      ⏱ Este token expira em {expires_min} minutos.<br>
      Se você não reconhece esta solicitação, ignore este e-mail.
    </p>
  </div>
</body>
</html>"""

    text = (
        f"Solicitação de aprovação para criar repositório '{repo_name}'.\n\n"
        f"Organização: {org}\n"
        f"Projeto:     {project}\n"
        f"Solicitado:  {requester}\n\n"
        f"Encaminhe ao solicitante:\n"
        f"Request ID: {request_id}\n"
        f"Token:      {token}\n\n"
        f"Expira em {expires_min} minutos."
    )

    if EMAIL_PROVIDER == "ses":
        _send_via_ses(to, subject, html, text)
    else:
        _send_via_smtp(to, subject, html, text)


def send_confirmation_email(to: str, repo_name: str, org: str, project: str, url: str) -> None:
    """Notifica o solicitante que o repositório foi criado."""

    subject = f"[Concluído] Repositório '{repo_name}' criado no Azure DevOps"

    html = f"""\
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
  <div style="background:#0a0a0a;color:#e4e4e4;border-radius:10px;padding:28px">
    <h2 style="color:#00ff88;margin:0 0 8px">Repositório Criado</h2>
    <p style="color:#888;font-size:13px;margin:0 0 24px">aiterraform · Unicred DevOps</p>
    <p style="color:#ccc">O repositório <strong style="color:#fff">{repo_name}</strong>
    foi criado com sucesso em <strong>{org}/{project}</strong>.</p>
    <a href="{url}" style="display:inline-block;margin-top:20px;background:#00ff88;
    color:#000;font-weight:700;padding:10px 20px;border-radius:6px;text-decoration:none">
      Abrir repositório →
    </a>
  </div>
</body>
</html>"""

    text = f"Repositório '{repo_name}' criado em {org}/{project}.\nURL: {url}"

    if EMAIL_PROVIDER == "ses":
        _send_via_ses(to, subject, html, text)
    else:
        _send_via_smtp(to, subject, html, text)


def _send_via_ses(to: str, subject: str, html: str, text: str) -> None:
    import boto3
    client = boto3.client("ses", region_name=SES_REGION)
    client.send_email(
        Source=EMAIL_FROM,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text,  "Charset": "UTF-8"},
                "Html": {"Data": html,  "Charset": "UTF-8"},
            },
        },
    )
    print(f"[email] SES: enviado para {to}", flush=True)


def _send_via_smtp(to: str, subject: str, html: str, text: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, to, msg.as_string())

    print(f"[email] SMTP: enviado para {to}", flush=True)