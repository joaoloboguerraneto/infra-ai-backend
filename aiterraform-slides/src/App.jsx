import { useState } from "react";

const SLIDES = [
  { id: "objetivo",   icon: "◈", label: "Objetivo" },
  { id: "llm",        icon: "⬡", label: "O que é LLM" },
  { id: "modelo",     icon: "◎", label: "Modelo" },
  { id: "arquitetura",icon: "☸", label: "Arquitetura" },
  { id: "infra",      icon: "▣", label: "Infra K8s" },
  { id: "repositorio",icon: "⌥", label: "Repositório" },
  { id: "demo",       icon: "→", label: "Demo" },
];

const Tag = ({ children, color = "#00ff88" }) => (
  <span style={{
    background: color + "18", border: `1px solid ${color}44`, color,
    borderRadius: 4, padding: "2px 8px", fontSize: 10,
    fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.05em",
  }}>{children}</span>
);

const Code = ({ children }) => (
  <code style={{ fontFamily: "monospace", fontSize: 12, color: "#00ff88", background: "#0a0a0a", padding: "1px 6px", borderRadius: 4 }}>
    {children}
  </code>
);

const Block = ({ title, children, color = "#1e1e1e", accent }) => (
  <div style={{
    background: "#0d0d0d", border: `1px solid ${accent || color}`,
    borderRadius: 10, padding: "16px 18px", marginBottom: 12,
  }}>
    {title && <div style={{ fontSize: 10, color: accent || "#555", fontFamily: "monospace", letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: 8 }}>{title}</div>}
    {children}
  </div>
);

// ─── SLIDES ────────────────────────────────────────────────────────────────

function ObjetivoSlide() {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#00ff88", fontFamily: "monospace", letterSpacing: "0.2em", marginBottom: 6 }}>VISÃO GERAL DO PROJETO</div>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 8, lineHeight: 1.1 }}>
        aiterraform — infraestrutura por linguagem natural
      </h2>
      <p style={{ fontSize: 14, color: "#777", marginBottom: 24, lineHeight: 1.7, maxWidth: 580 }}>
        Uma IA local rodando dentro do Kubernetes que permite criar, atualizar e destruir
        recursos na AWS e repositórios no Azure DevOps simplesmente descrevendo o que você precisa — sem escrever código Terraform.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        {[
          { icon: "🚫", title: "Problema atual", items: ["Dev precisa saber HCL/Terraform", "Configuração manual e propensa a erro", "Inconsistência entre projetos", "Tempo alto para criar infra básica"] },
          { icon: "✦", title: "Com aiterraform", items: ["Linguagem natural → recurso criado", "Templates validados — zero erro de sintaxe", "Padrões da Unicred garantidos em 100% dos recursos", "Infra provisionada em minutos"] },
        ].map(b => (
          <div key={b.title} style={{ background: "#0d0d0d", border: "1px solid #1e1e1e", borderRadius: 10, padding: "16px 18px" }}>
            <div style={{ fontSize: 20, marginBottom: 8 }}>{b.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: b.icon === "🚫" ? "#ff6666" : "#00ff88", marginBottom: 10 }}>{b.title}</div>
            {b.items.map(i => (
              <div key={i} style={{ fontSize: 12, color: "#666", marginBottom: 5, display: "flex", gap: 8 }}>
                <span style={{ color: b.icon === "🚫" ? "#ff4444" : "#00ff88" }}>{b.icon === "🚫" ? "✗" : "✓"}</span>{i}
              </div>
            ))}
          </div>
        ))}
      </div>

      <Block title="Recursos suportados nesta POC" accent="#00ccff40">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[["S3 Bucket", "#00ff88"], ["Lambda Function", "#00ff88"], ["SQS Queue + DLQ", "#00ff88"], ["Azure DevOps Repo", "#00ccff"], ["Fluxo de aprovação", "#9b88ff"]].map(([l, c]) => (
            <Tag key={l} color={c}>{l}</Tag>
          ))}
        </div>
      </Block>
    </div>
  );
}

