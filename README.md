# Hermes Agent — k3s + ArgoCD 🌀

[![Deploy](https://img.shields.io/badge/ArgoCD-Deployed-1f8ef1?logo=argo)](https://argo-cd.readthedocs.io/)

Depliegue de **Hermes Agent** (Nous Research) en k3s vía ArgoCD con GitOps.

## 📋 Stack

| Componente | Detalle |
|---|---|
| **Namespace** | `hermes` |
| **Modelo** | DeepSeek (`deepseek/deepseek-chat`) via OpenAI-compatible endpoint |
| **Gateway** | Telegram (principal) |
| **Almacenamiento** | Longhorn PVC (10Gi) |
| **Modo** | Gateway + CLI + Tools básicos |
| **ServiceAccount** | `hermes-agent` |

## 🗂️ Estructura del Repo

```
hermes/
├── argo/
│   └── application.yaml       # ArgoCD Application (app-of-apps)
├── namespace.yaml              # Namespace hermes
├── configmap.yaml              # Config + SOUL.md
├── pvc.yaml                    # PersistentVolumeClaim 10Gi
├── deployment.yaml             # Deployment del Gateway
├── secret.yaml.example         # Template de secrets (¡no subir el real!)
└── kustomization.yaml          # Kustomize wrapper
```

## 🚀 Primer Despliegue

### 1. Crear el Secret con credenciales

```bash
kubectl create secret generic hermes-secrets -n hermes \
  --from-literal=OPENAI_API_KEY="sk-deepseek-key-aqui" \
  --from-literal=TELEGRAM_BOT_TOKEN="tu-bot-token-aqui"
```

O usando el template:
```bash
cp secret.yaml.example secret.yaml
# Editar secret.yaml con tus credenciales
kubectl apply -f secret.yaml
```

### 2. Desplegar con ArgoCD

```bash
kubectl apply -f argo/application.yaml
```

O via CLI de ArgoCD:
```bash
argocd app create hermes-agent \
  --repo https://github.com/jhonalca223-openclaw/hermes.git \
  --path . \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace hermes \
  --sync-policy automated
```

### 3. Verificar

```bash
kubectl get pods -n hermes -w
kubectl logs -n hermes deployment/hermes-agent -f
```

## 🔧 Comandos útiles

```bash
# Ver config activa
kubectl exec -n hermes deployment/hermes-agent -- hermes config

# Chat interactivo (CLI dentro del pod)
kubectl exec -n hermes -it deployment/hermes-agent -- hermes chat

# Logs del gateway
kubectl logs -n hermes deployment/hermes-agent -f

# Shell directo al container
kubectl exec -n hermes -it deployment/hermes-agent -- bash
```

## ⚙️ Configuración

La configuración principal está en `configmap.yaml`:

- **Modelo:** DeepSeek via `api.deepseek.com/v1` (OpenAI-compatible)
- **Terminal:** Local dentro del container
- **Tools:** web_search, web_extract, file_tools, code_execution, terminal
- **Gateway:** Telegram

### Dashboard web

El dashboard público de Hermes ahora usa auth básica cuando se expone en
`0.0.0.0`.

- `HERMES_DASHBOARD_BASIC_AUTH_USERNAME`
- `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH`
- `HERMES_DASHBOARD_BASIC_AUTH_SECRET`

Esos valores se inyectan desde el `SealedSecret` `hermes-secrets`, así que
quedan gestionados por GitOps sin dejar secretos en claro en el repo.
La vía OAuth/OIDC sigue existiendo como alternativa, pero no es necesaria
para este despliegue.

Para agregar más plataformas: editar `configmap.yaml` > `gateway.platforms` y agregar las credenciales en el Secret.

El Deployment usa un ServiceAccount dedicado `hermes-agent`, preparado para autenticación GitOps con Vault Kubernetes auth.
Además, monta un JWT proyectado en `/var/run/secrets/vault/token` con `audience: vault`, que es el formato esperado por el rol `hermes-agent` en Vault.

Para apuntar a HCP Vault, define `VAULT_ADDR` con el endpoint de HCP y conserva:

- `VAULT_ROLE=hermes-agent`
- `VAULT_AUTH_PATH=kubernetes`
- `VAULT_JWT_PATH=/var/run/secrets/vault/token`

La policy `admin` debe existir en Vault y el rol `hermes-agent` debe tenerla asociada.

## 📦 Actualización

ArgoCD sincroniza automáticamente los cambios en `main`. Para forzar un redeploy del pod cuando cambia el ConfigMap:

```bash
kubectl rollout restart -n hermes deployment/hermes-agent
```

## 🔐 Seguridad

- No subir `secret.yaml` al repositorio
- Usar External Secrets Operator para gestión centralizada de secrets (ver template)
- El gateway solo acepta usuarios autorizados (configurable en Secret)
