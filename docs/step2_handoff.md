# Step 2: compare thinking modes fairly

We now save the settings and planned game situations before asking a model.
For the same situation, each mode gets identical user instructions; only its
thinking control changes. Every attempt keeps its answer, failures and measurements.
GPT-OSS is now downloaded and its controls verified, but local attempts timed
out before any usable answer. Main-comparison model selection remains unresolved.

## Try it offline

After the README installation, from the repository root:

```sh
python reasoning_modes.py
python experiment_config.py configs/qwen_boolean.json --ready
python experiment_starts.py configs/qwen_boolean.json
python freeway_study.py plan --config configs/native_effort_draft.json --output logs/native_plan_01 --dry-run
python freeway_study.py summarize --output logs/native_plan_01
python -m unittest discover
```

The native plan has 18 requests, all marked planned. Its summary correctly shows
zero attempted requests and missing partners. These commands need no Ollama.
Use a new output directory each time: old plans/executions are protected.

## Small check with the already installed Qwen model

Ollama must be running and the README's exact model installed:

```sh
python model_provenance.py configs/qwen_boolean.json
python freeway_study.py plan --config configs/qwen_boolean.json --output logs/qwen_check_01
python freeway_study.py execute --output logs/qwen_check_01 --limit 1
python freeway_study.py summarize --output logs/qwen_check_01
```

This attempts one measured frozen-state request plus a separate warm-up.
`execution.json` names every unrun partner; `runs/` contains the full recipe,
rendered requests, actual model/code/start details, and raw response.
`comparison_summary.json` and `comparison_modes.csv` give counts and denominators.
Qwen off/on remains separate from native Low/Medium/High. Legacy bare-runner and
historical study commands remain supported, but new research comparisons must
use saved recipes/plans. Do not label old unconfigured results as controlled runs.

For live games use `configs/qwen_live.json` with the same plan/execute commands,
or the existing runner's `--experiment-config` option. A frozen recipe is rejected
for live gameplay. Summary regeneration makes no model calls; action replay checks
saved moves, not fresh inference. Historical replay remains:

```sh
python replay_freeway.py evidence/freeway_20261008/live_01_seed0_tick2.json.gz
```

## Native pilot: local attempts and next decision

The offline native recipe uses six development situations × three levels, rotated
order, full-board versioned instructions and a shared 2048-token ceiling. It cannot
execute until an exact installed model digest is chosen and passes compatibility.
No evaluation games were played; selectors 5–7 remain reserved.

The authorized GPT-OSS 20B download is complete. On this Apple M3 / 16 GiB Mac,
the first load timed out at 180.081 seconds. A separate longer-load retry loaded
in 109.450 seconds, but its first Low answer timed out at 180.133 seconds.
No Medium/High questions ran, and there are no usable native-model answers.
Both attempts and offline reproduction commands are in the
[saved local evidence](../evidence/gptoss_local_pilot_20261019/README.md).
The model was unloaded; the downloaded weights remain installed.

