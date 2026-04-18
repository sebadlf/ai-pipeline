---
tags: [template]
---

# CLAUDE.md Template

Copiar este contenido al `CLAUDE.md` de cada nuevo proyecto.

---

```markdown
# CLAUDE.md

## Project Overview
[Qué es el proyecto, para quién, por qué existe. 2-3 oraciones.]

## Development Commands

\```bash
# Instalar dependencias
[comando]

# Correr en desarrollo
[comando]

# Correr tests
[comando]

# Lint / format
[comando]
\```

## Architecture
[Estructura de módulos, patrones clave, decisiones no-obvias que Claude necesita saber.]

## Conventions
- Naming: [snake_case, camelCase, etc.]
- Error handling: [patrón]
- Logging: [patrón]

## External References
- Linear project: [link]
- API docs: [archivo o link]
- Obsidian notes: [path en el vault]

## Git Conventions
- Branch format: `{linear-id}-{short-description}`
- Commit style: [conventional commits / free-form / etc.]
- Always reference Linear issue ID in PR body
```
