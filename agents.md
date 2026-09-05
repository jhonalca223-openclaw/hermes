# agents.md

## Repository
- Name: hermes
- Repo path: /opt/data/workspace/hermes
- Remote: https://github.com/jhonalca223-openclaw/hermes.git
- Default branch: main
- Owners / maintainers: jhonalca223-openclaw / Hermes GitOps maintainers

## Purpose
- What this application does: deploy Hermes Agent in k3s via ArgoCD/GitOps
- Primary users: Kelvin and authorized Telegram users
- Business/domain context: AI agent runtime with Telegram gateway and persistent workspace
- Critical paths: gateway startup, config mount, secret materialization, GitHub repo sync, persistent skills/session storage

## Stack
- Language(s): YAML, shell, markdown
- Framework(s): Hermes Agent, Argo CD, Kustomize, Istio
- Package manager / build system: GitOps manifests only; no app build system in this repo
- Runtime / base image: `nousresearch/hermes-agent:v2026.8.3`
- OS / architecture assumptions: k3s on Raspberry Pi / ARM64; initContainer installs ARM64 kubectl
- Observability stack: Kubernetes logs, pod status, ArgoCD sync/health

## Deployment
- Platforms: k3s
- Orchestration: ArgoCD Application (`argo/application.yaml`) + Kustomize
- CI/CD: GitOps on `main`
- Ingress / routing: Istio VirtualService `hermes.kdvops.com`
- Service mesh / edge / DNS: Istio gateway `istio-system/kdvops-gateway`
- External dependencies: Telegram bot API, OpenAI/DeepSeek API, GitHub repo access, k8s API, Longhorn storage, local AI provider at `http://pi-llm.local-ai.svc.cluster.local:8080/v1`

## Bootstrap
- Install: apply `argo/application.yaml` or let ArgoCD sync `main`
- Build: not applicable in-repo
- Run: Kubernetes Deployment `hermes-agent`
- Test: `kubectl get pods -n hermes`, `kubectl logs -n hermes deployment/hermes-agent -f`
- Lint: Kubernetes YAML validation via cluster apply / kustomize render
- Migrations / seed: none

## Configuration
- Main config files: `configmap.yaml`, `deployment.yaml`, `kustomization.yaml`, `argo/application.yaml`
- Environment variables: `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOW_ALL_USERS`, `TELEGRAM_ALLOWED_USERS`, `GITHUB_PAT`, `KUBECONFIG`, `HERMES_DASHBOARD_*`
- Feature flags: `gateway.platforms.telegram.enabled`, `gateway.allow_all_users`, `skills.auto_create`
- ConfigMaps / mounted files: `/opt/data/config.yaml`, `/opt/data/SOUL.md`
- Runtime overrides: container env, mounted PVC at `/opt/data`, initContainer-restored skills from `/opt/data/skills`

## Secrets and credential locations
Document only *where* secrets live, not their values.

- DB credentials: none in this repo
- App users / auth: `hermes-secrets` SealedSecret in namespace `hermes`
- Git credentials: `hermes-github` SealedSecret → `GITHUB_PAT`
- Cloud credentials: none documented
- Secret manager / vault refs: Bitnami SealedSecrets controller in-cluster; Vault access via Kubernetes auth with projected SA JWT at `/var/run/secrets/vault/token`
- CI/CD secret names: `hermes-secrets`, `hermes-github`

## Data and storage
- PVCs / volumes: `hermes-data` PVC, Longhorn, 10Gi, ReadWriteOnce
- Databases: SQLite state under the Hermes data volume
- Object storage: none
- Backups / restore notes: repo-managed skills are restored from GitOps checkout into `/opt/data/skills` during initContainer startup
- Retention / cleanup notes: PVC persists sessions, memories, logs, skills, workspace, and git metadata

## Operational notes
- Known pitfalls: repo uses an initContainer to clone/pull itself and restore skills from GitOps; ARM64 kubectl install happens there; `deployment.yaml` mounts `/opt/data` and uses the same PVC for persistent state
- Health checks: `hermes config` liveness probe, startup probe checks `/opt/data/config.yaml` and `/opt/data/workspace`
- Rollout expectations: ArgoCD syncs `main`; restart deployment if ConfigMap-only changes must be reloaded immediately
- Architecture / platform notes: service account is required for pod-side Kubernetes access; Vault auth uses a projected JWT with `audience=vault`; repo is optimized for k3s + GitOps on ARM64
- Recovery / failover notes: if skills are lost on PVC, initContainer repopulates them from the repo clone

## Verification
- Commands to confirm the app is healthy: `kubectl get pods -n hermes`, `kubectl logs -n hermes deployment/hermes-agent -f`
- Commands to confirm deployment state: `kubectl get deploy -n hermes hermes-agent`, `kubectl get sa -n hermes`, `kubectl get application -n argocd hermes-agent`
- Commands to confirm the repo is in sync: `git status --short --branch`, `git rev-list --left-right --count origin/main...HEAD`
- Commands to confirm secrets/config are resolved: `kubectl get secret -n hermes hermes-secrets hermes-github`, `kubectl exec -n hermes deployment/hermes-agent -- hermes config`

## Change log
- Date: 2026-08-12
- Summary of notable repo changes: added repo onboarding metadata and a dedicated Kubernetes ServiceAccount for Hermes
- Notes for future agents: keep GitOps-managed runtime behavior in sync between repo manifests and the initContainer bootstrap flow