The proposed API alternative, requiring user approval, is:
`gpt-5.4-mini-2026-03-17`, with a **$1 total spending cap**, no tools or automatic
retries. Its [official model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
lists Low/Medium/High support and that snapshot. No API adapter, API call or
provider substitution has been made; implementing one requires the user's choice.

After authorizing and verifying a practical model/provider, save its exact
identity in a new recipe and generate a new plan. Existing local attempts must
not be overwritten. The API path is not implemented or authorized yet. Summarize without new calls afterward. A timeout stops
further requests; check the server is idle before making a new attempt/folder.

## Files to read

| Files | What they do |
|---|---|
| `reasoning_modes.py`, `model_capabilities.py` | Distinguish switches/levels and reject unsupported controls |
| `experiment_config.py`, `experiment_identity.py` | Validate saved settings and identify matching comparisons |
| `model_provenance.py`, `run_provenance.py`, `experiment_starts.py` | Verify model, source and actual starts |
| `run_records.py`, `decision_records.py` | Keep setup failures, answers and unavailable measurements visible |
| `comparison_plan.py`, `comparison_execution.py`, `frozen_comparison.py` | Plan and execute through existing helpers/live runner |
| `comparison_summary.py`, `comparison_metrics.py` | Match partners, check compatibility and regenerate tables |
| `run_model_freeway.py`, `freeway_study.py` | Existing entry points, extended rather than replaced |

## Review order

These are dependent branches, not alternative implementations. Review each PR
against its named base; after merging a base, retarget its child through GitHub.
PR #9 is still the unmerged foundation. No teammate approval or merge is implied.

| PR | Change | Branch / head commit | Builds on |
|---|---|---|---|
| [#10](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/10) | Keep Qwen on/off separate from Low/Medium/High | `codex/step2-01-modes` / `67d3260` | #9 |
| [#11](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/11) | Reject reasoning levels a model does not support | `codex/step2-02-capabilities` / `4220409` | #10 |
| [#12](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/12) | Read experiment settings from a saved JSON file | `codex/step2-03-config` / `8cfc043` | #11 |
| [#13](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/13) | Keep game instructions identical across thinking modes | `codex/step2-04-requests` / `e1b5050` | #12 |
| [#14](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/14) | Give matching experiments the same comparison ID | `codex/step2-05-identities` / `0a21054` | #13 |
| [#15](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/15) | Check that the installed model matches the saved settings | `codex/step2-06-model-identity` / `6411d6d` | #14 |
| [#16](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/16) | Record which code and simulator produced a result | `codex/step2-07-source-provenance` / `702c0a2` | #15 |
| [#17](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/17) | Keep previously used game starts out of evaluation | `codex/step2-08-seed-splits` / `219f179` | #16 |
| [#18](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/18) | Keep bad answers separate from missing token counts | `codex/step2-09-response-records` / `63e163a` | #17 |
| [#19](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/19) | Save a run record even when model setup fails | `codex/step2-10-setup-logs` / `abf3a53` | #18 |
| [#20](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/20) | Run the existing game loop from saved experiment settings | `codex/step2-11-live-config` / `d243096` | #19 |
| [#21](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/21) | Save the matching game situations and mode order before running | `codex/step2-12-saved-plans` / `c53bfc0` | #20 |
| [#22](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/22) | Run one saved game situation and check the model's choice | `codex/step2-13-frozen-run` / `b701a96` | #21 |
| [#23](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/23) | Execute a saved plan without losing failed or unrun entries | `codex/step2-14-execute-plan` / `989e106` | #22 |
| [#24](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/24) | Show missing comparison partners instead of hiding them | `codex/step2-15-matching-summary` / `976779d` | #23 |
| [#25](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/25) | Report answer quality and missing measurements clearly | `codex/step2-16-summary-metrics` / `ec986fb` | #24 |
| [#26](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/26) | Keep saved plans and command-line runs exactly consistent | `codex/step2-17-plan-consistency` / `a5e89f8` | #25 |
| [#28](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/28) | Load weights without extra warm-up questions | `codex/step2-native-warmup` / `77850aa` | #27 |
| [#29](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/29) | Pin actual GPT-OSS weights and controls | `codex/step2-gptoss-pilot` / `3f9b919` | #28 |
| [#30](https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments/pull/30) | Keep longer loading separate from answer time | `codex/step2-gptoss-load-timeout` / `43c5744` | #29 |

Follow-up fixes stay in their original PRs: `6411d6d` uses metadata GET requests;
`d243096` repairs a parser regression; `c53bfc0` separates frozen/live recipes;
`ec986fb` retains failed setup in summaries and avoids duplicate imported tests.
The final guide PR builds on #26; its current head is visible on GitHub.

## Checked and pending

- [x] 65 offline tests pass, including fake-provider end-to-end failures and missing partners.
- [x] Existing historical summary/replay tests pass; original evidence is unchanged.
- [x] Qwen metadata-only compatibility check passes on installed Ollama 0.35.1.
- [x] Dry-run native plan: exactly 18 entries, zero model calls.
- [x] One real Qwen off-mode check: 1 valid answer / 1 measured request,
  2.965 seconds, plus a separate warm-up. All 35 other runs remain planned.
  Saved locally in `logs/step2_qwen_smoke_20261019/`; this is a workflow check,
  not a native-effort pilot or a model-quality finding.
- [x] GPT-OSS installed and verified; both unsuccessful local attempts preserved.
- [ ] A completed native comparison and main-model selection; API use needs approval.
- [ ] Human review and required checks before merge; no teammate messages were sent.

Reviewers: check request equality, failure/denominator handling, and the README
commands. These checks establish workflow correctness, not model superiority.
Further technical definitions and limitations are in [fair_comparisons.md](fair_comparisons.md).
