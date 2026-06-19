# Decision Record: LLM Inference for Self-Hosted ("data stays on the founder's servers")

**Status:** Decided · **Applies to:** Phase 2 (self-hosted, single-tenant)

## The problem

Phase 2's promise is "founder data never leaves the founder's infrastructure."
But the dCernment must send signal content (emails, Slack snippets,
revenue figures) to an LLM to synthesize alerts. If that LLM is a third-party
cloud API (Anthropic, OpenAI), the data *does* leave the box — to the model
vendor. So "data never leaves" is in tension with using the best models.

## Options considered

| Option | Data leaves box? | Quality | Ops burden on founder | Cost |
|---|---|---|---|---|
| **A. BYO cloud keys** (founder's own Anthropic/OpenAI account) | Yes → model vendor only (under vendor's enterprise/zero-retention terms) | Highest | None | Per-token, founder pays vendor |
| **B. Fully local model** (vLLM / Ollama on founder's GPU) | No — never leaves | Good→High (70B-class) but below frontier | High (GPU, model ops) | Hardware + electricity |
| **C. Hybrid** | Founder chooses A or B per deployment | — | — | — |

## Decision

**Ship C (hybrid), defaulting to A (BYO cloud keys), with B (local) as a
first-class, config-only switch.**

Rationale:
- **A is the right default.** Most founders care that data isn't pooled in
  *our* multi-tenant database — that's the real fear. Sending prompts to *their
  own* Anthropic/OpenAI account, under that vendor's zero-data-retention
  enterprise terms, satisfies the vast majority of buyers and gives the best
  alert quality. The data is processed by one named sub-processor the founder
  already trusts, never by us.
- **B must exist for the strict tier.** Regulated founders (health, finance,
  defense) who need *literal* "no third party, ever" can flip `LLM_MODE=local`
  and run a 70B-class model on their own GPU. Quality drops and they own the
  ops, but the guarantee is absolute. This is a paid/strict SKU, not the default.
- **No code fork.** Both are the same image; only env differs. We never have to
  maintain two products.

## What this means in practice

- We are **never** a data processor for prompt content in Phase 2. In mode A the
  founder's own vendor account processes it; in mode B nothing leaves the host.
- The founder's deployment must disclose its sub-processor: "Mode A sends signal
  content to <Anthropic|OpenAI> under your account's terms." Put this in the
  install guide and the in-app settings.
- Embeddings follow the same switch (cloud OpenAI embeddings, or a local
  embeddings model in mode B).

## Implementation (done)

`backend/coordinator.py` builds its model chain from env at startup:

```
# Mode A — cloud, BYO keys (default)
LLM_MODE=cloud
ANTHROPIC_API_KEY=...            # founder's own
OPENAI_API_KEY=...               # founder's own (fallback)
LLM_PRIMARY_MODEL=claude-sonnet-4-6            # optional overrides
LLM_FALLBACK_MODEL=gpt-4-turbo
LLM_LAST_RESORT_MODEL=claude-haiku-4-5
LLM_EMBED_MODEL=text-embedding-3-small

# Mode B — fully local, data never leaves the host
LLM_MODE=local
LLM_LOCAL_BASE_URL=http://ollama:11434/v1   # any OpenAI-compatible server
LLM_LOCAL_MODEL=llama3.1:70b
LLM_LOCAL_EMBED_MODEL=nomic-embed-text
LLM_LOCAL_API_KEY=local
```

The circular-fallback + bounded-backoff logic is unchanged; mode A gives it a
3-model chain, mode B a single local model. No other code is aware of the mode.

## Open follow-ups
- Mode B reference hardware sizing (which GPU runs 70B at acceptable latency).
- Optionally bundle an `ollama` service in the local-mode compose profile.
- Verify each cloud vendor's zero-retention terms and surface the choice in-app.