function LLMSlide() {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#ffaa00", fontFamily: "monospace", letterSpacing: "0.2em", marginBottom: 6 }}>CONCEITO FUNDAMENTAL</div>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 8 }}>O que é um LLM?</h2>
      <p style={{ fontSize: 14, color: "#777", marginBottom: 20, lineHeight: 1.7, maxWidth: 580 }}>
        LLM = <strong style={{ color: "#ccc" }}>Large Language Model</strong>. Um modelo de IA treinado em bilhões de textos que aprende padrões de linguagem e consegue gerar texto coerente a partir de um prompt.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 20 }}>
        {[
          { label: "Treinamento", icon: "📚", desc: "Lê bilhões de documentos e aprende padrões estatísticos de linguagem" },
          { label: "Inferência", icon: "⚡", desc: "Dado um prompt, prediz o próximo token mais provável em sequência" },
          { label: "Fine-tuning", icon: "🎯", desc: "Especialização para domínios específicos como código, medicina, direito" },
        ].map(b => (
          <div key={b.label} style={{ background: "#0d0d0d", border: "1px solid #1e1e1e", borderRadius: 8, padding: "14px" }}>
            <div style={{ fontSize: 20, marginBottom: 6 }}>{b.icon}</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#ffaa00", marginBottom: 6 }}>{b.label}</div>
            <div style={{ fontSize: 11, color: "#555", lineHeight: 1.5 }}>{b.desc}</div>
          </div>
        ))}
      </div>

      <Block title="Por que LLM local (on-premise)?" accent="#00ff8840">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: "#00ff88", fontFamily: "monospace", marginBottom: 8 }}>VANTAGENS</div>
            {["Dados nunca saem da rede da Unicred", "Zero custo por token (sem API externa)", "Funciona em rede isolada / air-gap", "Controle total sobre o modelo e versão", "Sem dependência de fornecedores externos"].map(v => (
              <div key={v} style={{ fontSize: 12, color: "#5a8a5a", marginBottom: 5 }}>✓ {v}</div>
            ))}
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#ffaa00", fontFamily: "monospace", marginBottom: 8 }}>VS API EXTERNA (OpenAI, Claude)</div>
            {["Dados enviados para servidores externos", "Custo por token — escala mal com volume", "Dependência de SLA de terceiros", "Requer internet — indisponível offline", "Sujeito a mudanças de preço/política"].map(v => (
              <div key={v} style={{ fontSize: 12, color: "#886644", marginBottom: 5 }}>✗ {v}</div>
            ))}
          </div>
        </div>
      </Block>

      <Block accent="#9b88ff40">
        <div style={{ fontSize: 13, color: "#9b88ff", lineHeight: 1.6 }}>
          <strong style={{ color: "#ccc" }}>No aiterraform:</strong> o LLM não gera o Terraform diretamente. Ele só extrai a <em>intenção</em> do prompt — tipo de recurso e parâmetros. O HCL correto vem de templates Python pré-validados. Isso garante código correto independente do modelo.
        </div>
      </Block>
    </div>
  );
}

