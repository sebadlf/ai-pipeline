---
tags: [tools, obsidian, meta]
---

# Convenciones de este vault

## Estructura de carpetas

```
ai-pipeline-vault/
├── HOME.md                    # Punto de entrada
├── projects/                  # Un sub-folder por proyecto
│   ├── _templates/            # Templates reutilizables
│   └── [proyecto]/
│       ├── README.md          # Overview del proyecto
│       ├── decisions/         # ADRs
│       ├── domain/            # Conocimiento de dominio
│       └── runbooks/          # Procedimientos operativos
├── knowledge/                 # Conocimiento transversal
│   ├── python/
│   ├── ml/                    # ML y trading (específico para este vault)
│   ├── architecture/
│   ├── devops/
│   └── tools/
├── workflows/                 # Flujos de trabajo documentados
├── daily-logs/                # Diario de trabajo
└── retrospectives/            # Retros por ciclo
```

## Convenciones de nombrado

- **Archivos**: título descriptivo en español, con espacios: `Feature engineering y selección.md`
- **Templates**: prefijo `tpl-`: `tpl-adr.md`, `tpl-daily-log.md`
- **ADRs**: `ADR-NNN — Título.md`
- **Daily logs**: `YYYY-MM-DD.md`
- **Retros**: `Retro — [nombre del ciclo].md`

## Tags

Tags principales:
- Por tipo: `adr`, `domain`, `runbook`, `daily`, `retro`, `template`
- Por proyecto: `ai-pipeline`, `[otro-proyecto]`
- Por área: `trading`, `ml`, `python`, `devops`, `architecture`, `tools`

## Links

- Usar `[[wikilinks]]` para todo lo interno
- Usar `[markdown links](url)` solo para URLs externas
- Los README.md de cada sección son el punto de entrada — mantenerlos actualizados

## Plugins recomendados

- **Templater** — para usar los templates de `_templates/` al crear notas
- **Calendar** — para navegar daily logs por fecha
- **Dataview** — para queries dinámicas (ej: "todos los ADRs aceptados")
- **Git** — para versionar el vault automáticamente
