# Hermes Secrets Map

This document defines the standard way Hermes should record *where* secrets live, not the secret values themselves.

## Source of truth

- **Human/operator secrets:** HashiCorp Vault
- **Cluster materialization:** Kubernetes Secrets created from Vault-backed workflows
- **GitOps repository:** only references, manifests, and secret locations
- **Memory:** never store secret values

## Enabled Vault engines

- `kv/` — persistent static secrets
- `kubernetes/` — cluster/service-account related access
- `aws/` — cloud access and dynamic AWS credentials
- `azure/` — cloud access and dynamic Azure credentials
- `ssh/` — SSH credentials and short-lived access
- `cubbyhole/` — session-scoped temporary secrets

## Path conventions

Use stable, human-readable paths.

### KV

Recommended shape:

- `kv/hermes/<repo-or-app>/...`
- `kv/cluster/<namespace>/...`
- `kv/operator/<system>/...`

Examples:

- `kv/hermes/github/pat`
- `kv/hermes/jira/api-token`
- `kv/hermes/azure/devops-pat`
- `kv/cluster/hermes/openai-api-key`
- `kv/cluster/redone/db-password`

### Kubernetes

Use this engine for Kubernetes-facing auth material and cluster integration references.

Suggested shapes:

- `kubernetes/<cluster>/<namespace>/...`
- `kubernetes/<cluster>/<service-account>/...`

Examples:

- `kubernetes/k3s/hermes/service-account`
- `kubernetes/k3s/argocd/repo-creds`

### AWS

Suggested shape:

- `aws/<account>/<purpose>/...`

Examples:

- `aws/prod/terraform`
- `aws/shared/backup-role`

### Azure

Suggested shape:

- `azure/<tenant>/<subscription>/<purpose>/...`

Examples:

- `azure/main/devops`
- `azure/main/automation`

### SSH

Suggested shape:

- `ssh/<host-or-group>/<purpose>/...`

Examples:

- `ssh/raspi516/admin`
- `ssh/k3s-control-plane/bootstrap`

### Cubbyhole

Use only for temporary/session-bound material:

- short-lived tokens
- one-off bootstrap material
- ephemeral verification data

Do not use cubbyhole as the long-term home for anything important.

## What must be documented in `agents.md`

Only record *locations* and references:

- Vault path
- secret name
- Kubernetes Secret / SealedSecret name
- namespace
- env var key
- file path
- service-account or auth role name
- cloud vault reference

Do **not** record:

- passwords
- PATs
- tokens
- private keys
- JSON secret payloads

## Recommended repo convention

For each application or repo, document a small secret inventory:

| Secret type | Location |
|---|---|
| DB password | `kv/<app>/db/password` |
| App token | `kv/<app>/token` |
| GitHub PAT | `kv/hermes/github/pat` |
| Azure DevOps PAT | `kv/hermes/azure/devops-pat` |
| SSH access | `ssh/<host>/<purpose>` |
| K8s service access | `kubernetes/<cluster>/<namespace>/...` |

## Workflow

1. Discover the secret source during repo onboarding.
2. Write the location into `agents.md`.
3. If the value must reach Kubernetes, materialize it through Vault-backed automation or a sealed secret workflow.
4. Keep the repo free of plaintext secret values.

## Verification checklist

- [ ] Secret locations are documented
- [ ] No secret values appear in repo docs
- [ ] The source of truth is Vault or another approved secret manager
- [ ] Kubernetes workloads reference materialized secrets, not plaintext values in git
- [ ] The documentation is updated when a secret path or source changes