function ModeloSlide() {
  const [sel, setSel] = useState(0);
  const modelos = [
    {
      nome: "llama3.2:3b", org: "Meta", tag: "POC — CPU-friendly",
      tagColor: "#00ff88", ram: "2 GB", gpu: "Recomendado", cpu: "OK (~30s/resp)",
      desc: "Modelo compacto da Meta. Ideal para POC sem GPU — roda em qualquer máquina com 4 GB de RAM. Bom para extração de intenção (a tarefa real no aiterraform).",
      pull: "ollama pull llama3.2:3b",
    },
    {
      nome: "codellama:7b", org: "Meta", tag: "Código",
      tagColor: "#00ccff", ram: "4.7 GB", gpu: "Recomendado", cpu: "Lento (~90s)",
      desc: "Especializado em código. Treinado especificamente em repositórios de código e HCL. Gera melhor estrutura lógica mas requer mais RAM.",
      pull: "ollama pull codellama:7b",
    },
    {
      nome: "codellama:13b", org: "Meta", tag: "Melhor qualidade",
      tagColor: "#9b88ff", ram: "8 GB", gpu: "Necessário", cpu: "Inviável",
      desc: "Versão maior do CodeLlama. Excelente qualidade de código e HCL. Recomendado para ambiente de produção com GPU NVIDIA disponível.",
      pull: "ollama pull codellama:13b",
    },
    {
      nome: "deepseek-coder-v2", org: "DeepSeek", tag: "Estado da arte",
      tagColor: "#ffaa00", ram: "13 GB", gpu: "Obrigatório", cpu: "Inviável",
      desc: "Melhor modelo open source para geração de código em 2024. Supera GPT-4 em benchmarks de código. Para clusters com GPU dedicada.",
      pull: "ollama pull deepseek-coder-v2",
    },
  ];
  const m = modelos[sel];

  return (
    <div>
      <div style={{ fontSize: 10, color: "#9b88ff", fontFamily: "monospace", letterSpacing: "0.2em", marginBottom: 6 }}>MODELOS DISPONÍVEIS</div>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 8 }}>Qual modelo usar?</h2>
      <p style={{ fontSize: 14, color: "#777", marginBottom: 16, lineHeight: 1.7 }}>
        O Ollama gerencia os modelos como o Docker gerencia containers — pull, run, list. Qualquer modelo HuggingFace compatível pode ser carregado.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
        {modelos.map((mod, i) => (
          <button key={mod.nome} onClick={() => setSel(i)} style={{
            background: sel === i ? "#151515" : "#0a0a0a",
            border: sel === i ? `1px solid ${mod.tagColor}50` : "1px solid #1a1a1a",
            borderRadius: 8, padding: "10px 14px", cursor: "pointer", textAlign: "left",
            display: "flex", alignItems: "center", gap: 12, transition: "all 0.15s",
          }}>
            <div style={{ flex: 1, fontFamily: "monospace", fontSize: 13, fontWeight: 700, color: sel === i ? "#fff" : "#666" }}>{mod.nome}</div>
            <Tag color={mod.tagColor}>{mod.tag}</Tag>
            <div style={{ fontSize: 11, color: "#444", fontFamily: "monospace" }}>{mod.ram}</div>
          </button>
        ))}
      </div>

      <Block accent={m.tagColor + "30"}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 12 }}>
          {[["Organização", m.org], ["RAM", m.ram], ["CPU-only", m.cpu]].map(([k, v]) => (
            <div key={k} style={{ background: "#080808", borderRadius: 6, padding: "8px 10px" }}>
              <div style={{ fontSize: 10, color: "#333", fontFamily: "monospace", marginBottom: 3 }}>{k}</div>
              <div style={{ fontSize: 12, color: "#ccc" }}>{v}</div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 12, color: "#777", lineHeight: 1.6, marginBottom: 10 }}>{m.desc}</p>
        <div style={{ background: "#080808", borderRadius: 6, padding: "8px 12px", fontFamily: "monospace", fontSize: 12, color: "#00ff88" }}>
          <span style={{ color: "#333" }}>$ </span>{m.pull}
        </div>
      </Block>

      <div style={{ background: "#0a1218", border: "1px solid #00ccff25", borderRadius: 8, padding: "12px 14px", fontSize: 12, color: "#5588aa", lineHeight: 1.6, display: "flex", gap: 10 }}>
        <span>💡</span>
        <span><strong style={{ color: "#ccc" }}>Na POC atual usamos llama3.2:3b.</strong> O modelo só precisa entender o pedido e extrair <Code>type + params</Code> — uma tarefa simples. O HCL é gerado pelos templates Python, não pelo modelo.</span>
      </div>
    </div>
  );
}

