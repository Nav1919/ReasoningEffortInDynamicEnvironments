"""Explicit Ollama reasoning controls; run `python reasoning_modes.py` to list.

Token ceilings are separate generation limits, never native reasoning levels.
Tests: test_reasoning_modes.py. No provider or network access.
"""
import copy
import json

QWEN_MODES = {name: {'control': 'boolean', 'value': value}
              for name, value in [('off', False), ('on', True)]}
NATIVE_MODES = {name: {'control': 'effort', 'value': name}
                for name in ['low', 'medium', 'high']}


def thinking_value(mode):
    """Validate one explicit mode and return its provider think value."""
    if not isinstance(mode, dict) or set(mode) != {'control', 'value'}:
        raise ValueError('Mode requires exactly control and value')
    control, value = mode['control'], mode['value']
    if control == 'boolean' and type(value) is bool:
        return value
    if control == 'effort' and value in ('low', 'medium', 'high'):
        return value
    raise ValueError('Expected a boolean control or native low/medium/high effort')


def modes_for(control):
    """Return independent definitions so callers cannot mutate shared modes."""
    if control not in ('boolean', 'effort'):
        raise ValueError('Unknown reasoning control')
    return copy.deepcopy(QWEN_MODES if control == 'boolean' else NATIVE_MODES)


if __name__ == '__main__':
    print(json.dumps({'qwen': modes_for('boolean'), 'native': modes_for('effort')}, indent=2))
