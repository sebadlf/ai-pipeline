---
date: 2026-04-18
status: in_progress
tags: [plan, integration, claude, obsidian, linear, github]
---

# Integración Claude+Obsidian+Linear+GitHub — plan de continuación

Plan iniciado el 2026-04-18 para montar en `ai-pipeline` la integración de Claude Code + Obsidian + Linear + GitHub (flujo: issue en Linear → branch + PR → auto-merge → auto-close → actualizar vault). Esta nota queda versionada en el repo para poder retomar el trabajo desde otra máquina.

## Decisiones previas ya tomadas

- **Linear team**: se reutiliza `Becerra` (prefix `BEC`). NO se crea equipo `AIP` (el usuario cambió de idea a mitad de la sesión inicial).
- **Team ID de Linear**: `8d9ea564-f922-4b4d-8784-a0b55e98d73d`
- **Vault name**: `ai-pipeline-vault/` dentro del repo.
- **Branch format**: `sebadlf-bec-{issue-number}-{descripcion}`.

## Lo que ya está hecho (no repetir)

### Vault (`ai-pipeline-vault/`)
- Estructura completa: `HOME.md`, `projects/_templates/` (6 templates), `projects/ai-pipeline/{decisions,domain,runbooks,plans}`, `knowledge/{python,ml,architecture,devops,tools}`, `workflows/`, `daily-logs/`, `retrospectives/`.
- **3 ADRs**: ADR-001 (Docker híbrido), ADR-002 (Polars sobre pandas), ADR-003 (Ensemble top-3 weighted avg).
- **6 domain notes**: Feature engineering y selección, Normalización con stats persistentes, Clustering de stocks, Optuna y overfitting gap penalty, Promotion cascading y precision-at-threshold, Regime detection y backtesting.
- **3 runbooks**: Setup desde cero, Correr el pipeline end-to-end, Cleanup de MLflow runs.
- **Daily log** `2026-04-18.md` con el cierre de la sesión de setup.
- **Workflow**: `workflows/Workflow de desarrollo.md` con el flujo de 5 pasos diario adaptado a ai-pipeline.

### GitHub Actions + PR template
- `.github/workflows/ci.yml` — jobs: `lint` (ruff check + format --check) y `test` (pytest), ambos con `uv sync --extra dev`.
- `.github/workflows/auto-merge.yml` — squash auto-merge al abrir/reabrir PR no-draft cuando CI pasa.
- `.github/pull_request_template.md` — con slot para Linear ID `BEC-...`.

### CLAUDE.md
Extendido con 3 secciones al final (sin tocar el contenido técnico existente):
- **External References**: Linear team BEC, vault path, GitHub repo, MLflow
- **Git Conventions**: branch format, PR body con BEC-N, main protegido, CI obligatorio, auto-merge
- **Workflow**: flujo de 7 pasos con cierre de vault obligatorio (paso 7)

### Permisos Claude Code
`.claude/settings.local.json` extendido con `mcp__linear__*`, `mcp__obsidian__*`, `mcp__github__*` + helpers bash de `git` / `gh` / `uv run ruff` / `uv run pytest`.

## Pendiente

### Paso 1 — `.gitignore` del vault

Agregar al `.gitignore` del repo:

```
ai-pipeline-vault/.obsidian/
```

Motivo: cuando el usuario abra el vault en Obsidian desktop, se genera la carpeta `.obsidian/` con config local (workspace layout, recent files, hotkeys personalizados) que no debe viajar al repo. El archivo `.gitignore` del repo ya existe — sólo agregar la línea.

### Paso 2 — Decidir organización de issues dentro del team BEC

Si el team Linear `Becerra` se comparte con otros repos/proyectos del usuario, hay que definir cómo filtrar los issues que corresponden a `ai-pipeline`. Opciones:

- **Sub-project Linear** (recomendado): crear un project `ai-pipeline` dentro del team. Tiene mejor UI de filtro en Linear.
- **Label por repo**: más liviano, pero se pierde en la UI.
- **Prefijo en el título**: frágil, no recomendado.

