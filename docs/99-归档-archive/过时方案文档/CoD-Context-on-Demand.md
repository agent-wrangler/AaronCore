# CoD — Context-on-Demand

```
Core_Architecture : CoD (Context-on-Demand)
Mode              : Hybrid Routing (Flash / Trace Back)
Principle         : Minimalist context loading, precise historical alignment.
```

## Overview

CoD is the dynamic context dispatch layer of NovaCore.
Every conversation turn triggers a binary routing decision:

- **Flash** — Respond directly from live context (L1 + L4).
  No retrieval. Pure intuitive resonance with the current moment.

- **Trace Back** — Activate memory recall (L2 search / L8 knowledge / tools).
  Historical alignment. Surfacing what matters from the past.

## Design Principle

> "Sustain resonance through instant intuition.
>  Complete alignment through deep historical tracing."

The routing is automatic and invisible to the user.
The dashboard surfaces the ratio as a retrospective health metric —
not a real-time monitor, but a mirror of Nova's cognitive pattern over time.

## Key Files

| Layer | File | Role |
|-------|------|------|
| Routing decision | `routes/chat.py` | `_cod_used_this_turn` flag |
| Stats recording  | `core/state_loader.py` | `record_memory_stats(cod_used=...)` |
| Dashboard UI     | `static/js/stats.js` | `buildMemoryModule()` |
