import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path


class TerraformPipeline:
    def __init__(self, state_bucket: str, aws_region: str):
        self.state_bucket = state_bucket
        self.aws_region   = aws_region

    def _backend_tf(self, region: str, run_id: str) -> str:
        has_creds = bool(os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_ROLE_ARN"))
        use_s3    = bool(self.state_bucket) and has_creds

        if use_s3:
            return (
                "terraform {\n"
                '  backend "s3" {\n'
                f'    bucket         = "{self.state_bucket}"\n'
                f'    key            = "poc/{run_id}/terraform.tfstate"\n'
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

    async def run(self, data: dict, action: str):
        run_id    = str(uuid.uuid4())[:8]
        workdir   = Path(f"/tmp/tf-{run_id}")
        plan_file = workdir / "tfplan"
        workdir.mkdir(parents=True)

        def event(step: str, msg: str) -> str:
            return f"data: {json.dumps({'step': step, 'msg': msg})}\n\n"

        try:
            region = data.get("provider_region", self.aws_region)
            (workdir / "backend.tf").write_text(self._backend_tf(region, run_id))

            for f in data["arquivos"]:
                if f["conteudo"].strip():
                    (workdir / f["path"]).write_text(f["conteudo"])

            print(f"[{run_id}] action={action} workdir={list(workdir.iterdir())}", flush=True)

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

            # ── DELETE: terraform destroy ─────────────────────────────
            if action == "delete":
                yield event("destroy", "Executando terraform destroy...")

                # plan do destroy para mostrar o que será removido
                async for line, rc in self._run_cmd(
                        ["terraform", "plan", "-destroy", "-no-color",
                         f"-out={plan_file}"], workdir):
                    if line:
                        print(f"[{run_id}] DESTROY-PLAN: {line}", flush=True)
                        yield event("plan_out", line)

                if rc != 0:
                    yield event("error", "terraform plan -destroy falhou.")
                    return

                yield event("destroy_confirm", "Plan de destruição gerado. Aplicando...")

                async for line, rc in self._run_cmd(
                        ["terraform", "apply", "-destroy", "-no-color",
                         "-auto-approve", str(plan_file)], workdir):
                    if line:
                        print(f"[{run_id}] DESTROY: {line}", flush=True)
                        yield event("apply_out", line)

                yield event("done", "Recurso destruído com sucesso.")
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
                yield event("plan_done", "Plan concluido. Use action=apply para criar.")
                return

            # ── terraform apply ───────────────────────────────────────
            yield event("apply", "Aplicando na AWS...")
            async for line, rc in self._run_cmd(
                    ["terraform", "apply", "-no-color", "-auto-approve",
                     str(plan_file)], workdir):
                if line:
                    print(f"[{run_id}] APPLY: {line}", flush=True)
                    yield event("apply_out", line)

            state_msg = (
                f"State: s3://{self.state_bucket}/poc/{run_id}/terraform.tfstate"
                if self.state_bucket else "State: local (efemero)"
            )
            yield event("done", f"Recurso criado! {state_msg}")

        except Exception as e:
            print(f"[{run_id}] EXCEPTION: {e}", flush=True)
            yield event("error", str(e))
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    @staticmethod
    async def _run_cmd(cmd: list, cwd: Path):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            text = line.decode().rstrip()
            if text:
                yield text, 0
        rc = await proc.wait()
        yield "", rc