Si el team es exclusivo de este repo, este paso no aplica. Consultar con el usuario.

### Paso 3 — Primer issue real de smoke-test

Crear en Linear (team `BEC`) un issue chico y observable para validar que todo el circuito funciona end-to-end.

**Propuesta de contenido**:
- **Título**: "Validar flujo integrado Claude+Obsidian+Linear+GitHub en ai-pipeline"
- **Descripción**: PR trivial (ej. agregar `ai-pipeline-vault/.obsidian/` al `.gitignore` — ver Paso 1) para verificar que auto-merge funciona, CI pasa, y Linear auto-cierra el issue al mergear la PR.
- **Criterios de aceptación**:
  - PR creada con branch `sebadlf-bec-N-validar-flujo-integrado`
  - CI verde (ruff lint + format + pytest)
  - Auto-merge squash se ejecuta solo
  - Linear auto-cierra el issue porque el PR body menciona `BEC-N`

### Paso 4 — Ejecutar flow end-to-end

Con el issue `BEC-N` creado:

```bash
git checkout main && git pull
git checkout -b sebadlf-bec-N-validar-flujo-integrado

# Edit .gitignore: agregar ai-pipeline-vault/.obsidian/

git add .gitignore
git commit -m "chore: ignore obsidian local config (BEC-N)"
git push -u origin sebadlf-bec-N-validar-flujo-integrado

gh pr create --title "chore: ignore obsidian local config" --body "Closes BEC-N"
```

Luego observar:
1. Que el workflow `ci.yml` corre y pasa.
2. Que el workflow `auto-merge.yml` setea auto-merge en la PR.
3. Que al pasar CI, GitHub mergea squash automáticamente.
4. Que Linear auto-cierra `BEC-N` por el `Closes BEC-N` en el body.

**Nota sobre auto-close de Linear**: requiere que la integración GitHub↔Linear esté activa en el workspace. Si no cierra solo, instalar el Linear GitHub app desde https://linear.app/settings/integrations/github.

### Paso 5 — Validar CI

Es probable que pytest en CI falle por:

- **Dependencias pesadas**: `torch`, `mlflow`, `polars`, `optuna` son grandes. El job de CI las instala con `uv sync --extra dev` — puede tardar 2-5 min y consumir minutos de GitHub Actions.
- **Tests que requieren DB/MLflow**: si algún test necesita Postgres live o MLflow server, va a romper. Mirigación:
  - Marcarlos con `@pytest.mark.integration` y excluirlos del CI con `uv run pytest -m "not integration"`
  - O mover tests de integración a una suite aparte.
- **Ruff encuentra errores en código existente**: el proyecto nunca corrió ruff en CI hasta ahora. Probable que falle la primera vez. Mitigación: en una PR previa al smoke-test, correr `uv run ruff check --fix .` + `uv run ruff format .` y commitear el resultado como "chore: ruff pass".

### Paso 6 — Retrospectiva

Cuando el smoke-test quede verde, crear en `ai-pipeline-vault/retrospectives/Retro — integración inicial.md` documentando qué salió bien y qué ajustar. Usar template `tpl-retrospectiva`.

## Contexto técnico para retomar

- **Repo path**: ajustar al path local donde esté clonado el repo `ai-pipeline`
- **Vault path relativo**: `ai-pipeline-vault/` en la raíz del repo (ya versionado)
- **Workflow doc**: `ai-pipeline-vault/workflows/Workflow de desarrollo.md`
- **Project index**: `ai-pipeline-vault/projects/ai-pipeline/README.md`
- **Todo el scaffolding previo** está commiteado dentro del repo — no se necesita ninguna referencia externa para retomar el trabajo.

## Links a notas relacionadas

- [[../README|AI Pipeline README]]
- [[../../../workflows/Workflow de desarrollo]]
- [[../runbooks/Setup desde cero]] — si hace falta re-onboarding en otra máquina