function ArquiteturaSlide() {
  const flow = [
    { icon: "👤", label: "Usuário", sub: "digita em linguagem natural", color: "#888" },
    { icon: "⚛", label: "Frontend\nnginx/K8s", sub: "POST /generate SSE", color: "#00ccff" },
    { icon: "🐍", label: "Backend\nFastAPI", sub: "orquestra tudo", color: "#3a86ff" },
    { icon: "🌿", label: "Ollama\nService", sub: "extrai type+params", color: "#00ff88" },
    { icon: "📦", label: "Template\nPython", sub: "gera HCL correto", color: "#9b88ff" },
    { icon: "☁", label: "AWS / Azure\nDevOps", sub: "recurso criado", color: "#ffaa00" },
  ];

  return (
    <div>
      <div style={{ fontSize: 10, color: "#3a86ff", fontFamily: "monospace", letterSpacing: "0.2em", marginBottom: 6 }}>COMO TUDO SE CONECTA</div>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 8 }}>Arquitetura da solução</h2>

      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 20, flexWrap: "wrap" }}>
        {flow.map((f, i) => (
          <>
            <div key={f.label} style={{ flex: 1, minWidth: 90, background: "#0d0d0d", border: `1px solid ${f.color}30`, borderRadius: 8, padding: "12px 8px", textAlign: "center" }}>
              <div style={{ fontSize: 20, marginBottom: 4 }}>{f.icon}</div>
              <div style={{ fontSize: 11, fontWeight: 700, color: f.color, whiteSpace: "pre-line", lineHeight: 1.3, marginBottom: 3 }}>{f.label}</div>
              <div style={{ fontSize: 10, color: "#444", lineHeight: 1.3 }}>{f.sub}</div>
            </div>
            {i < flow.length - 1 && <div key={"a"+i} style={{ color: "#222", fontSize: 16, flexShrink: 0 }}>›</div>}
          </>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <Block title="Fluxo Terraform (AWS)" accent="#00ff8830">
          {["1. LLM extrai {type, params} do prompt", "2. Template Python gera HCL válido", "3. terraform init (provider do cache)", "4. terraform validate (garante HCL correto)", "5. terraform plan (mostra ao usuário)", "6. terraform apply → recurso criado na AWS", "7. State salvo no S3 (por tipo/nome)"].map((s, i) => (
            <div key={i} style={{ fontSize: 11, color: "#5a8a5a", marginBottom: 4, display: "flex", gap: 8 }}>
              <span style={{ color: "#00ff88", fontFamily: "monospace" }}>{i + 1}.</span>{s.slice(3)}
            </div>
          ))}
        </Block>
        <Block title="Fluxo Azure DevOps (Repositório)" accent="#00ccff30">
          {["1. LLM detecta intenção de criar repo", "2. Frontend pede e-mails inline", "3. Backend gera token de aprovação (TTL 30min)", "4. E-mail enviado ao arquiteto via SMTP/SES", "5. Arquiteto encaminha token ao solicitante", "6. Token validado → API Azure cria repositório", "7. E-mail de confirmação com URL do repo"].map((s, i) => (
            <div key={i} style={{ fontSize: 11, color: "#4a7a9a", marginBottom: 4, display: "flex", gap: 8 }}>
              <span style={{ color: "#00ccff", fontFamily: "monospace" }}>{i + 1}.</span>{s.slice(3)}
            </div>
          ))}
        </Block>
      </div>
    </div>
  );
}

function InfraSlide() {
  const [tab, setTab] = useState("cluster");
  const tabs = [
    { id: "cluster", label: "Cluster K8s" },
    { id: "pods", label: "Pods" },
    { id: "secrets", label: "Secrets" },
    { id: "state", label: "Terraform State" },
  ];

  const content = {
    cluster: (
      <div>
        <p style={{ fontSize: 13, color: "#777", marginBottom: 14, lineHeight: 1.6 }}>
          POC local usando <strong style={{ color: "#ccc" }}>kind</strong> (Kubernetes IN Docker) — cria um cluster completo dentro de containers Docker. Sem necessidade de VM ou cloud.
        </p>
        <div style={{ background: "#080808", border: "1px solid #1e1e1e", borderRadius: 8, padding: "14px 16px", fontFamily: "monospace", fontSize: 12, lineHeight: 1.8, color: "#c8c8c8", marginBottom: 12 }}>
          <div style={{ color: "#555" }}># Criar cluster</div>
          <div><span style={{ color: "#00ff88" }}>$</span> kind create cluster --name terraform-ai</div>
          <div style={{ marginTop: 8, color: "#555" }}># Ver tudo rodando</div>
          <div><span style={{ color: "#00ff88" }}>$</span> kubectl get pods -n ai-infra</div>
          <div style={{ color: "#555" }}># Expor localmente</div>
          <div><span style={{ color: "#00ff88" }}>$</span> make pf  <span style={{ color: "#555" }}># port-forwards dos 3 serviços</span></div>
        </div>
        <div style={{ fontSize: 12, color: "#555", fontStyle: "italic" }}>Para produção: EKS (AWS) ou cluster on-prem Unicred com as mesmas configurações.</div>
      </div>
    ),
    pods: (
      <div>
        {[
          { name: "ollama", img: "ollama/ollama:latest", port: "11434", desc: "Servidor LLM. Gerencia modelos como Docker gerencia imagens.", color: "#00ff88", pvc: "20 GB PVC" },
          { name: "terraform-ai-backend", img: "terraform-ai-backend:latest", port: "8080", desc: "FastAPI + Terraform CLI embutido. Orquestra LLM, templates e pipeline.", color: "#3a86ff", pvc: "—" },
          { name: "terraform-ai-frontend", img: "nginx:alpine", port: "80", desc: "Nginx servindo o HTML estático via ConfigMap. Zero build necessário.", color: "#9b88ff", pvc: "ConfigMap" },
        ].map(p => (
          <div key={p.name} style={{ background: "#0a0a0a", border: `1px solid ${p.color}25`, borderRadius: 8, padding: "12px 14px", marginBottom: 8, display: "flex", gap: 14 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "monospace", fontSize: 13, fontWeight: 700, color: p.color, marginBottom: 4 }}>{p.name}</div>
              <div style={{ fontSize: 11, color: "#555", marginBottom: 4 }}>{p.desc}</div>
              <div style={{ fontSize: 10, color: "#333", fontFamily: "monospace" }}>image: {p.img}</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end", flexShrink: 0 }}>
              <Tag color={p.color}>:{p.port}</Tag>
              {p.pvc !== "—" && <Tag color="#555">{p.pvc}</Tag>}
            </div>
          </div>
        ))}
      </div>
    ),
    secrets: (
      <div>
        <p style={{ fontSize: 13, color: "#777", marginBottom: 12, lineHeight: 1.6 }}>Credenciais nunca ficam em código — injetadas via Kubernetes Secrets no ambiente do pod.</p>
        {[
          { name: "aws-credentials", keys: ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"], color: "#ffaa00", note: "Para EKS prod: usar IRSA — sem chave" },
          { name: "azure-devops-credentials", keys: ["AZURE_DEVOPS_PAT"], color: "#00ccff", note: "PAT com scopes: Code R/W + Project Read" },
          { name: "email-credentials", keys: ["SMTP_USER", "SMTP_PASS"], color: "#9b88ff", note: "Gmail App Password ou Mailtrap para testes" },
        ].map(s => (
          <div key={s.name} style={{ background: "#0a0a0a", border: `1px solid ${s.color}25`, borderRadius: 8, padding: "12px 14px", marginBottom: 8 }}>
            <div style={{ fontFamily: "monospace", fontSize: 12, color: s.color, marginBottom: 6 }}>{s.name}</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
              {s.keys.map(k => <Tag key={k} color="#555">{k}</Tag>)}
            </div>
            <div style={{ fontSize: 11, color: "#444" }}>{s.note}</div>
          </div>
        ))}
      </div>
    ),
    state: (
      <div>
        <p style={{ fontSize: 13, color: "#777", marginBottom: 12, lineHeight: 1.6 }}>
          Estado do Terraform salvo no S3 com chave determinística — mesmo create e delete sempre encontram o mesmo state.
        </p>
        <div style={{ background: "#080808", border: "1px solid #1e1e1e", borderRadius: 8, padding: "14px 16px", fontFamily: "monospace", fontSize: 12, lineHeight: 1.9, color: "#c8c8c8", marginBottom: 12 }}>
          <div style={{ color: "#555" }}>s3://unicred-terraform-state-poc/</div>
          <div>poc/<span style={{ color: "#00ff88" }}>s3_bucket</span>/<span style={{ color: "#ffaa00" }}>unicred-poc</span>/terraform.tfstate</div>
          <div>poc/<span style={{ color: "#00ff88" }}>sqs_queue</span>/<span style={{ color: "#ffaa00" }}>eventos-pix</span>/terraform.tfstate</div>
          <div>poc/<span style={{ color: "#00ff88" }}>lambda_function</span>/<span style={{ color: "#ffaa00" }}>processador-ted</span>/terraform.tfstate</div>
        </div>
        <div style={{ background: "#0d0d0d", border: "1px solid #1e1e1e", borderRadius: 8, padding: "12px 14px", fontSize: 12, color: "#555" }}>
          <span style={{ color: "#ffaa00", fontWeight: 700 }}>DynamoDB</span> <Code>terraform-locks</Code> — impede dois applies simultâneos no mesmo recurso (state locking).
        </div>
      </div>
    ),
  };

  return (
    <div>
      <div style={{ fontSize: 10, color: "#ffaa00", fontFamily: "monospace", letterSpacing: "0.2em", marginBottom: 6 }}>KUBERNETES ON-PREM / KIND</div>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 16 }}>Infraestrutura do projeto</h2>

      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid #1e1e1e", marginBottom: 16 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            background: "none", border: "none",
            color: tab === t.id ? "#ffaa00" : "#555",
            fontFamily: "var(--font-sans, system-ui)", fontWeight: 700, fontSize: 12,
            padding: "8px 14px", cursor: "pointer",
            borderBottom: tab === t.id ? "2px solid #ffaa00" : "2px solid transparent",
            marginBottom: -1, transition: "all .15s",
          }}>{t.label}</button>
        ))}
      </div>
      {content[tab]}
    </div>
  );
}

