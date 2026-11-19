# COMSOL Multiphysics Unified MCP (`comsol-mcp-unified`)

A clean-room, MIT-licensed, modular **Model Context Protocol (MCP)** server for **COMSOL Multiphysics** that unifies the strongest architectural ideas across the COMSOL MCP ecosystem into one cleanly packaged repository—with **selectable tool profiles**, **zero committed vendor binaries/PDFs**, and **MCP Python SDK v1 & v2 compatibility**.

## What It Unifies

| Capability | Profile | Description |
| :--- | :--- | :--- |
| **Warm `mph` Interactive Session** | `core` (87 tools + 4 MCP resources) | Full parity interactive modeling: session, model CRUD/version/audit/diff/Java export, parameters & sweeps, geometry primitives/booleans/selections, materials, physics features, meshing, sync/async solving, results/interpolation/export, and generic low-level node mutation. |
| **Domain Physics & Physics Builder** | `physics` (45 tools) | Full 10-tool Electrochemistry/battery suite, acoustics & PDE builders + boundary presets, interactive flow/heat setup helpers, multiphysics couplings, and custom `.mphphb` Physics Builder XML generation, registration & status. |
| **Isolated Native CLI Batch Queue** | `batch` (10 tools) | Direct `comsolcompile` + `comsolbatch` async job queue (no `mph`/JPype needed), workspace file locking, non-destructive copy-on-edit `.mph` publication, completion-marker verification, short temp dir (`MAX_PATH` safe), and real OS process-tree cancellation. |
| **Windows Desktop GUI & Live `Model1`** | `gui` (6 tools) | COMSOL Desktop process/window diagnostics, full/graphics-panel screenshots, restricted `model.` Java Shell execution, `mph` → Desktop sync, and live COMSOL Server `Model1` attach. |
| **Offline COMSOL API Catalog** | `catalog` (11 tools) | Built-in physics/BC/variable/discretization reference schemas + `static_catalog_*` parity tools + local extractor (`comsol-mcp catalog-build`) decoding `<COMSOL_HOME>/data/completion/*.xml` from your own installation. |
| **Guided Workflows & Pre-Solve Validation** | `validate` (5 tools) | Stateful 10-step modeling workflow templates, rule-based model/material/boundary/mesh/study completeness validator, and bilingual (EN/ZH) modeling assistant. |
| **Embedded Guides & Optional PDF RAG** | `rag` (11 tools) | Built-in offline guides + troubleshooting + `pdf_*` parity aliases + optional ChromaDB/PyMuPDF semantic search supporting **both** local `sentence-transformers` and OpenAI-compatible/DashScope API embeddings. |
| **Dry-Run Simulator & Java Codegen** | `dryrun` (4 tools) | Full in-memory simulator for testing without a COMSOL license + standalone offline COMSOL Java model generator (`generate_model_java`). |

**Total with `COMSOL_MCP_PROFILES=all`: 179 unique tools (100% 135/135 classic COMSOL-MCP tool parity + 44 unified batch/GUI/validation/catalog/dryrun tools) + 4 MCP resources.**

Also includes a zero-dependency local status dashboard (`comsol-mcp web`) and CLI diagnostics (`comsol-mcp doctor`).

## Quick Start

### 1. Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mph,dev]"
```

Optional extras:
- `.[mph]` — warm `mph` + `jpype1` backend
- `.[gui]` — Windows Desktop GUI automation (`pywinauto`, `pywin32`, `pyperclip`, `Pillow`, `psutil`)
- `.[rag-local]` — offline PDF RAG (`pymupdf`, `chromadb`, `sentence-transformers`)
- `.[rag-api]` — PDF RAG with remote OpenAI-compatible / DashScope embeddings (`pymupdf`, `chromadb`)

### 2. Inspect Environment (`doctor`)

```powershell
comsol-mcp doctor
```

### 3. Extract Local COMSOL XML Catalog (Optional, Recommended)

```powershell
comsol-mcp catalog-build
```

This parses your installed `<COMSOL_HOME>/data/completion/*.xml` into `./catalog_cache/` (git-ignored) so agents can look up exact COMSOL feature and property names offline.

### 4. Configure Your MCP Client

**Full unified server (all 179 tools + 4 resources, including 100% 135/135 classic COMSOL-MCP parity):**
```json
{
  "mcpServers": {
    "comsol": {
      "command": "C:/path/to/comsol-mcp-unified/.venv/Scripts/python.exe",
      "args": ["-m", "comsol_mcp", "serve"],
      "env": {
        "COMSOL_MCP_PROFILES": "all",
        "COMSOL_MCP_WORKSPACE": "C:/path/to/comsol-mcp-unified/models"
      }
    }
  }
}
```

**Focused profile examples (smaller LLM tool context):**
- Interactive `mph` + catalog + validation (34 tools): `"COMSOL_MCP_PROFILES": "core,catalog,validate"`
- Minimal native Windows batch queue only (10 tools): `"COMSOL_MCP_PROFILES": "batch"`
- Dry-run development without COMSOL installed: `"COMSOL_MCP_DRYRUN": "true"`

### 5. Optional Web Status Dashboard

```powershell
comsol-mcp web --port 8765
```

## MCP Resources

When the server runs, four read-only MCP resources are always exposed:
- `comsol://session/info` — overall backend, profile, and workspace status
- `comsol://model/{name}/tree` — full model inspection tree
- `comsol://model/{name}/parameters` — model parameters
- `comsol://model/{name}/physics` — physics interfaces and features

## Testing

```powershell
pytest
```

All unit, protocol, dry-run, catalog, validator, codegen, and batch process-control tests run offline without consuming a COMSOL license seat.

## License

MIT — see [LICENSE](LICENSE). This project is an independent community integration and is not affiliated with or endorsed by COMSOL AB.
