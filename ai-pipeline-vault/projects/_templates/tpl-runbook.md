---
tags: [template]
---

# Runbook Template

Para procedimientos operativos que se repiten.

---

```markdown
---
last_verified: YYYY-MM-DD
tags: [runbook, area]
---

# Runbook: [Nombre del procedimiento]

## Cuándo usar
[En qué situación se ejecuta este runbook.]

## Pre-requisitos
- [ ] [Acceso / herramienta / permiso necesario]

## Pasos

### 1. [Paso]
\```bash
[comando]
\```
[Explicación breve si no es obvio.]

### 2. [Paso]
...

## Verificación
[Cómo confirmar que el procedimiento fue exitoso.]

## Rollback
[Cómo revertir si algo sale mal.]

## Historial
| Fecha | Quién | Notas |
|-------|-------|-------|
| YYYY-MM-DD | ... | ... |
```
