# AG-UI protocol layer

The CLI and (eventually) Gradio UI communicate with the LangGraph agent through
the [AG-UI](https://github.com/ag-ui-protocol/ag-ui) event protocol. The
emitter is the single LangChain-aware seam: it allows renderers to dispatch on
`event.type` without the need to 'know' about LangGraph.

```mermaid
graph LR
    GH[GitHub tools]
    LG[LangGraph StateGraph]
    EM[emit_agui_events]
    BUS[AsyncIterator of BaseEvent]
    CLI[Rich CLI renderer]
    GR[Gradio renderer - planned]
    SSE[SSE encoder - planned]
    Term[Terminal]
    Web[Browser]
    Ext[External AG-UI clients]

    GH --- LG
    LG -->|astream_events v2| EM
    EM --> BUS
    BUS --> CLI
    BUS -.-> GR
    BUS -.-> SSE
    CLI --> Term
    GR -.-> Web
    SSE -.-> Ext

    classDef built fill:#dff5e1,stroke:#2a9d4a,color:#000
    classDef planned fill:#fff5d6,stroke:#c08a00,color:#000,stroke-dasharray:4 3
    class EM,BUS,CLI built
    class GR,SSE,Web,Ext planned
```

| Node | Source file |
|---|---|
| `emit_agui_events` | [src/agui/emitter.py](../../src/agui/emitter.py) |
| Rich CLI renderer | [src/agui/renderer.py](../../src/agui/renderer.py) |
| Gradio renderer (planned) | [src/ui/handlers.py](../../src/ui/handlers.py) |

Legend: solid green = implemented. Dashed amber = planned.