function RepositorioSlide() {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#00ccff", fontFamily: "monospace", letterSpacing: "0.2em", marginBottom: 6 }}>GITHUB — joaoloboguerraneto/aiterraform</div>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 16 }}>Organização dos arquivos</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: "#00ff88", fontFamily: "monospace", letterSpacing: "0.1em", marginBottom: 10 }}>app/ — BACKEND PYTHON</div>
          {[
            ["main.py", "Rotas FastAPI + handler por tipo (SSE)"],
            ["extractor.py", "Chama o LLM → extrai {type, params}"],
            ["pipeline.py", "terraform init/validate/plan/apply/destroy"],
            ["routes_azure.py", "Endpoints /azure/* com fluxo de aprovação"],
            ["approvals.py", "Store de tokens com TTL em memória"],
            ["azure_devops.py", "Cliente REST API do Azure DevOps"],
            ["email_sender.py", "Envio via AWS SES ou SMTP"],
            ["templates/base.py", "Classe abstrata TerraformTemplate"],
            ["templates/s3.py", "HCL S3 + import_map para destroy"],
            ["templates/sqs.py", "HCL SQS + DLQ + import_map"],
            ["templates/lambda_.py", "HCL Lambda + IAM + CloudWatch"],
          ].map(([f, d]) => (
            <div key={f} style={{ display: "flex", gap: 10, marginBottom: 5, alignItems: "flex-start" }}>
              <code style={{ fontSize: 11, color: "#00ff88", fontFamily: "monospace", flexShrink: 0, minWidth: 160 }}>{f}</code>
              <div style={{ fontSize: 11, color: "#555", lineHeight: 1.4 }}>{d}</div>
            </div>
          ))}
        </div>

        <div>
          <div style={{ fontSize: 11, color: "#ffaa00", fontFamily: "monospace", letterSpacing: "0.1em", marginBottom: 10 }}>k8s/ — MANIFESTS KUBERNETES</div>
          {[
            ["00-namespace.yaml", "Namespace ai-infra"],
            ["01-ollama.yaml", "PVC + Deployment + Service do Ollama"],
            ["02-aws-secret.yaml.template", "Template do Secret AWS (não commitar com valores)"],
            ["03-backend.yaml", "Deployment com todas as env vars e secretKeyRef"],
            ["04-frontend.yaml", "nginx + ConfigMap placeholder"],
            ["05-azure-devops-secret.yaml.template", "Template PAT do Azure"],
            ["06-email-secret.yaml.template", "Template credenciais SMTP"],
          ].map(([f, d]) => (
            <div key={f} style={{ display: "flex", gap: 10, marginBottom: 5, alignItems: "flex-start" }}>
              <code style={{ fontSize: 11, color: "#ffaa00", fontFamily: "monospace", flexShrink: 0, minWidth: 160 }}>{f}</code>
              <div style={{ fontSize: 11, color: "#555", lineHeight: 1.4 }}>{d}</div>
            </div>
          ))}

          <div style={{ fontSize: 11, color: "#9b88ff", fontFamily: "monospace", letterSpacing: "0.1em", marginBottom: 10, marginTop: 16 }}>RAIZ DO PROJETO</div>
          {[
            ["Dockerfile", "Python 3.12-slim + Terraform 1.9.5 + provider AWS pré-baixado"],
            ["Makefile", "make deploy / make pf / make logs / make frontend"],
            ["providers.tf", "Usado no build para pre-baixar o provider AWS (sem download em runtime)"],
            ["requirements.txt", "fastapi · uvicorn · httpx · boto3 · email-validator"],
            ["frontend/index.html", "UI completa — infra AWS + fluxo Azure DevOps inline"],
          ].map(([f, d]) => (
            <div key={f} style={{ display: "flex", gap: 10, marginBottom: 5, alignItems: "flex-start" }}>
              <code style={{ fontSize: 11, color: "#9b88ff", fontFamily: "monospace", flexShrink: 0, minWidth: 160 }}>{f}</code>
              <div style={{ fontSize: 11, color: "#555", lineHeight: 1.4 }}>{d}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 14, background: "#0a1218", border: "1px solid #00ccff25", borderRadius: 8, padding: "12px 14px", fontSize: 12, color: "#5588aa", lineHeight: 1.6 }}>
        <strong style={{ color: "#ccc" }}>Adicionar novo recurso AWS</strong> = criar <Code>app/templates/rds.py</Code> herdando <Code>TerraformTemplate</Code> + uma linha de import em <Code>templates/__init__.py</Code>. O LLM, o pipeline e o Swagger reconhecem automaticamente.
      </div>
    </div>
  );
}

