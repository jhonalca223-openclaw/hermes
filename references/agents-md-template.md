# agents.md template

Use this as the standard starting point for a repository or application onboarding file.

## Repository
- Name:
- Repo path:
- Remote:
- Default branch:
- Owners / maintainers:

## Purpose
- What this application does:
- Primary users:
- Business/domain context:
- Critical paths:

## Stack
- Language(s):
- Framework(s):
- Package manager / build system:
- Runtime / base image:
- OS / architecture assumptions:
- Observability stack:

## Deployment
- Platforms:
- Orchestration:
- CI/CD:
- Ingress / routing:
- Service mesh / edge / DNS:
- External dependencies:

## Bootstrap
- Install:
- Build:
- Run:
- Test:
- Lint:
- Migrations / seed:

## Configuration
- Main config files:
- Environment variables:
- Feature flags:
- ConfigMaps / mounted files:
- Runtime overrides:

## Secrets and credential locations
Document only *where* secrets live, not their values.

- DB credentials:
- App users / auth:
- Git credentials:
- Cloud credentials:
- Secret manager / vault refs:
- CI/CD secret names:

## Data and storage
- PVCs / volumes:
- Databases:
- Object storage:
- Backups / restore notes:
- Retention / cleanup notes:

## Operational notes
- Known pitfalls:
- Health checks:
- Rollout expectations:
- Architecture / platform notes:
- Recovery / failover notes:

## Verification
- Commands to confirm the app is healthy:
- Commands to confirm deployment state:
- Commands to confirm the repo is in sync:
- Commands to confirm secrets/config are resolved:

## Change log
- Date:
- Summary of notable repo changes:
- Notes for future agents:
