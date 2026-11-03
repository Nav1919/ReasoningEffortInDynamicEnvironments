# Weekly Project Tracker — Reasoning Effort in Dynamic Environments

**Team:** Pranav Panicker · Akash Wudali · Shohini Rhea Sarkar  
**Schedule:** One task per person due Tuesday and one due Thursday; Monday is a progress discussion, **not** a task.  
**Capacity:** Plan each task for about 3–4 hours, plus a one-hour check-in and review (approximately 8–10 hours per person weekly).  
**Start:** Thursday, September 17, 2026 (launch and shared decisions). First task due Tuesday, September 22. Last planned handoff Thursday, December 10. Confirm actual course submission deadlines before relying on the final date.

## High-level direction

We will test whether an LLM agent playing [RealtimeGym's Freeway](https://github.com/SALT-NLP/RealtimeGym) should always act quickly, always reason longer, or use a small router that considers difficulty, how quickly traffic changes, and how old its current view is. Freeway asks the agent to cross changing traffic using U (up), D (down), or S (stay). The observation is the information Freeway shows the agent about the current game. We start with measured quick-versus-deliberate results, test whether changing traffic and older views alter that tradeoff, propose competing simple routing rules, and compare frozen policies on new starts. Then we validate the findings and write/present the paper.

**Terms:** One *frozen model* is one specific LLM selected in Week 1 and kept the same across policies (no training, fine-tuning, or swapping). *Quick* and *deliberate* are two recorded reasoning/output-budget settings for that model, not separate models. Tokens measure text processed/generated; seconds measure elapsed time. More thinking may help the action but costs compute and lets Freeway change. A *matched start* means compared policies face the same recorded seed/game situation. A *held-out start* is never used to change router rules. RealtimeGym offers token or wall-clock time-pressure controls; verify the actual effect of each setting rather than assuming it changes world volatility.

**Scope:** Freeway only, one frozen LLM, two selected difficulties, measured pressure settings, one fixed older-view condition, fixed quick/deliberate baselines, simple adaptive policies, and simulator-derived evaluation. Do not assume a learned volatility estimator, additional environments, fine-tuning, reinforcement learning, or an LLM judge are part of the core work.

**Working rule:** Tuesday tasks must not need another Tuesday task to finish first. Thursday tasks may consume Tuesday artifacts. Keep one shared runner and a recorded configuration/seed manifest. Link each task to its GitHub Issue and submit code or docs through a reviewed PR. Each Monday meeting reviews the previous Thursday's **result and pivot decision** before new work starts. Check off a task only when its output is linked or committed; pilot figures are explicitly labeled preliminary.

## Weekly direction and tasks
### Week 1 · Sep 21–24, 2026 — Can the same LLM play Freeway quickly and deliberately?

**Thursday result:** A small quick-versus-deliberate pilot table and a labeled first figure; not yet a paper claim.

**Monday check-in (discussion, not a task):** Sep 21: Select one accessible model, agree on what quick and deliberate will mean, and assign reviewers.

**Tuesday direction:** Make the first fair Freeway comparison possible.

**Pranav — Make Freeway usable**

- [ ] Download RealtimeGym, install it, and run its supplied Freeway example.
- [ ] Save one actual game observation (the description of current player and traffic positions); identify how the example sends U (up), D (down), or S (stay), and what the game reports afterward.
- [ ] **Why:** Akash needs a verified game example before attaching an LLM. **Output:** Add tested installation commands, actions, example log, and blockers to the README.

**Akash — Choose one model and define two reasoning modes**

- [ ] Name the single LLM the team can access and afford; never commit credentials.
- [ ] Specify exactly how quick versus deliberate will differ (for example, permitted output/reasoning budget), and what stays identical; state how to record response tokens and elapsed seconds.
- [ ] **Why:** Using the same model isolates the effect of reasoning effort. **Output:** Commit a model decision note with two proposed configurations and cost/latency recording instructions.

**Rhea — Design the first pilot**

- [ ] Choose a few recorded Freeway starts and fields to log: start/seed, game setting, mode, action, game outcome, tokens, seconds.
- [ ] Write a prediction about when deliberate might help and when waiting might hurt.
- [ ] **Why:** The first runs need an explicit question. **Output:** Commit a one-page pilot plan and empty results table.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Prove Freeway runs can be repeated**

- [ ] Repeat the supplied example on recorded settings or seeds; save several observation → action → outcome sequences.
- [ ] Check a teammate can follow the README commands.
- [ ] **Why:** One lucky run is not reproducible evidence. **Output:** Commit short logs, repeatable commands, and any README corrections.

**Akash — Run the first quick/deliberate pilot**

- [ ] After Pranav's Tuesday installation is verified, connect the selected model so it chooses U, D, or S.
- [ ] Run both reasoning settings on the same small set of starts; log actions, outcomes, tokens, seconds, and failures.
- [ ] **Why:** We need the first measurement of performance versus decision cost. **Output:** Commit runner commands, raw logs, and a side-by-side pilot table.

**Rhea — Plot and interpret the pilot**

- [ ] Plot game outcome by mode and show measured time/token use and sample sizes.
- [ ] Record failures and decide the most useful Week 2 change; label the finding preliminary.
- [ ] **Why:** Even an inconclusive pilot should steer the next experiment. **Output:** Commit one labeled figure and a next-experiment memo.


### Week 2 · Sep 28–Oct 1, 2026 — Does a faster-changing Freeway punish waiting?

**Thursday result:** A manipulation check and a pilot outcome chart across time-pressure settings.

**Monday check-in (discussion, not a task):** Sep 28: Review Week 1 data and choose feasible pressure settings.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Measure the effect of game speed**

- [ ] Use RealtimeGym's documented time-pressure controls at two or three settings; measure how much the game advances during equal reasoning intervals.
- [ ] Predict which setting should make long decisions least useful.
- [ ] **Why:** We must show that 'world speed' is actually different. **Output:** Commit tested settings, a state-change table, and the prediction.

**Akash — Automate baseline runs**

- [ ] Create commands for quick and deliberate runs that accept setting and seed.
- [ ] Automatically log action, outcome, output tokens, elapsed seconds, and failures.
- [ ] **Why:** Consistent records make experiments comparable. **Output:** Commit two run commands and example result files.

**Rhea — Define an observation-to-action change check**

- [ ] Compare actual game logs to identify what the model saw and what changed by the time its action executed.
- [ ] Write what that check measures and does not prove.
- [ ] **Why:** Long latency alone does not establish that traffic changed consequentially. **Output:** Commit a metric definition and two worked examples.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Validate the speed manipulation**

- [ ] Repeat the change measurement at every selected setting and graph game progress.
- [ ] Document any setting that fails to create distinct traffic movement.
- [ ] **Why:** All later pressure claims depend on a real manipulation. **Output:** Commit a labeled state-change plot and run commands.

**Akash — Compare modes under pressure**

- [ ] Run quick and deliberate on matching starts at each pressure setting; keep the model and difficulty fixed.
- [ ] Record incomplete runs rather than replacing them silently.
- [ ] **Why:** This tests whether extra reasoning loses value as Freeway changes faster. **Output:** Commit raw results and an outcome/time table by pressure.

**Rhea — Make the Week 2 result and pivot decision**

- [ ] Plot outcome and observation-to-action change by mode and setting.
- [ ] Decide whether to keep the conditions, adjust them, or repair the measurement.
- [ ] **Why:** The team should not scale a non-informative pilot. **Output:** Commit a figure and a short keep/change decision.


### Week 3 · Oct 5–8, 2026 — Does game difficulty change when extra reasoning is worthwhile?

**Thursday result:** A matched difficulty × pressure comparison with where quick or deliberate wins.

**Monday check-in (discussion, not a task):** Oct 5: Choose two Freeway difficulties and a feasible run count from measured costs.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Validate easy and harder Freeway settings**

- [ ] Run examples at two selected difficulty levels and explain the visible difference in actual observations.
- [ ] Confirm changing difficulty does not unintentionally change pressure; predict which combinations favor deliberate.
- [ ] **Why:** A router should weigh harder decisions against a moving world. **Output:** Commit example observations, a six-condition table, and a prediction.

**Akash — Collect quick-mode reference data**

- [ ] Run quick on recorded starts for both difficulty levels at every chosen pressure.
- [ ] Log settings, costs, game outcomes, and missing runs.
- [ ] **Why:** Quick mode is the reference for measuring the value of more thought. **Output:** Commit raw quick results and a coverage table.

**Rhea — Prepare matched comparison analysis**

- [ ] Write code that pairs quick and deliberate by the same start and condition.
- [ ] Define a figure of outcome difference plus token/time cost and variation across starts.
- [ ] **Why:** Unmatched traffic starts could explain fake performance differences. **Output:** Commit analysis code, pairing checks, and a figure template.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Explain representative traffic sequences**

- [ ] Inspect straightforward and difficult trajectories across pressure settings.
- [ ] Use stated selection rules and annotate when traffic moved during decisions.
- [ ] **Why:** Examples can explain the quantitative trend without cherry-picking. **Output:** Commit annotated trajectories and selection criteria.

**Akash — Collect matching deliberate results**

- [ ] Run deliberate on the same recorded starts and conditions as Tuesday's quick results.
- [ ] Check which pairs are complete and document failures.
- [ ] **Why:** This completes the fair reasoning-effort comparison. **Output:** Commit deliberate raw records and a pairing audit.

**Rhea — Produce the first main comparison figure**

- [ ] Plot deliberate-minus-quick game outcome by difficulty and pressure; show counts and uncertainty.
- [ ] State where deliberate helps, hurts, or shows no clear difference.
- [ ] **Why:** The router needs regions where a choice genuinely matters. **Output:** Commit a main figure and a wins/losses memo.


### Week 4 · Oct 12–15, 2026 — Does acting on an older view of traffic create a distinct failure?

**Thursday result:** A fresh-versus-delayed experiment, with checked delays and an outcome plot.

**Monday check-in (discussion, not a task):** Oct 12: Choose one delay and a subset of informative Week 3 conditions.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Provide a current or older game view**

- [ ] Make Freeway supply either its present observation or one from an agreed earlier moment, holding other settings fixed.
- [ ] Show an actual current/older pair and the traffic state at action time.
- [ ] **Why:** We need to isolate stale information from general slow thinking. **Output:** Commit the setting, examples, and tests.

**Akash — Connect both modes to both views**

- [ ] Run quick and deliberate with both current and older observations.
- [ ] Confirm model, prompts/budgets, and game starts stay fixed for a matched pair.
- [ ] **Why:** Observation age should be the intended difference. **Output:** Commit four verified run configurations and smoke-test logs.

**Rhea — Define an outdated-action indicator**

- [ ] Implement a check for relevant traffic change between the supplied view and action.
- [ ] Test it on known changed and unchanged examples; predict where delay matters.
- [ ] **Why:** A measured mechanism strengthens the paper beyond reward alone. **Output:** Commit metric code, unit tests, and a prediction.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Audit observation age**

- [ ] Inspect current/older pairs and verify actual ages and action-time game state.
- [ ] List any mismatched or unusable pairs.
- [ ] **Why:** An old-view experiment fails if the view was not old. **Output:** Commit a delay-validation table with examples.

**Akash — Run paired current/older experiments**

- [ ] Compare quick and deliberate on the same starts in selected conditions.
- [ ] Log age, outcome, cost, and every missing pair.
- [ ] **Why:** This tests whether freshness changes the best reasoning mode. **Output:** Commit raw paired runs and a coverage table.

**Rhea — Show the freshness result**

- [ ] Plot outcome and outdated-action rate by observation condition and mode.
- [ ] Decide from observed evidence whether a look-again choice belongs in the router.
- [ ] **Why:** A new router option must address a real measured failure. **Output:** Commit a figure and a yes/no decision with reasoning.


### Week 5 · Oct 19–22, 2026 — Can simple rules choose reasoning effort better than always quick or always deliberate?

**Thursday result:** A first head-to-head pilot of fixed modes and three routing rules on the same starts.

**Monday check-in (discussion, not a task):** Oct 19: Each person presents a hypothesis; agree on one shared runner and allowed decision-time inputs.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Propose a world-speed rule**

- [ ] Implement a quick/deliberate choice using difficulty and pressure but not observation age in the shared runner.
- [ ] State a prediction and show choices on five example game situations.
- [ ] **Why:** This tests whether world speed alone explains useful adaptation. **Output:** Commit the rule, example decisions, tests, and prediction.

**Akash — Propose a difficulty-only rule**

- [ ] Implement a quick/deliberate choice using difficulty alone in the same runner.
- [ ] Show its choices on the five common situations and predict when extra tokens will be wasted.
- [ ] **Why:** A standard adaptive-compute explanation should be challenged fairly. **Output:** Commit the rule, example decisions, tests, and prediction.

**Rhea — Propose a freshness-aware rule**

- [ ] Implement a small rule using difficulty, pressure, and age of last view; permit quick, deliberate, or a new view before choosing.
- [ ] Show decisions on the five common situations and predict when looking again pays off.
- [ ] **Why:** This is the proposed contribution, which must justify extra complexity. **Output:** Commit the rule, example decisions, tests, and prediction.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Pilot the speed rule**

- [ ] Run it on agreed common starts and compare with both fixed modes.
- [ ] Count its quick versus deliberate choices by pressure.
- [ ] **Why:** We need measured evidence for the speed hypothesis. **Output:** Commit matching records, an outcome table, and a choice plot.

**Akash — Pilot the difficulty-only rule**

- [ ] Run it on the same starts; record reward, tokens, and seconds.
- [ ] Compare its costs against both fixed modes.
- [ ] **Why:** A simpler policy may obtain the same gain at less complexity. **Output:** Commit matching records and a reward-versus-cost figure.

**Rhea — Pilot and compare all rules**

- [ ] Run the freshness rule on the shared starts, counting refresh decisions.
- [ ] Put all three rules and both fixed modes in one table with failures and costs.
- [ ] **Why:** This is the first evidence of whether freshness-aware routing is promising. **Output:** Commit a common comparison figure and a Week 6 investigation decision.


### Week 6 · Oct 26–29, 2026 — Why do the rules fail, and which versions are ready for a new-start test?

**Thursday result:** Three diagnosed failure cases, limited revisions, and frozen rules.

**Monday check-in (discussion, not a task):** Oct 26: Set aside new starts for Week 7; agree each person may change one rule condition using development starts only.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Investigate speed-rule mistakes**

- [ ] Find cases where pressure routing chose quick but deliberate did better, or the reverse; identify a shared pattern.
- [ ] Change one threshold and compare before/after on development starts.
- [ ] **Why:** Diagnosed errors are stronger than arbitrary tuning. **Output:** Commit mistake table, one revision, and before/after outcomes.

**Akash — Investigate wasted compute**

- [ ] Find cases where difficulty routing spent more tokens without better game outcome.
- [ ] Change one rule condition and remeasure outcome versus compute on development starts.
- [ ] **Why:** A useful router should avoid paying for unnecessary thought. **Output:** Commit mistake table, one revision, and cost/benefit comparison.

**Rhea — Investigate unnecessary or missed refreshes**

- [ ] Find examples where freshness routing looked again unnecessarily or missed a useful refresh.
- [ ] Change one observation-age/refresh condition on development starts.
- [ ] **Why:** Refreshing can consume time and must solve a defined failure. **Output:** Commit mistake table, one revision, and refresh/outcome comparison.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Freeze the revised speed rule**

- [ ] Run the revision on common development starts and report strongest/weakest conditions.
- [ ] Record exact rule inputs and threshold.
- [ ] **Why:** Week 7 needs a fixed, fair speed-aware comparator. **Output:** Commit results and a dated frozen-rule specification.

**Akash — Freeze the revised difficulty rule**

- [ ] Run on the same development starts, reporting outcome and tokens/seconds.
- [ ] Record exact allowed input and threshold.
- [ ] **Why:** The simpler adaptive baseline must also be fixed before new-start testing. **Output:** Commit results and a dated frozen-rule specification.

**Rhea — Freeze the proposed freshness rule**

- [ ] Run on those same starts and compare against all fixed and adaptive policies.
- [ ] Record final decision rules, refresh cost handling, and reserved Week 7 starts.
- [ ] **Why:** An honest generalization test cannot tune on its evaluation data. **Output:** Commit comparative figure and dated frozen-policy/evaluation record.


### Week 7 · Nov 2–5, 2026 — Do fixed routing rules help on Freeway starts not used to improve them?

**Thursday result:** Main held-out policy comparison with costs, sample sizes, and uncertainty.

**Monday check-in (discussion, not a task):** Nov 2: Lock held-out starts, conditions, run count, primary outcomes, and figure; no rule changes after seeing results.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Test the world-speed hypothesis on new starts**

- [ ] Run always quick, always deliberate, and frozen speed-aware rule across held-out pressure settings.
- [ ] Check the prewritten prediction that speed routing helps most when the game changes fastest.
- [ ] **Why:** This independently tests the value of environmental speed. **Output:** Commit raw records, coverage table, and pressure-stratified comparison.

**Akash — Test difficulty adaptation and compute costs**

- [ ] Run frozen difficulty-only routing on the same held-out starts.
- [ ] Measure outcome, tokens, and seconds against fixed modes; report missing starts.
- [ ] **Why:** We must know if ordinary difficulty adaptation already solves the problem. **Output:** Commit raw records, coverage table, and outcome-versus-cost table.

**Rhea — Test the freshness-aware rule on new starts**

- [ ] Run the frozen freshness rule on those same starts and conditions.
- [ ] Record outcome, time/tokens, every refresh decision, and failures.
- [ ] **Why:** This is the direct test of the project's proposed method. **Output:** Commit raw records, coverage table, and router-choice table.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Explain the actual pressure result**

- [ ] Verify game-state change remains distinct by pressure setting in held-out runs.
- [ ] Plot how the speed-aware policy does at each setting, including losses.
- [ ] **Why:** The speed claim needs validated environmental change. **Output:** Commit manipulation figure and conditional policy results.

**Akash — Explain quality versus cost**

- [ ] Put fixed and adaptive outcomes alongside tokens and seconds.
- [ ] Identify conditions where more reasoning did not improve the game.
- [ ] **Why:** A reward gain with much higher cost is not an unqualified win. **Output:** Commit cost–performance figure with sample counts.

**Rhea — Make the main paper comparison**

- [ ] Pair outcomes from identical starts; show variation and uncertainty.
- [ ] Report all policies and conditions where the proposed rule loses.
- [ ] **Why:** The paper's claim must match the full held-out evidence. **Output:** Commit primary figure, numerical table, and defensible interpretation.


### Week 8 · Nov 9–12, 2026 — Which router inputs matter, and does the result survive complete games?

**Thursday result:** Two feature-removal experiments, short full-game results, and a research evidence package.

**Monday check-in (discussion, not a task):** Nov 9: Lock ablation conditions and full-game starts before examining their outcomes.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Remove pressure information**

- [ ] Copy the frozen freshness rule but deny it the pressure setting; hold everything else fixed.
- [ ] Run the full and pressure-blind rules on matching starts.
- [ ] **Why:** If results remain unchanged, speed awareness may not explain the gain. **Output:** Commit paired ablation records and the exact rule change.

**Akash — Remove the look-again option**

- [ ] Copy the frozen freshness rule but prevent it from requesting a new view; retain its other inputs.
- [ ] Run both rules on matching starts and record time/tokens saved.
- [ ] **Why:** This tests whether refreshing adds value beyond choosing thought length. **Output:** Commit paired ablation records and cost table.

**Rhea — Plan full-game validation**

- [ ] Choose a modest fixed list of complete Freeway starts and the strongest simple comparator from Week 7.
- [ ] Define episode-level outcomes and an analysis table before running.
- [ ] **Why:** A rule may win isolated decisions yet fail across an entire game. **Output:** Commit full-game manifest, commands, and analysis template.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Explain the pressure-blind ablation**

- [ ] Plot full versus pressure-blind routing by game-speed setting.
- [ ] Include places where removing speed had no effect.
- [ ] **Why:** This tests a causal explanation for the routing gain. **Output:** Commit figure, caption, and plotting command.

**Akash — Explain no-refresh and run complete games**

- [ ] Plot full versus no-refresh policy and account for refresh cost.
- [ ] Run Rhea's fixed complete-game manifest for the selected policies, retaining failed episodes.
- [ ] **Why:** The mechanism and full-trajectory behavior need direct evidence. **Output:** Commit ablation figure, full-game logs, and coverage/cost table.

**Rhea — Assemble the research claim-to-evidence map**

- [ ] Summarize full-game outcomes, main policy comparison, and both ablations.
- [ ] Match each planned paper claim to a figure/table and list contrary results.
- [ ] **Why:** The team must know exactly what the data can honestly support. **Output:** Commit full-game figure and a results handoff for testing and writing.


### Week 9 · Nov 16–19, 2026 — Can we trust and reproduce our results before writing the paper?

**Thursday result:** Passing tests, checked comparisons and figures, and one dated validated result set.

**Monday check-in (discussion, not a task):** Nov 16: Review the claim-to-evidence map; each person names the result they trust least.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Audit Freeway behavior**

- [ ] Rerun environment, difficulty, pressure, delayed-view, and refresh tests.
- [ ] Spot-check saved runs against their stated settings and game transitions.
- [ ] **Why:** A policy result is unreliable if Freeway behaved differently from the Methods description. **Output:** Commit validation checklist, commands, test results, and needed corrections.

**Akash — Audit agent and policy comparisons**

- [ ] Check matched starts, model/settings, permitted policy inputs, logged tokens/seconds, and failed-run handling.
- [ ] Reproduce several saved comparison rows from the recorded commands.
- [ ] **Why:** Policies must differ only in the decision rule under test. **Output:** Commit reproduced rows, discrepancy list, and test report.

**Rhea — Audit figures and claims**

- [ ] Regenerate figures from raw records and check counts, labels, uncertainty, and excluded runs.
- [ ] Classify each proposed claim as supported, uncertain, or unsupported.
- [ ] **Why:** The paper must not overstate its evidence. **Output:** Commit regenerated figures and an analysis audit.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Fix confirmed environment defects**

- [ ] Repair verified environment/timing/refresh bugs and add regression tests.
- [ ] Identify result cells affected by any code change.
- [ ] **Why:** A repaired bug must be tested and traced to affected evidence. **Output:** Commit fixes, passing tests, and a rerun list.

**Akash — Repair or rerun affected comparisons**

- [ ] Fix confirmed runner/logging bugs and rerun affected starts under original settings.
- [ ] Keep corrected and original records identifiable; report remaining failures.
- [ ] **Why:** Changed numbers must have a transparent reason. **Output:** Commit corrected records, coverage audit, and change log.

**Rhea — Freeze validated results version 1**

- [ ] Recreate figures/tables after corrections and reconcile the claim-to-evidence map.
- [ ] Record sample counts, limitations, and version date.
- [ ] **Why:** Drafting needs a single trustworthy result set. **Output:** Commit dated results-v1 index with figures, tables, and limitations.

### Thanksgiving buffer · Nov 23–29, 2026

**Monday, Nov 23 (optional discussion, not a task):** Confirm the validated results and Week 10 writing ownership. There are no Tuesday/Thursday assigned deliverables this week: UMD Thanksgiving break runs Nov 25–29, and Thursday, Nov 26 is Thanksgiving. Use the week only for an actual course deadline or needed recovery; do not silently count it as a six-task sprint.

### Week 10 · Nov 30–Dec 3, 2026 — Can we tell the complete research story in one draft?

**Thursday result:** A complete paper draft with figures, citations, methods, results, and explicit limitations.

**Monday check-in (discussion, not a task):** Nov 30: Agree on central claim, paper outline, section ownership, and who integrates the document.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Draft Freeway and experiment Methods**

- [ ] Explain game objective, chosen difficulty/pressure/old-view settings, and manipulation checks in ordinary language.
- [ ] Add actual configuration table and cite RealtimeGym.
- [ ] **Why:** Readers must know what the game did and what was controlled. **Output:** Commit environment/methods draft and configuration table.

**Akash — Draft model, policies, and reproduction Methods**

- [ ] Name the actual frozen model and quick/deliberate settings; define fixed and simpler routing baselines.
- [ ] Explain matched starts, logging, exact commands, and cost measurement.
- [ ] **Why:** Readers must separate routing gains from model and budget differences. **Output:** Commit agents/baselines methods draft and reproducibility table.

**Rhea — Draft introduction and proposed method**

- [ ] Write motivation and research questions from results-v1, not expected gains.
- [ ] Explain freshness-aware inputs, quick/deliberate/refresh decisions, held-out design, and one worked routing example.
- [ ] **Why:** The contribution needs a precise, approachable claim. **Output:** Commit introduction and proposed-method draft.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Draft environmental results and limitations**

- [ ] Explain pressure and older-view figures, including weak or failed conditions.
- [ ] Identify limitations of the Freeway-only test.
- [ ] **Why:** The paper needs evidence the freshness problem was measurable. **Output:** Commit results paragraphs linked to figures and a limitations paragraph.

**Akash — Draft policy outcomes and costs**

- [ ] Explain main policy comparison and feature-removal experiments alongside token/time tradeoffs.
- [ ] Check every stated number against results-v1.
- [ ] **Why:** Quality and compute are both part of the research question. **Output:** Commit comparison/ablation results paragraphs and checked figure list.

**Rhea — Integrate one full draft**

- [ ] Merge all sections, add full-game results, related work, conclusion, citations, and figure references.
- [ ] Flag contradictory or missing explanations for both teammates to review.
- [ ] **Why:** A complete draft reveals problems isolated sections hide. **Output:** Commit one complete paper draft and a specific review-request list.


### Week 11 · Dec 7–10, 2026 — Is the paper, code, and presentation ready for submission?

**Thursday result:** Reviewed paper, final slides, runnable demo, passing tests, and navigable repo links.

**Monday check-in (discussion, not a task):** Dec 7: Everyone reads the complete draft and names factual errors, unclear figures, and rubric gaps.

**Tuesday direction:** Complete the inputs needed for the week's experiment.

**Pranav — Review technical accuracy**

- [ ] Check Freeway, timing, delay, refresh, and code-unit descriptions against code and results.
- [ ] Run setup and relevant tests from documented commands on a clean setup if feasible.
- [ ] **Why:** A clear paper is not enough if implementation claims are wrong. **Output:** Commit technical review comments and reproducibility checklist.

**Akash — Review experimental accuracy**

- [ ] Verify every baseline, sample size, figure number, ablation claim, and cost statement against results-v1.
- [ ] Run tests and check that proposed slides show the same findings.
- [ ] **Why:** Paper and slides must report the same measured experiment. **Output:** Commit evidence review, test report, and figure corrections.

**Rhea — Review narrative and rubric coverage**

- [ ] Read as a newcomer: trace question → baseline tradeoff → router → held-out result → limits.
- [ ] Check required report/presentation items, code documentation, and unit-test inventory.
- [ ] **Why:** The submission must make a coherent argument and meet course requirements. **Output:** Commit editorial review and assigned rubric-gap checklist.

**Thursday direction:** Show the week's result and explicitly decide what it implies for next week.

**Pranav — Finalize environment documentation**

- [ ] Address technical review comments and link code units to their unit tests.
- [ ] Update README navigation, verified install commands, and validation instructions.
- [ ] **Why:** A researcher should be able to obtain and inspect the experiment. **Output:** Commit tested documentation and code/test inventory.

**Akash — Finalize reproducible runs and demo**

- [ ] Address runner review; verify test command and full baseline/controller run guide.
- [ ] Record one short Freeway demo showing a router choice and outcome.
- [ ] **Why:** The distributed code must visibly do what the paper claims. **Output:** Commit run guide, passing-test record, and short demo or trajectory.

**Rhea — Finalize paper and slides**

- [ ] Integrate peer reviews, references, figures, and captions.
- [ ] Prepare final slides covering question, methods, evidence, router, findings, and limitations; link submission artifacts from README.
- [ ] **Why:** The result must be communicated consistently across every deliverable. **Output:** Commit submission-ready paper and presentation links.

## Weekly result log

At every Monday discussion, add a link to last Thursday's figure, table, validated result, or paper draft, followed by one sentence saying what it showed and the decision for next week. Keep missing runs and negative findings visible.

| Week | Thursday output / PR / Issue links | What did we learn? | Keep, change, or investigate? |
|---|---|---|---|
| 1 | _Add link_ | _Add result_ | _Add decision_ |
| 2 | _Add link_ | _Add result_ | _Add decision_ |
| 3 | _Add link_ | _Add result_ | _Add decision_ |
| 4 | _Add link_ | _Add result_ | _Add decision_ |
| 5 | _Add link_ | _Add result_ | _Add decision_ |
| 6 | _Add link_ | _Add result_ | _Add decision_ |
| 7 | _Add link_ | _Add result_ | _Add decision_ |
| 8 | _Add link_ | _Add result_ | _Add decision_ |
| 9 | _Add link_ | _Add result_ | _Add decision_ |
| 10 | _Add link_ | _Add result_ | _Add decision_ |
| 11 | _Add link_ | _Add result_ | _Add decision_ |

## Evidence-backed publication checkpoint — October 17, 2026

- [x] Scripted Freeway baseline and asynchronous Ollama runner exist.
- [x] Frozen-state pilot: 135 responses / 15 situations; see
  [report](freeway_timing_study.md) and [raw evidence](../evidence/freeway_20261008/README.md).
- [x] Matched live pilot: five seeds at 1/2/4 seconds per turn; saved crossing
  counts 0/5, 2/5, 2/5, with complete per-seed records.
- [x] Offline replay and relocated summary-regeneration tests exist;
  see [README commands](../README.md).
- [x] Fresh isolated dependency installation on the same Mac; all 11 tests pass.
- [ ] Installation on another machine/operating system.
- [ ] Human PR approval and merge of this publication work.
- [ ] Freshness-aware routing, refresh experiments, held-out comparisons and ablations.

This checkpoint does not mark the planned weekly research tasks complete.
Earlier checkboxes/result placeholders remain as planning history. Evidence here
supports a preliminary runner/pilot milestone, not a validated controller result.
