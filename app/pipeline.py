import asyncio
import json
import os
import re
import shutil
import uuid
from pathlib import Path


class TerraformPipeline:
    def __init__(self, state_bucket: str, aws_region: str):
        self.state_bucket = state_bucket
        self.aws_region   = aws_region

    def _state_key(self, data: dict) -> str:
        """
        Chave determinística: poc/{tipo}/{nome}/terraform.tfstate

        Estrutura no S3:
          poc/
            s3_bucket/
              unicred-poc/terraform.tfstate
            sqs_queue/
              eventos-pix/terraform.tfstate
            lambda_function/
              processador-ted/terraform.tfstate

        Create e delete sempre usam a mesma chave — nunca perde o state.
        """
        resource_type = data.get("recurso", "unknown").lower().replace(" ", "_")

        # Nome vindo direto dos params (mais confiável que parsear HCL)
        params    = data.get("_params", {})
        nome      = params.get("nome") or params.get("function_name") or "default"
        nome_safe = re.sub(r'[^a-z0-9_-]', '-', nome.lower())

        return f"poc/{resource_type}/{nome_safe}/terraform.tfstate"

    def _backend_tf(self, region: str, state_key: str) -> str:
        has_creds = bool(os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_ROLE_ARN"))
        use_s3    = bool(self.state_bucket) and has_creds

        if use_s3:
            return (
                "terraform {\n"
                '  backend "s3" {\n'
                f'    bucket         = "{self.state_bucket}"\n'
                f'    key            = "{state_key}"\n'
                f'    region         = "{self.aws_region}"\n'
                '    dynamodb_table = "terraform-locks"\n'
                "    encrypt        = true\n"
                "  }\n"
                "  required_providers {\n"
                '    aws = { source = "hashicorp/aws", version = "~> 5.0" }\n'
                "  }\n"
                "}\n"
                f'provider "aws" {{ region = "{region}" }}\n'
            )
        return (
            "terraform {\n"
            "  required_providers {\n"
            '    aws = { source = "hashicorp/aws", version = "~> 5.0" }\n'
            "  }\n"
            "}\n"
            f'provider "aws" {{ region = "{region}" }}\n'
        )

    async def _auto_import(self, import_map: list, workdir: Path, run_id: str) -> list:
        """
        Importa recursos para o state automaticamente.
        Falhas individuais são ignoradas — só falha se nenhum importar.
        """
        results = []
        for item in import_map:
            address = item["address"]
            res_id  = item["id"]
            print(f"[{run_id}] IMPORT: {address} <- {res_id}", flush=True)

            lines = []
            rc    = 0
            async for line, rc in self._run_cmd(
                    ["terraform", "import", "-no-color", address, res_id], workdir):
                if line:
                    lines.append(line)
                    print(f"[{run_id}] IMPORT-OUT: {line}", flush=True)

            results.append({
                "address": address,
                "id":      res_id,
                "success": rc == 0,
                "output":  lines,
            })

        imported = sum(1 for r in results if r["success"])
        print(f"[{run_id}] IMPORT: {imported}/{len(results)} importados", flush=True)
        return results

    async def run(self, data: dict, action: str, template=None):
        run_id    = str(uuid.uuid4())[:8]
        workdir   = Path(f"/tmp/tf-{run_id}")
        plan_file = workdir / "tfplan"
        workdir.mkdir(parents=True)

        def event(step: str, msg: str) -> str:
            return f"data: {json.dumps({'step': step, 'msg': msg})}\n\n"

        try:
            region    = data.get("provider_region", self.aws_region)
            state_key = self._state_key(data)
            params    = data.get("_params", {})

            print(f"[{run_id}] action={action} state_key={state_key}", flush=True)
            print(f"[{run_id}] params={params} template={template}", flush=True)

            (workdir / "backend.tf").write_text(self._backend_tf(region, state_key))
            for f in data["arquivos"]:
                if f["conteudo"].strip():
                    (workdir / f["path"]).write_text(f["conteudo"])

            # ── terraform init ────────────────────────────────────────
            yield event("init", "terraform init...")
            rc = 0
            async for line, rc in self._run_cmd(
                    ["terraform", "init", "-no-color", "-reconfigure"], workdir):
                if line:
                    print(f"[{run_id}] INIT: {line}", flush=True)
                    yield event("init_out", line)

            if rc != 0:
                yield event("error", "terraform init falhou.")
                return

            # ── DELETE ────────────────────────────────────────────────
            if action == "delete":
                yield event("destroy", f"Verificando state...")

                # Plan -destroy completo sem break
                plan_output = []
                rc = 0
                async for line, rc in self._run_cmd(
                        ["terraform", "plan", "-destroy", "-no-color",
                         f"-out={plan_file}"], workdir):
                    if line:
                        plan_output.append(line)
                        print(f"[{run_id}] DESTROY-PLAN: {line}", flush=True)
                        yield event("plan_out", line)

                print(f"[{run_id}] plan -destroy rc={rc}", flush=True)

                state_empty = any(
                    "No objects need to be destroyed" in l or "No changes" in l
                    for l in plan_output
                )
                print(f"[{run_id}] state_empty={state_empty} template={template is not None}", flush=True)

                if state_empty:
                    if template is None:
                        yield event("error", "State vazio e template nao disponivel para import.")
                        return

                    import_map = template.import_map(params)
                    print(f"[{run_id}] import_map={import_map}", flush=True)

                    if not import_map:
                        yield event("error", "State vazio e import_map vazio para este recurso.")
                        return

                    yield event("plan_out",
                        f"State vazio — importando {len(import_map)} recurso(s)...")

                    results = await self._auto_import(import_map, workdir, run_id)
                    for r in results:
                        status = "OK" if r["success"] else "SKIP"
                        yield event("plan_out", f"  [{status}] {r['address']}")

                    imported = sum(1 for r in results if r["success"])
                    if imported == 0:
                        yield event("error",
                            "Nenhum recurso encontrado na AWS para importar. "
                            "Verifique o nome e a region.")
                        return

                    # Re-run plan -destroy apos import
                    yield event("plan_out", "Re-executando plan -destroy apos import...")
                    rc = 0
                    async for line, rc in self._run_cmd(
                            ["terraform", "plan", "-destroy", "-no-color",
                             f"-out={plan_file}"], workdir):
                        if line:
                            print(f"[{run_id}] DESTROY-PLAN2: {line}", flush=True)
                            yield event("plan_out", line)

                    if rc != 0:
                        yield event("error", "terraform plan -destroy falhou apos import.")
                        return

                elif rc != 0:
                    yield event("error", "terraform plan -destroy falhou.")
                    return

                # Apply -destroy
                yield event("destroy_confirm", "Destruindo recursos na AWS...")
                async for line, rc in self._run_cmd(
                        ["terraform", "apply", "-destroy", "-no-color",
                         "-auto-approve", str(plan_file)], workdir):
                    if line:
                        print(f"[{run_id}] DESTROY: {line}", flush=True)
                        yield event("apply_out", line)

                yield event("done", "Recurso destruido com sucesso.")
                return

            # ── terraform validate ────────────────────────────────────
            rc = 0
            async for line, rc in self._run_cmd(
                    ["terraform", "validate", "-no-color"], workdir):
                if line:
                    print(f"[{run_id}] VALIDATE: {line}", flush=True)
                    yield event("init_out", line)

            if rc != 0:
                yield event("error", "HCL invalido.")
                return

            # ── terraform plan ────────────────────────────────────────
            yield event("plan", "terraform plan...")
            rc = 0
            async for line, rc in self._run_cmd(
                    ["terraform", "plan", "-no-color", f"-out={plan_file}"], workdir):
                if line:
                    print(f"[{run_id}] PLAN: {line}", flush=True)
                    yield event("plan_out", line)

            if rc != 0:
                yield event("error", "terraform plan falhou.")
                return

            if action != "apply":
                yield event("plan_done",
                    "Plan concluido. Clique em Aplicar na AWS para criar.")
                return

            # ── terraform apply ───────────────────────────────────────
            yield event("apply", "Aplicando na AWS...")
            async for line, rc in self._run_cmd(
                    ["terraform", "apply", "-no-color", "-auto-approve",
                     str(plan_file)], workdir):
                if line:
                    print(f"[{run_id}] APPLY: {line}", flush=True)
                    yield event("apply_out", line)

            yield event("done",
                f"Recurso criado! State: s3://{self.state_bucket}/{state_key}")

        except Exception as e:
            print(f"[{run_id}] EXCEPTION: {e}", flush=True)
            yield event("error", str(e))
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    @staticmethod
    async def _run_cmd(cmd: list, cwd: Path):
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            text = line.decode().rstrip()
            if text:
                yield text, 0
        rc = await proc.wait()
        yield "", rc