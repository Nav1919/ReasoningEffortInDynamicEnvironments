# Fair reasoning-mode comparisons — Step 2

New comparisons will keep observations, user instructions, model artifact and
supported generation settings fixed. Only the explicit reasoning control changes.
Existing Qwen off/on is a boolean comparison; it is not native Low/Medium/High.
A generated-token ceiling is a shared limit, not an effort level.

Offline: `python reasoning_modes.py` lists both definition sets and
`python -m unittest test_reasoning_modes.py` checks them. The historical runner
still sends exactly the same Qwen requests. Definitions alone do not certify
that a selected model supports a control; capability checks follow separately.

This work is stacked above unmerged PR #9, preserving its evidence unchanged.

## Capability checks and model-selection blocker (October 19)

`python model_capabilities.py` lists explicit, evidence-backed profiles.
Qwen uses booleans; GPT-OSS uses low/medium/high. The installed server's
`thinking.values` takes precedence; without it the fallback is restricted to
Ollama 0.35.1 and the verified architecture family. Unknown profiles, levels,
family mismatches and unverified fallback versions fail locally.

Sources: [installed-release thinking documentation](https://github.com/ollama/ollama/blob/v0.35.1/docs/capabilities/thinking.mdx)
and [OpenAI Ollama guide](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama).
The server documentation explicitly warns unsupported named values can default;
we reject them instead. Profile validation alone cannot verify installed weights.

Local audit: Ollama client/server 0.35.1, 16 GiB RAM, about 72 GiB free disk.
Only Qwen models are installed. [GPT-OSS 20B](https://ollama.com/library/gpt-oss:20b)
is listed at about 14 GB and a minimum of roughly 16 GB memory: local execution
is marginal until measured. No download, upgrade, API substitution or pilot calls
were performed. Native-model selection and the 18-request pilot remain blocked
on a resource decision. Offline implementation continues without pretending
Qwen off/on supplies native Low/Medium/High results.

## Explicit recipes

`python experiment_config.py configs/qwen_boolean.json --ready` validates the
existing-model recipe offline. `configs/native_effort_draft.json` is a separate
native design with a null expected digest; `--ready` rejects it until model
selection is resolved. No historical records are assigned these new recipes.
Both use one shared validator and will feed the existing request/study functions.
All effective scientific settings are explicit; unsupported options are rejected.

## Matching instructions

`build_comparison_request` extends the existing runner's request construction;
for a matching observation/interval its requests differ only in `think`.
Qwen changes false/true; native effort changes low/medium/high. Tests compare
entire requests, not just their labels. Provider-internal formatting may differ.
`prompt_record` saves the exact instruction prefix and SHA256 per condition.

The pinned simulator's step/state-builder source was inspected: player moves
before traffic, goal ends immediately, collisions check updated integer cells,
wrapping is delayed, and nonterminal collisions reset traffic. Existing
`progress_source` describes those mechanics correctly, but omitted edge clamps.
New `progress_source_v2` adds only that clarification. Original/progress and the
historical source-corrected template remain unchanged. Frozen diagnostics keep
these same user instructions; their asynchronous wording limits interpretation.
