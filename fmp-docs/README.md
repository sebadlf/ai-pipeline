# Documentación local — Financial Modeling Prep (FMP)

Espejo offline de la documentación pública de la API **stable**, generado desde [developer/docs](https://site.financialmodelingprep.com/developer/docs).

## Contenido

| Archivo / carpeta | Descripción |
|-------------------|-------------|
| [`developer-docs-main.html`](developer-docs-main.html) | HTML completo de la página principal de documentación (navegación, enlaces, estructura del sitio). |
| [`stable/`](stable/) | **263** páginas en Markdown, una por endpoint/slug stable (título, URL del endpoint, descripción, parámetros en JSON). |
| [`STABLE_INDEX.md`](STABLE_INDEX.md) | Lista enlazada de todos los slugs (regenerable). |
| [`propuesta-endpoints.md`](propuesta-endpoints.md) | Endpoints sugeridos para enriquecer el pipeline de trading ML de este repo. |

## Regenerar la documentación

Desde la raíz del repositorio:

```bash
uv run python scripts/sync_fmp_docs.py
```

Opcional: prueba de humo de la API (requiere `FMP_API_KEY` en el entorno; **no** commitear la clave):

```bash
export FMP_API_KEY="tu_clave"
uv run python scripts/sync_fmp_docs.py --verify
```

**Nota:** Peticiones sin `User-Agent` de navegador pueden recibir `403` desde CloudFront; el script usa un User-Agent estándar.

## Seguridad

No incluyas la API key en archivos versionados. Si la clave se compartió en texto plano, rota la clave en el panel de FMP.
