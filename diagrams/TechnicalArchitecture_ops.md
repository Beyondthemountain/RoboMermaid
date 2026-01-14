---
title: "ops"
source: "diagrams-src/TechnicalArchitecture.mmd"
version: "eb23057"
generated: "2026-01-14T11:35:37+00:00"
---

# ops

[View SVG](./TechnicalArchitecture_ops.svg)

```mermaid
flowchart LR
%% Global config (included in all views)
%%{init: {"theme":"default"}}%%











%% Connections (tag edges so they carve cleanly)










%% Styles (global)
classDef actor fill:#fff,stroke:#333,stroke-width:1px;
classDef component fill:#f7f7ff,stroke:#333,stroke-width:1px;
classDef service fill:#eef9ff,stroke:#333,stroke-width:1px;
classDef data fill:#fff8e6,stroke:#333,stroke-width:1px;
classDef ops fill:#f0fff4,stroke:#333,stroke-width:1px;
classDef security fill:#fff0f0,stroke:#333,stroke-width:1px;
user["User"]:::actor
obs["Observability (Logs/Metrics/Tracing)"]:::ops
queue[("Event Bus / Queue")]:::data
ingest --> queue
parse --> queue
ingest -.-> obs
parse -.-> obs
api_gw -.-> obs
auth -.-> obs
```