function DemoSlide() {
  const roteiro = [
    { num: "01", title: "Preparar o ambiente", color: "#555",
      cmds: ["make pf   # sobe os 3 port-forwards", "open http://localhost:3000"],
      note: "Mostrar kubectl get pods -n ai-infra — tudo Running no K8s" },
    { num: "02", title: "Criar bucket S3", color: "#00ff88",
      cmds: ["cria um bucket S3 chamado unicred-relatorios-poc na us-east-1"],
      note: "Clicar Ver Plan → mostrar HCL gerado → Aplicar → abrir console AWS ao vivo" },
    { num: "03", title: "Criar SQS com DLQ", color: "#00ff88",
      cmds: ["cria uma fila SQS chamada eventos-pix com dead letter queue"],
      note: "2 filas criadas automaticamente — eventos-pix + eventos-pix-dlq" },
    { num: "04", title: "Deletar recurso (import automático)", color: "#ffaa00",
      cmds: ["deletar a fila SQS eventos-pix com dead letter queue"],
      note: "Mostrar o import automático nos logs → destroy completo" },
    { num: "05", title: "Criar repositório Azure DevOps", color: "#00ccff",
      cmds: ["crie um repositorio test-ia-unicred"],
      note: "Preencher e-mails → e-mail chega ao arquiteto → colar token → repo criado no Azure" },
    { num: "06", title: "Mostrar a API (Swagger)", color: "#9b88ff",
      cmds: ["open http://localhost:8080/docs"],
      note: "Demonstrar /render direto sem LLM — integrável com qualquer sistema" },
  ];

  return (
    <div>
      <div style={{ fontSize: 10, color: "#9b88ff", fontFamily: "monospace", letterSpacing: "0.2em", marginBottom: 6 }}>ROTEIRO DA APRESENTAÇÃO</div>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 20 }}>Demo — passo a passo</h2>

      {roteiro.map(r => (
        <div key={r.num} style={{ display: "flex", gap: 14, marginBottom: 12, alignItems: "flex-start" }}>
          <div style={{ fontFamily: "monospace", fontSize: 11, color: r.color, fontWeight: 700, width: 28, flexShrink: 0, marginTop: 3 }}>{r.num}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#ddd", marginBottom: 6 }}>{r.title}</div>
            <div style={{ background: "#080808", border: "1px solid #1a1a1a", borderRadius: 6, padding: "8px 12px", marginBottom: 6 }}>
              {r.cmds.map((c, i) => (
                <div key={i} style={{ fontFamily: "monospace", fontSize: 11, color: c.startsWith("#") ? "#3a5a3a" : "#aaa", lineHeight: 1.7 }}>
                  {!c.startsWith("#") && <span style={{ color: r.color, marginRight: 6 }}>$</span>}{c}
                </div>
              ))}
            </div>
            <div style={{ fontSize: 11, color: "#555", fontStyle: "italic" }}>💡 {r.note}</div>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16, background: "#0a1a0a", border: "1px solid #00ff8830", borderRadius: 8, padding: "14px 16px", display: "flex", gap: 10 }}>
        <span>🎯</span>
        <div style={{ fontSize: 13, color: "#5a9a5a", lineHeight: 1.6 }}>
          <strong style={{ color: "#00ff88" }}>Ponto alto:</strong> mostrar o terminal com <Code>kubectl logs deploy/terraform-ai-backend -f</Code> em paralelo com o browser — o público vê o modelo processando, o Terraform rodando e o recurso aparecendo no console AWS em tempo real.
        </div>
      </div>
    </div>
  );
}

