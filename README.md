# RoboMermaid
creating multiple levels of mermaid diagram from Yaml

# Diagram Views from a Single Mermaid Source

This repository uses a **single source of truth** approach for diagrams:

- Engineers author **one master Mermaid file** (`.mmd`) per logical diagram.
- The master file contains **view tags** that mark which parts belong to which perspectives (e.g. overview, customer, ops, security).
- An automated script **carves the master file into multiple view-specific outputs**:
  - A Markdown file with provenance and metadata.
  - An SVG image for embedding in other documents.

This ensures all diagram views stay consistent and are always derived from the same source.

---

## Authoring the Master Diagram

Create a file such as:

```
diagrams-src/UserJourneys.mmd
```

Use normal Mermaid syntax for any diagram type (flowchart, sequence, journey, state, etc.), and add **view tags** using Mermaid comments.

### Line-level view tags

A tag applies to the **next Mermaid statement**:

```mermaid
%%@view:overview,customer
A[Ingest]
```

This line will appear in the `overview` and `customer` views.

### Block-level view tags

For multi-line constructs, use begin/end markers:

```mermaid
%%@begin:view=security
subgraph Auth
  A1[Login]
  A2[Token]
end
%%@end
```

The entire block belongs to the `security` view.

### Global lines

Any line without a view tag is included in **all views**.  
Use this for:

- Diagram headers (`flowchart LR`, `sequenceDiagram`, `journey`, etc.)
- Theme or init blocks
- Shared participants or styles

---

## Carving Views

A script processes each master `.mmd` file and:

1. Reads all view tags.
2. For each view:
   - Extracts only the lines and blocks belonging to that view (plus global lines).
   - Writes a **view-specific Mermaid file**.
3. Generates two outputs per view:

### 1. Provenance Markdown

Example:

```
diagrams/UserJourneys_customer.md
```

Contains:

- Front-matter metadata (source file, view name, version, generation time).
- The carved Mermaid diagram (for readability and audit).

Example structure:

```markdown
---
source: diagrams-src/UserJourneys.mmd
view: customer
version: <git-sha>
generated: <timestamp>
---

# UserJourneys — customer

```mermaid
<carved diagram>
```
```

### 2. Rendered Image

Example:

```
diagrams/UserJourneys_customer.svg
```

This is the rendered diagram only, with **no metadata**, suitable for embedding.

---

## Using the Diagrams in Documentation

In any Markdown page, embed the SVG and link to its provenance page:

```markdown
[![Customer journey](../diagrams/UserJourneys_customer.svg)](../diagrams/UserJourneys_customer.md)
```

This gives:

- A clean visual in the document.
- A click-through link to full metadata and source context.

---

## Naming and Stability

Output files follow a stable pattern:

```
<MasterName>_<view>.md
<MasterName>_<view>.svg
```

For example:

```
UserJourneys_customer.md
UserJourneys_customer.svg
UserJourneys_ops.md
UserJourneys_ops.svg
```

Paths never change, so links remain valid even as diagrams evolve.

---

## Automation

The pipeline is fully automated:

1. Edit a master `.mmd` file.
2. Commit and push.
3. CI runs the carving and rendering script.
4. Updated `.md` and `.svg` view files are generated and committed.

This guarantees:

- One authoritative diagram source.
- Multiple consistent perspectives.
- Traceable provenance for every rendered image.
