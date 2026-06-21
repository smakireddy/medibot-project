# Step 1 — Parse (`ingestion/parser.py`)

## What it does

Converts a raw PDF file into a `DoclingDocument` — a structured, in-memory object that understands the document's layout rather than treating it as flat text.

## Why not PyMuPDF or pdfplumber?

Standard PDF extractors give you one giant string per page with no structural awareness:

```
# pdfplumber output (bad)
"Adult Dosage — Amoxicillin\n25mg twice daily. Duration: 7 days.\nDose | Age | Weight\n..."
```

Docling runs a **layout analysis model** on the PDF and identifies individual element types:

| Element | Class | Example |
|---|---|---|
| Section heading | `SectionHeaderItem` | "Adult Dosage — Amoxicillin" |
| Body paragraph | `TextItem` | "25mg twice daily..." |
| Table | `TableItem` | Each cell preserved, not flattened |
| Code block | label `"code"` | Protocol steps, formulas |

This structure is what allows the chunker in the next step to produce **heading-aware chunks** instead of arbitrary text windows.

## The converter is a singleton

```python
_converter: DocumentConverter | None = None

def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter
```

`DocumentConverter` loads a layout analysis model on first call. Reusing it across all files in a collection avoids reloading the model for every PDF — ingestion time drops significantly on collections with many files.

## Output

```
parse_document("drug_formulary.pdf")
→ DoclingDocument
    ├── SectionHeader: "Drug Formulary"
    │     └── SectionHeader: "Antibiotics"
    │           └── SectionHeader: "Amoxicillin"
    │                 ├── SectionHeader: "Adult Dosage"
    │                 │     └── Paragraph: "25mg twice daily..."
    │                 └── Table: [dose | age | weight | notes]
    └── ...
```

This structured object is passed directly to Step 2 (chunking). The original PDF file is not used again.

## Source

- Module: [`ingestion/parser.py`](../../ingestion/parser.py)
- Docling docs: https://ds4sd.github.io/docling/
