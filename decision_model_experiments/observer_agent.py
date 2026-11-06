"""Turn a Freeway observation into a reasoning trace.

The observer is not the decision model. It writes reasoning only; it does not
choose or execute U / D / S. The runner later reveals this text to the actor.

Import: `from decision_model_experiments.observer_agent import ObserverAgent`
Call: `ObserverAgent(client, max_tokens=x).think(observation) -> str`
`observer.last_result` is the full `GenerationResult` for tokens, latency, and failures.

Tests: `python -m unittest tests.test_observer_agent -v`
"""

import copy
import json

def convert_scalar(value):
    # Observations can contain NumPy scalars; JSON needs plain Python values.
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def build_observer_prompt(observation, board="full"):
    # Same Freeway mechanics as the live runner, but ask for reasoning only.
    # Do not request an action letter; the actor, not this agent, chooses U/D/S.
    if isinstance(observation, str):
        observation_text = observation
    else:
        snapshot = copy.deepcopy(observation)
        if board == "structured" and isinstance(snapshot, dict):
            snapshot.pop("state_string", None)
        observation_text = json.dumps(snapshot, default=convert_scalar)
    return (
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
        "Write reasoning only. Do not output U, D, or S as a chosen action.\n\n"
        "Observation:\n"
        + observation_text
    )


class ObserverAgent:
    """Generate a reasoning trace from one Freeway observation."""

    def __init__(self, client, max_tokens, thinking=True, board="full"):
        self.client = client
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.board = board
        self.last_result = None

    def think(self, observation) -> str:
        """Ask the reasoning model for a trace. Return the reply text only."""
        prompt = build_observer_prompt(observation, board=self.board)
        self.last_result = self.client.call_reasoning_model(
            prompt, max_tokens=self.max_tokens, think=self.thinking,
        )
        # Keep last_result for logging. Do not parse U/D/S from this text.
        return self.last_result.content