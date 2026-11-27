"""Turn a Freeway observation into a reasoning trace.

The observer is not the decision model. It writes reasoning only; it does not
choose or execute U / D / S. The runner later reveals this text to the actor.

Import: `from decision_model_experiments.observer_agent import ObserverAgent`
Call: `ObserverAgent(client, max_tokens=x).think(observation) -> str`
`think` returns thinking plus content so a Qwen think-on call with empty
`content` still yields a revealable trace. `observer.last_result` is the
full `GenerationResult` for tokens, latency, and failures.

Tests: `python -m unittest tests.test_observer_agent -v`
"""

import copy
import json

def convert_scalar(value):
    # Observations can contain NumPy scalars; JSON needs plain Python values.
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def build_observer_prompt(observation, board="full", max_tokens=None):
    # Same Freeway mechanics as the live runner, but ask for reasoning only.
    # Do not request an action letter; the actor, not this agent, chooses U/D/S.
    # The trace is cut off at the token budget and read from the first word
    # while cars move, so the opening must already name the next step.
    if isinstance(observation, str):
        observation_text = observation
    else:
        snapshot = copy.deepcopy(observation)
        if board == "structured" and isinstance(snapshot, dict):
            snapshot.pop("state_string", None)
        observation_text = json.dumps(snapshot, default=convert_scalar)
    budget = ""
    if max_tokens is not None:
        budget = f"The token budget is {int(max_tokens)} tokens. "
    return (
        "The objective is to CROSS, not to survive at the starting line. "
        "Staying forever loses at turn 100. Reason about making upward "
        "progress when possible; S or D can be useful when traffic requires "
        "it. S is not automatically safe in a traffic lane. Waiting forever "
        "for a perfectly certain crossing fails. "
        "Play Freeway. Reason about the current situation only; "
        "do not choose an action letter. "
        "Reach y=9 from y=0 while avoiding cars in lanes y=1 through y=8. "
        "U increases player y by 1; D decreases it by 1; S leaves it unchanged. "
        "The player stays at x=0. player_states is player y. "
        "Each car_states entry is [lane_y, head_x, direction, speed, length]. "
        "Positions, speed, and length use units of 1/12 of a board column. "
        "Speed is the positive distance moved per turn. "
        "For right-moving cars the tail is head_x-length; "
        "for left-moving cars it is head_x+length. Cars wrap around the board. "
        "The player moves before cars move and collisions are checked. "
        "A collision resets the player and traffic to their starting layout. "
        "Score starts at 100 and falls by 1 each turn. "
        "The episode ends on reaching the goal or after 100 turns. "
        "Time is limited. "
        + budget
        + "This reasoning is cut off when the token budget runs out, "
        "and it is read from the first word while the world steps and cars move. "
        "Later sentences are often never seen, and they describe a board that "
        "has already changed. "
        "The observation is one moment of a changing environment. "
        "Cars move on every step while this reasoning is read, so say in the "
        "opening that the conclusion is about moving traffic and can go stale "
        "before a later sentence is used. "
        "The first sentence must say whether moving up, staying, or moving down "
        "is the useful next step, and must name the deciding car by lane_y, "
        "direction, head_x, and speed. "
        "In state_string the first line is y=9 and the last line is y=0; "
        "P on the last line is the start. "
        "Do not spend the opening restating the goal, re-deriving that "
        "orientation, or planning how to parse the board. "
        "Judge the next turn only: the player moves first, then each car moves "
        "by its speed. The step is safe when no car body covers x=0 in the lane "
        "the player will occupy after the cars move. "
        "Write reasoning only. Do not output U, D, or S as a chosen action.\n\n"
        "Observation:\n"
        + observation_text
        + "\n\nStart with that next step, the deciding car, and the fact that "
        "the environment is still changing. The rest may be cut off."
    )


def reasoning_trace(result):
    """Text the runner reveals. Qwen with thinking on writes into `thinking`
    first; `content` is often empty when `x` is small or the budget hits
    `length`. Use both, thinking first, and do not drop a truncated trace.
    """
    if result is None:
        return ""
    parts = []
    thinking = (result.thinking or "").strip()
    content = (result.content or "").strip()
    if thinking:
        parts.append(thinking)
    if content:
        parts.append(content)
    return "\n".join(parts)


class ObserverAgent:
    """Generate a reasoning trace from one Freeway observation."""

    def __init__(self, client, max_tokens, thinking=True, board="full"):
        self.client = client
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.board = board
        self.last_result = None

    def think(self, observation) -> str:
        """Ask the reasoning model for a trace. Return thinking and/or content."""
        prompt = build_observer_prompt(
            observation, board=self.board, max_tokens=self.max_tokens,
        )
        self.last_result = self.client.call_reasoning_model(
            prompt, max_tokens=self.max_tokens, think=self.thinking,
        )
        # Keep last_result for logging. Do not parse U/D/S from this text.
        return reasoning_trace(self.last_result)