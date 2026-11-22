# Research Questions

---

## The short version

Small AI language models (the kind you can run on a single graphics card, not the giant ones behind commercial chatbots) are bad at playing games where the world keeps moving while they think. We want to find out exactly *where* in their decision-making they go wrong, try a simple fix for each problem, and then check whether diagnosing the problem first leads to a better game-playing agent than applying fixes blindly. We'll also run the same tests on two larger commercial models, to see whether the problems shrink, change, or stay the same as models get bigger.

---

## Some background

### The game

We use a game called **Freeway**. It's simple: a chicken starts at the bottom of the screen and has to cross several lanes of traffic to reach the top. Cars move left or right at different speeds, and when a car reaches one edge of the screen, it reappears on the other side. On each turn, the player can move **up**, move **down**, or **stay** where it is. Getting hit by a car is bad; getting to the top is good.

Freeway is part of a collection of games called RealtimeGym, built by researchers at Stanford to study exactly the problem we care about: what happens when an AI has to make decisions while the world keeps going. In these games, the cars don't pause while the AI is thinking. If the AI takes too long, it falls behind, and by the time it decides, the situation may have changed.

### The models

We test two kinds of models.

**Small, freely available models.** Our main subject is the **Qwen3.5** family from Alibaba, released in March 2026, which is currently the strongest family of small open models. We use three sizes, **2 billion, 4 billion, and 9 billion parameters**, so we can see how the results change as the model gets bigger while everything else stays the same. ("Parameters" is a rough measure of a model's size.) These models have a "thinking mode," where they write out their reasoning before giving an answer. That often helps on hard problems, but it also takes time, which matters a lot in a game where the cars keep moving. We run all three sizes with thinking off, and the 4B model with thinking on as well.

**Larger commercial models.** To see how much of the problem is about size, we also test two low-cost commercial models that we reach through their companies' online services: **DeepSeek V4.1 Flash** and **OpenAI's GPT-5 mini**. Both are much larger than our small models and both reason before answering. DeepSeek also connects our work to the Stanford study, which used DeepSeek models. Because these services charge per use, we run them on a smaller set of situations than the small models (details below).

### Why this is interesting

When a model loses at Freeway, we usually only see the end result: the chicken got hit. That doesn't tell us *why*. Did the model misread where the cars were? Did it guess wrong about where they'd be next? Did it figure out the right move but pick a different one anyway? Did it just repeat what it did last turn? Each of these is a different problem with a different fix, and knowing which one is happening is the first step toward building something better.

### How we can tell what went wrong

The game is a computer simulation, so we always know the right answer. For any moment in the game, the simulator can tell us exactly where every car is, where each car will be in one, two, or eight turns, and which moves are safe. We call this the **answer key**. It lets us check each step of the model's thinking separately, instead of only checking whether it survived.

We also saved 500 game situations ahead of time (snapshots of the board at a particular moment), sorted into types: situations where moving up is safe, situations where waiting is better, situations where the chicken needs to step back, and a few other dangerous cases. We'll use 300 of these to explore and tune, and keep 200 hidden until the very end for the final test, so we can't accidentally tune our approach to the test.

---

## How we think about a model's decision

We break each decision into four steps:

1. **Seeing.** Read the board and figure out where the cars are.
2. **Predicting.** Work out where the cars will be over the next few turns.
3. **Acting.** Pick a move based on that prediction.
4. **Not getting stuck in a rut.** Make that choice based on the current board, not just on what it did in the last few turns.

A model can fail at any of these steps, and a failure early on (like misreading the board) will ruin everything after it. Our questions are organized around these four steps.

---

## The three big questions

### Question 1: Where do models break down?

This is the diagnosis. We test each of the four steps on its own, using the answer key to score the model.

**1a. Can the model see the board correctly?** We'll ask simple questions like "Which car is closest to you?" and "Is there a car in this spot?" We'll also try describing the board in three different ways (a text picture of the grid, a table listing each lane, and a plain list of car positions) to see whether some formats are easier for the model to read. A good answer would look something like: *"The table format is much easier for the smallest model to read, but the larger models do fine with any format."*

**1b. How far ahead can the model predict?** We'll ask the model where specific cars will be one turn from now, two turns from now, and so on up to eight turns. We expect predictions to get worse the further ahead it has to look; what we want to know is how quickly that happens, where the errors start (for example, when a car wraps around to the other side of the screen), and whether thinking mode helps. A good answer: *"The 4B model predicts accurately for about two turns, then falls apart. With thinking mode, it stays accurate for about four."*

**1c. Does the model act on its own predictions?** We'll ask the model to choose a move in three ways: with no prediction given, with its own earlier prediction in front of it, and with the correct prediction from the answer key in front of it. If it still picks bad moves even when handed the right prediction, the problem isn't seeing or predicting; it's turning knowledge into action. A good answer: *"Even with the correct prediction in front of it, the model chooses a dangerous move 30% of the time."*

**1d. Does the model get stuck repeating itself?** We'll show the model the same board several times, each time with a different made-up history of what it supposedly did before: always staying, always moving up, or its real past moves. If the history changes what it does on an identical board, it's being swayed by its past rather than the present. We'll also check how often that change leads to an unsafe move. A good answer: *"After a history of staying put, the model stays 40% more often, even when moving up is safe."*

**1e. Which step is the biggest problem, and does that change with size?** For each step, we'll quietly give the model the correct answer for that step only (the true car positions, or the true predictions, and so on) and see how much its final moves improve. The step where getting the right answer helps the most is the one holding the model back the most. We'll compare this across the three Qwen3.5 sizes, with thinking mode on and off, and against the two commercial models. A good answer: *"For the 2B model, prediction is the biggest problem. For the 9B model and both commercial models, it's acting on the prediction."*

**Why Question 1 matters on its own:** Even if nothing else in this project works, knowing where models break, and how that changes with size, gives anyone building game-playing agents (or any agent that works in a changing environment) a clear place to focus.

---

### Question 2: Can each problem be fixed cheaply?

For each step, we've designed one or two simple fixes that don't involve retraining the model; they only change what the model is shown or how its answer is used.

- **For seeing:** describe the board in whichever format the model reads best, or have it restate the nearby cars before choosing a move.
- **For predicting:** tell the model the exact rule for how cars move, or have it write a small piece of code that calculates the positions and run that code for it.
- **For acting:** have the model write out only its prediction, and let a simple, fixed rule pick the safest move from that prediction.
- **For getting stuck:** replace the list of its past moves with a short summary of how the board has changed.

We test each fix by itself and ask four things.

**2a. Does the fix help the step it's aimed at?** If we fix prediction, do predictions actually get better? We'll measure the same scores from Question 1 before and after.

**2b. Does it lead to better moves?** A fix can improve one step without improving the final decision; for example, better predictions won't help if the model ignores them. We'll measure how often the model picks a safe move, before and after.

**2c. What does it cost?** Every fix makes the model read or write more, and in a real-time game, extra writing means extra delay. We'll count how much extra text (measured in "tokens," roughly word fragments) each fix adds to every decision.

**2d. Does fixing one problem reveal another?** Once prediction is fixed, maybe acting becomes the new weak point. We'll rerun the measurement from 1e with each fix turned on to see whether the biggest problem moves somewhere else.

**Why Question 2 matters:** It tells us which fixes are worth using and what they cost, which is what someone would need to know to actually build a better agent.

---

### Question 3: Does diagnosing first produce a better agent?

This is the end product of the project. We're building a tool that, given any model, runs the tests from Question 1, works out which steps are weakest, picks the matching fixes from Question 2, and assembles an improved agent. Question 3 asks whether that's actually better than simpler approaches.

**3a. Is diagnosis better than guessing?** We'll compare four versions of each model on the 200 hidden situations: the model with no fixes, the model with the fixes our diagnosis picked, the model with the same number of fixes picked at random, and the model with every fix turned on. If the diagnosis-picked version doesn't beat random picks, the diagnosis isn't adding anything.

**3b. Is it a good trade between accuracy and speed?** Turning on every fix will probably give the best moves, but it will also be the slowest. We want to know whether the diagnosis-picked fixes get close to that accuracy while adding much less delay, because in a real-time game, a slightly less accurate decision made quickly can beat a perfect one made too late.

**3c. Does the diagnosis correctly predict which fix will help?** If the diagnosis says "prediction is the biggest problem," does the prediction fix really help the most? We'll compare the diagnosis's ranking (from the exploration situations) with which fix actually helped most on the 200 hidden ones.

**3d. Does it hold up in real play?** Everything above uses frozen snapshots of the board. As a final check, we'll run full games with the small models, where the cars keep moving while the model thinks, and compare how often each version crosses safely and how often it gets hit.

**3e. Does diagnose-then-fix help big models too, or only small ones?** We'll run the same diagnosis and fixes on the two commercial models. If they benefit as much as the small models, the method is general. If they don't, that tells us these problems mostly go away with size, and the method matters most for small models.

**Why Question 3 matters:** It's the difference between "here's an analysis of what goes wrong" and "here's a method that makes agents better." If diagnosis-first works, it's a recipe others can apply to their own models and games.

---

## What we're deliberately *not* trying to answer

To keep the project focused, we're leaving these out:

- **A full ranking of commercial models.** We test two low-cost commercial models to see how results change with size, not to find the best one.
- **Retraining or fine-tuning models.** Every fix works by changing what the model sees or how its answer is used.
- **Other games.** We plan to add a second game (Snake) after this first round, but not now.
- **Prompt wording in general.** We only test the three board formats in 1a.
- **Live games with the commercial models.** Their response times depend on how busy the company's servers are, which we can't control, so they're tested on frozen board snapshots only.

---

## How we'll run things

These settings stay the same across every experiment, so results can be compared fairly.

**Small models.** Qwen3.5 at 2B, 4B, and 9B parameters with thinking mode off, plus Qwen3.5 4B with thinking mode on. If time allows, we'll add the 0.8B model. All run at full precision on rented graphics cards (RunPod) using vLLM, a standard tool for running these models. We record the exact software version for every run.

**Commercial models.** DeepSeek V4.1 Flash and GPT-5 mini, reached through their companies' online services. GPT-5 mini's reasoning effort is set to "low" to keep its thinking length closer to our small models' and to control cost. We record exactly which model version each service reports. These run on 150 of the 300 exploration situations and all 200 hidden ones, once each rather than three times, to stay within budget.

**Thinking limit.** In thinking mode, the small model gets up to about 2,000 tokens of reasoning, plus up to 512 tokens for its answer. If it runs out of room before finishing, we record that it was cut off and count the answer as wrong. Running out of time is a real failure in a real-time game. For the commercial models, we record how many reasoning tokens they used on every answer.

**Turning thinking on and off.** We switch Qwen3.5's thinking mode on or off explicitly for every request, never relying on the default, and check that answers with thinking off contain no reasoning.

**Randomness.** These models have some built-in randomness in what they write. For the small models, we use the settings Qwen recommends on its model page for each mode (for thinking mode: temperature 1.0, top-p 0.95, top-k 20, presence penalty 1.5), record the exact values in our configuration files, and run every test three times with different random seeds.

**Unreadable answers.** If a model's answer can't be understood or is cut off, the chicken stays put, and the answer counts as a mistake. We don't throw these out.

**Earlier pilot results.** We ran a small pilot earlier with an older model (Qwen3 4B) and different software (Ollama). Those results aren't mixed with these.

**Budget.** We expect to spend about $20–35 on rented graphics cards and $20–40 on the commercial models, under $100 in total.

---

## How we'll judge the results

**Scoring a move.** A move counts as correct if the answer key says it's safe. We'll report this overall and for each type of situation (safe to advance, better to wait, need to step back).

**How the diagnosis picks fixes.** Using only the exploration situations, we rank the four steps by how much giving the model the right answer helps (question 1e). We turn on the fix for every step whose improvement is above a cutoff. We choose that cutoff using the exploration situations only, preferring fewer fixes when there's a tie. Then we lock the cutoff and the list of fixes before looking at the 200 hidden situations.

**Comparisons on the hidden situations.** For every model, we compare: no fixes; diagnosis-picked fixes; the same number of fixes picked at random (averaged over 10 random draws); every fix turned on; and, purely as a reference for the best possible result, whichever single fix happened to do best.

**Measuring uncertainty.** For every comparison, we report a 95% confidence interval, calculated by resampling the situations 1,000 times. Every version of a model is tested on the same situations with the same random seeds, so the comparisons are fair. Because the commercial models run once per situation, their intervals will be wider, and we'll say so. We report every comparison listed here, whether or not the result is what we hoped for.

**What we leave out.** Only situations where no move is safe, and we'll say how many there were. Nothing else is excluded.

---

## Changes

*None yet. Any change made after experiments begin will be listed here with the date and the reason.*
