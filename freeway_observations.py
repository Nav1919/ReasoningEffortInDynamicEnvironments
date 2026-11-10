"""Canonical observable Freeway state and six deterministic text renderers.

Preview: python freeway_observations.py --file data/freeway_scenarios.json --id 0
Inputs: existing bank observation only; outputs: text, never simulator labels.
Validation: python -m unittest test_freeway_observations -v. See docs/stage-a.md.
"""
import argparse
import json
from pathlib import Path

VERSION = 'stage-a-observation-v1'
FORMATS = ('ascii', 'coordinates', 'prose', 'table', 'relative', 'json')
FIELDS = ('id', 'lane', 'head_x', 'direction', 'speed', 'length')
CONVENTIONS = ('Player x=0; lane 0 is start, lane 9 is goal. '
               'Head x is the simulator observable coordinate; grid column j '
               'has x=12*(j-4). Length is the reported extent. '
               'Tail x=head_x-length for rightward cars, head_x+length for leftward cars. '
               'Speed is the reported motion magnitude per tick. '
               'Do not assume modulo wrap or constant displacement on each tick.')


def canonical(observation):
    """Whitelist state_builder fields; never inspect the snapshot or answer key."""
    state = observation['state']
    player = int(state['player_states'])
    if not 0 <= player <= 8:
        raise ValueError('Expected nonterminal player lane 0..8')
    cars = []
    # Stable IDs follow the observable car list, including slots for absent cars.
    # They identify objects within this frozen state, not across reset episodes.
    for index, item in enumerate(state['car_states']):
        lane, head, direction, speed, length = item
        if head is None:
            if any(value is not None for value in item[2:]):
                raise ValueError('Partially absent car')
            continue
        if direction not in ('left', 'right') or not 1 <= lane <= 8:
            raise ValueError('Invalid car lane or direction')
        if speed <= 0 or length < 0:
            raise ValueError('Invalid car geometry or speed')
        cars.append(dict(zip(FIELDS, (f'C{index:02d}', int(lane), int(head),
                                     direction, int(speed), int(length)))))
    return dict(version=VERSION, player=dict(x=0, lane=player), cars=cars)


def footprint(car):
    """Observable closed head-to-tail extent; not a next-tick collision oracle."""
    head = car['head_x']
    tail = head + car['length'] * (1 if car['direction'] == 'left' else -1)
    return min(head, tail), max(head, tail)


def render(view, representation):
    if representation not in FORMATS:
        raise ValueError(f'Unknown representation: {representation}')
    header = f"{VERSION}\n{CONVENTIONS}\nPlayer: x=0 lane={view['player']['lane']}\n"
    cars = view['cars']
    if representation == 'json':
        body = json.dumps(view, sort_keys=True, separators=(',', ':'))
    elif representation == 'coordinates':
        body = '(id,lane,head_x,direction,speed,length)\n' + '\n'.join(
            str(tuple(car[key] for key in FIELDS)) for car in cars)
    elif representation == 'table':
        body = '| ' + ' | '.join(FIELDS) + ' |\n'
        body += '| ' + ' | '.join(['---'] * len(FIELDS)) + ' |\n'
        body += '\n'.join('| ' + ' | '.join(str(car[key]) for key in FIELDS) + ' |'
                          for car in cars)
    elif representation == 'prose':
        lines = []
        for lane in range(10):
            entries = [f"{c['id']} has head x={c['head_x']}, direction {c['direction']}, "
                       f"speed {c['speed']}, length {c['length']}"
                       for c in cars if c['lane'] == lane]
            lines.append(f"Lane {lane}: " + ('; '.join(entries) or 'no cars') + '.')
        body = '\n'.join(lines)
    elif representation == 'relative':
        body = 'Offsets from player; positive lane offset points toward goal.\n'
        body += '\n'.join(
            f"{c['id']}: dx={c['head_x']}, dlane={c['lane']-view['player']['lane']}, "
            f"direction={c['direction']}, speed={c['speed']}, length={c['length']}"
            for c in cars)
    else:
        # Keep all nine indexed cells, all ten lanes, overlaps and stable IDs.
        # Exact metadata retains subcell positions and off-board heads that a
        # cell drawing alone would discard. No hidden timer is consulted.
        lines = ['lane/column | ' + ' | '.join(map(str, range(9)))]
        for lane in reversed(range(10)):
            cells = []
            for column in range(9):
                x = 12 * (column-4)
                labels = [c['id'] for c in cars if c['lane'] == lane
                          and footprint(c)[0] <= x <= footprint(c)[1]]
                if lane == view['player']['lane'] and column == 4:
                    labels.append('P')
                cells.append(','.join(labels) or '.')
            lines.append(f'{lane} | ' + ' | '.join(cells))
        lines.append('Exact object metadata (including off-board heads):')
        lines.extend(' '.join(f'{key}={c[key]}' for key in FIELDS) for c in cars)
        body = '\n'.join(lines)
    return header + body + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--id', type=int, default=0)
    parser.add_argument('--format', choices=FORMATS)
    args = parser.parse_args()
    # Preview reads existing observations only and does not restore a simulator.
    bank = json.loads(args.file.read_text())
    record = next(s for s in bank['scenarios'] if s['id'] == args.id)
    view = canonical(record['observation'])
    for name in (args.format,) if args.format else FORMATS:
        print(f'=== {name} ===\n{render(view, name)}')


if __name__ == '__main__':
    main()
