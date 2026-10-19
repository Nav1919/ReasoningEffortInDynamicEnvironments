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
