IMAGE   := terraform-ai-backend
KIND    := terraform-ai
NS      := ai-infra

.PHONY: help build load deploy apply-k8s frontend restart logs pf clean

help:
	@echo ""
	@echo "  make build       — Build da imagem Docker"
	@echo "  make load        — Carrega imagem no cluster kind"
	@echo "  make deploy      — build + load + restart"
	@echo "  make apply-k8s   — kubectl apply em todos os manifests"
	@echo "  make frontend    — Atualiza ConfigMap do frontend"
	@echo "  make restart     — Reinicia os deployments"
	@echo "  make logs        — Logs do backend em tempo real"
	@echo "  make pf          — Sobe os 3 port-forwards"
	@echo "  make clean       — Remove todos os recursos do namespace"
	@echo ""

build:
	docker build -t $(IMAGE):latest .

load:
	kind load docker-image $(IMAGE):latest --name $(KIND)

deploy: build load
	kubectl rollout restart deployment/$(IMAGE) -n $(NS)
	kubectl rollout status  deployment/$(IMAGE) -n $(NS)

apply-k8s:
	@echo "Criando Secret AWS a partir de variaveis de ambiente..."
	@kubectl create secret generic aws-credentials \
		--namespace $(NS) \
		--from-literal=AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		--from-literal=AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
		--from-literal=AWS_DEFAULT_REGION=$(AWS_DEFAULT_REGION) \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -f k8s/00-namespace.yaml
	kubectl apply -f k8s/01-ollama.yaml
	kubectl apply -f k8s/03-backend.yaml
	kubectl apply -f k8s/04-frontend.yaml
	@$(MAKE) frontend

frontend:
	kubectl create configmap frontend-html \
		--from-file=index.html=frontend/index.html \
		--namespace $(NS) \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl rollout restart deployment/terraform-ai-frontend -n $(NS)

restart:
	kubectl rollout restart deployment/$(IMAGE) -n $(NS)
	kubectl rollout restart deployment/terraform-ai-frontend -n $(NS)
	kubectl rollout status  deployment/$(IMAGE) -n $(NS)

logs:
	kubectl logs -n $(NS) deploy/$(IMAGE) -f

pf:
	@echo "Subindo port-forwards (Ctrl+C para encerrar)..."
	@pkill -f "kubectl port-forward" 2>/dev/null || true
	@sleep 1
	kubectl port-forward -n $(NS) svc/terraform-ai-frontend 3000:80    &
	kubectl port-forward -n $(NS) svc/$(IMAGE)              8080:8080  &
	kubectl port-forward -n $(NS) svc/ollama                11434:11434 &
	@sleep 2
	@curl -s http://localhost:8080/health | python3 -m json.tool

pull-model:
	kubectl exec -n $(NS) deploy/ollama -- ollama pull llama3.2:3b

clean:
	kubectl delete namespace $(NS) --ignore-not-found