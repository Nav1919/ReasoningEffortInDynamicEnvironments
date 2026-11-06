"""Choose a Freeway action from a runner-built context.

The actor is the decision model. It does not know the experimental
`context_mode`; the runner already assembled the context string.

Import: `from decision_model_experiments.actor_agent import ActorAgent`
Call: `ActorAgent(client).act(context) -> "U"|"D"|"S"`
`actor.last_result` is the full `GenerationResult` for tokens, latency, and failures.
`actor.last_action_source` is `"actor"` on a parsed letter, otherwise `"fallback"`.

Tests: `python -m unittest tests.test_actor_agent -v`
"""

from decision_model_experiments.models import parse_action


FALLBACK_ACTION = "S"


def build_actor_prompt(context):
    # Ask for a single executable letter. Do not mention context_mode; the
    # runner already chose what to put in `context`. Omit wall-clock tick
    # language because this experiment is discrete token-reveal, not latency.
    return (
        "Play Freeway. Choose one action: U (up), D (down), or S (stay). "
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
        "Return only U, D, or S.\n\n"
        "Context:\n"
        + context
    )


class ActorAgent:
    """Choose U / D / S from a built context string."""

    def __init__(self, client, max_tokens=8, fallback_action=FALLBACK_ACTION):
        if fallback_action not in {"U", "D", "S"}:
            raise ValueError("fallback_action must be U, D, or S")
        self.client = client
        self.max_tokens = max_tokens
        self.fallback_action = fallback_action
        self.last_result = None
        self.last_action_source = None

    def act(self, context: str) -> str:
        """Ask the instant model for one action. Fall back to S if invalid."""
        prompt = build_actor_prompt(context)
        # Thinking stays off for the actor unless a later experiment changes this call.
        self.last_result = self.client.call_instant_model(
            prompt, max_tokens=self.max_tokens, think=False,
        )
        parsed = parse_action(self.last_result.response, self.last_result.error)
        if parsed is None:
            # Preserve the failed or unparsable reply; the environment still needs an action.
            self.last_action_source = "fallback"
            return self.fallback_action
        self.last_action_source = "actor"
        return parsed