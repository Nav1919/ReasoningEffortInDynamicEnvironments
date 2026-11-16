# This file describes one Freeway scene in six ways and makes questions about it.
# It reads only the public game observation, so answers and saved game secrets stay out of prompts.
# Import it from the runner; check it with python -m unittest test_stage_a -v.
import json
import math
import random

from freeway_observations import canonical, render

FORMATS = ('grid', 'coordinates', 'prose', 'lane_table', 'relative_positions', 'json')
VERSION = 'stage-a-v1'
RULES = (
    'This is a frozen Freeway observation. Player x=0; lane 0 is start and lane 9 is goal. '
    'Grid columns run from x=-48 to x=48 in steps of 12. All x positions, lengths, '
    'distances and nominal speeds use these same scaled units; lane steps count as 12 '
    'distance units. Reported head_x includes slow-car phase. occupied_x lists actual '
    'whole-cell car positions, including off-board cells. Nominal speed is not a promise '
    'of equal movement each tick. Cars do not use ordinary modulo wrapping. '
    'Distance means Manhattan distance to the nearest occupied car cell, including off-board '
    'cells. Nearby means distance <=24. IDs identify cars within this scene. '
    'Answer the current question only; do not predict future positions. '
)


def read_scene(observation):
    scene = canonical(observation)
    scene['turn'] = observation['state']['game_turn']
    for car in scene['cars']:
        head, length = car['head_x'], car['length']
        if length < 11 or (length + 1) % 12:
            raise ValueError('Expected whole-cell car lengths')
        cell_head = (math.floor(head / 12) if car['direction'] == 'right' else math.ceil(head / 12)) * 12
        toward_tail = -1 if car['direction'] == 'right' else 1
        car['occupied_x'] = [cell_head + toward_tail * 12 * offset for offset in range((length + 1) // 12)]
    return scene


def distance(car, scene):
    return abs(car['lane'] - scene['player']['lane']) * 12 + min(abs(x) for x in car['occupied_x'])


def render_scene(scene, format_name):
    names = dict(zip(FORMATS, ('ascii', 'coordinates', 'prose', 'table', 'relative', 'json')))
    if format_name not in names:
        raise ValueError(f'Unknown representation: {format_name}')
    if format_name == 'json':
        return json.dumps(scene, sort_keys=True)
    text = f"Turn {scene['turn']}.\n" + render(scene, names[format_name])
    text += 'Grid symbols: P=player, C=traffic, X=player and traffic, .=empty.\n' if format_name == 'grid' else ''
    text += 'Whole-cell occupancy (x units, including off-board cells):\n'
    for car in scene['cars']:
        text += f"{car['id']}: occupied_x={car['occupied_x']}\n"
    if format_name == 'lane_table':
        text += 'Distance from player (x units):\n'
        for car in sorted(scene['cars'], key=lambda c: (c['lane'], distance(c, scene), c['id'])):
            text += f"lane={car['lane']} car={car['id']} distance={distance(car, scene)}\n"
    return text


def make_questions(scene, seed):
    rng = random.Random(seed)
    cells = [(lane, x) for lane in range(1, 9) for x in range(-48, 49, 12)]
    occupied = {(c['lane'], x) for c in scene['cars'] for x in c['occupied_x']}
    target = bool(rng.randrange(2))
    choices = [cell for cell in cells if (cell in occupied) == target]
    lane, x = rng.choice(choices or cells)
    cars = scene['cars']
    nearest_distance = min((distance(c, scene) for c in cars), default=None)
    nearest = sorted(c['id'] for c in cars if distance(c, scene) == nearest_distance)
    car = rng.choice(cars) if cars else None
    questions = [
        dict(probe='occupancy', text=f'Is traffic occupying lane {lane}, x={x}?',
             answer={'occupied': (lane, x) in occupied}, schema='{"occupied": true or false}'),
        dict(probe='nearest', text='Which car or cars have the smallest distance to the player? Include all ties.',
             answer={'cars': nearest}, schema='{"cars": ["car IDs"]}; use [] if there are no cars'),
        dict(probe='counting', text='How many distinct cars are nearby (distance <=24)?',
             answer={'count': sum(distance(c, scene) <= 24 for c in cars)}, schema='{"count": integer}'),
    ]
    if car:
        questions.extend([
            dict(probe='motion', text=f"What direction and nominal speed does {car['id']} have?",
                 answer={'direction': car['direction'], 'speed': car['speed']},
                 schema='{"direction": "left" or "right", "speed": integer}'),
            dict(probe='localization', text=f"What is the reported head_x of {car['id']}?",
                 answer={'head_x': car['head_x']}, schema='{"head_x": integer}'),
        ])
    return questions


def make_prompt(scene_text, question):
    instructions = RULES
    if question['probe'] == 'action':
        instructions += (
            'Choose U, D, or S to cross safely and make progress. U increases player lane; '
            'D decreases it; S stays. The player moves first; reaching lane 9 ends immediately. '
            'Otherwise traffic moves and collisions are checked on updated whole cells, '
            'not swept paths. A collision resets the player and traffic. The episode times '
            'out at turn 100. Choose an action for this snapshot, without inference delay. '
        )
    return instructions + '\n\n' + scene_text + '\n\n' + question['text'] + '\nReturn only ' + question['schema']


def score_answer(question, text):
    result = dict(valid=False, correct=False, signed_error=None, absolute_error=None, safe=None)
    try:
        answer = json.loads(text)
    except (ValueError, TypeError):
        return result
    if not isinstance(answer, dict) or set(answer) != set(question['answer']):
        return result
    probe = question['probe']
    if probe == 'occupancy':
        valid = type(answer['occupied']) is bool
    elif probe == 'nearest':
        ids = answer['cars']
        valid = isinstance(ids, list) and all(isinstance(x, str) for x in ids) and len(set(ids)) == len(ids)
    elif probe == 'counting':
        valid = type(answer['count']) is int and answer['count'] >= 0
    elif probe == 'motion':
        valid = answer['direction'] in ('left', 'right') and type(answer['speed']) is int and answer['speed'] > 0
    elif probe == 'localization':
        valid = type(answer['head_x']) is int
    elif probe == 'action':
        valid = isinstance(answer['action'], str) and answer['action'] in ('U', 'D', 'S')
    else:
        raise ValueError(f'Unknown question type: {probe}')
    result['valid'] = valid
    if not valid:
        return result
    if probe == 'nearest':
        result['correct'] = sorted(answer['cars']) == sorted(question['answer']['cars'])
    elif probe == 'action':
        result['correct'] = answer['action'] in question['answer']['action']
        result['safe'] = answer['action'] in question['safe_actions']
    else:
        result['correct'] = answer == question['answer']
    if probe == 'localization':
        error = answer['head_x'] - question['answer']['head_x']
        result.update(signed_error=error, absolute_error=abs(error))
    return result