const COMPS = {
  objetivo: ObjetivoSlide, llm: LLMSlide, modelo: ModeloSlide,
  arquitetura: ArquiteturaSlide, infra: InfraSlide,
  repositorio: RepositorioSlide, demo: DemoSlide,
};

export default function App() {
  const [active, setActive] = useState("objetivo");
  const idx   = SLIDES.findIndex(s => s.id === active);
  const Slide = COMPS[active];

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;700;800&display=swap');
        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
        body{background:#070707;color:#e4e4e4;font-family:'Syne',sans-serif}
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:2px}
      `}</style>
      <div style={{ maxWidth: 920, margin: "0 auto", padding: "22px 18px", minHeight: "100vh", display: "flex", flexDirection: "column", gap: 18 }}>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 11, fontFamily: "monospace", color: "#2a2a2a", letterSpacing: "0.2em", marginBottom: 3 }}>UNICRED · PLATAFORMA DEVOPS</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em" }}>aiterraform — apresentação</div>
          </div>
          <div style={{ background: "#00ff8815", border: "1px solid #00ff8840", color: "#00ff88", fontFamily: "monospace", fontSize: 10, padding: "5px 12px", borderRadius: 4, letterSpacing: "0.08em" }}>
            LLM + K8s + TERRAFORM + AZURE
          </div>
        </div>

        <div style={{ display: "flex", gap: 4, background: "#0d0d0d", border: "1px solid #1a1a1a", borderRadius: 10, padding: 4, overflowX: "auto" }}>
          {SLIDES.map(s => (
            <button key={s.id} onClick={() => setActive(s.id)} style={{
              flex: "0 0 auto", background: active === s.id ? "#161616" : "none", border: "none",
              borderRadius: 7, padding: "9px 12px", cursor: "pointer", transition: "all .15s",
              display: "flex", flexDirection: "column", alignItems: "center", gap: 3,
            }}>
              <span style={{ fontSize: 14, color: active === s.id ? "#fff" : "#333" }}>{s.icon}</span>
              <span style={{ fontSize: 10, fontWeight: 700, color: active === s.id ? "#ddd" : "#333", letterSpacing: "0.02em", whiteSpace: "nowrap" }}>{s.label}</span>
            </button>
          ))}
        </div>

        <div style={{ flex: 1, background: "#0d0d0d", border: "1px solid #1a1a1a", borderRadius: 12, padding: "24px 26px", minHeight: 480, overflowY: "auto" }}>
          <Slide />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button onClick={() => setActive(SLIDES[idx - 1].id)} disabled={idx === 0}
            style={{ background: "#111", border: "1px solid #222", color: "#666", fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 12, padding: "9px 18px", borderRadius: 6, cursor: idx === 0 ? "default" : "pointer", opacity: idx === 0 ? 0.3 : 1 }}>
            ← Anterior
          </button>
          <span style={{ fontFamily: "monospace", fontSize: 11, color: "#2a2a2a" }}>{idx + 1} / {SLIDES.length}</span>
          <button onClick={() => setActive(SLIDES[idx + 1].id)} disabled={idx === SLIDES.length - 1}
            style={{ background: idx === SLIDES.length - 1 ? "#111" : "#00ff88", border: "none", color: idx === SLIDES.length - 1 ? "#666" : "#000", fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 12, padding: "9px 18px", borderRadius: 6, cursor: idx === SLIDES.length - 1 ? "default" : "pointer", opacity: idx === SLIDES.length - 1 ? 0.3 : 1 }}>
            Próximo →
          </button>
        </div>
      </div>
    </>
  );
}