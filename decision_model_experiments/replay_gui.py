"""Pygame step debugger for a verified decision-model ReplayTrace.

Launch through `python -m decision_model_experiments.replay EPISODE.json`.
Inputs: verified simulator snapshots and saved prompts/results. Output: a
resizable, read-only Freeway window with before/after views and scrollable text.
No network, inference, filesystem writes, or sprite assets are needed. Text is
wrapped for display only; ReplayTrace retains the exact strings in the log.
Tests: tests/test_decision_replay.py (dummy SDL rendering and input events).
Controls and verification limits: decision_model_experiments/replay.md.
"""

import math

from decision_model_experiments.experiment_runner import draw_freeway_surface


# Keep navigation independent of SDL so seeking and playback boundaries can be
# checked without a desktop. A selected step always owns its prompt and action;
# changing the board phase never changes the selected model call.
class ReplayCursor:
    def __init__(self, count):
        self.count = count
        self.index = 0
        self.after = False
        self.playing = False
        self.interval = 1.0

    def seek(self, index):
        self.index = max(0, min(max(self.count - 1, 0), index))

    def advance(self):
        if self.index + 1 >= self.count:
            self.playing = False
        else:
            self.seek(self.index + 1)


class ReplayWindow:
    """Render the existing Freeway GUI alongside readable saved trace panels."""

    BACKGROUND = (17, 23, 34)
    PANEL = (26, 35, 49)
    TEXT = (231, 237, 247)
    MUTED = (164, 181, 202)
    ACCENT = (85, 211, 179)
    WARNING = (255, 183, 109)
    TABS = ("Actor prompt", "Reasoning", "Observer prompt", "Outputs", "State", "Episode")

    def __init__(self, trace, filename, size=(1400, 900)):
        import pygame
        pygame.init()
        self.pg = pygame
        self.trace = trace
        self.filename = filename
        self.cursor = ReplayCursor(len(trace.episode["steps"]))
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption(f"Freeway trace replay | {filename}")
        self.ui_font = pygame.font.SysFont("sans", 19)
        self.title_font = pygame.font.SysFont("sans", 27, bold=True)
        self.text_size = 18
        self.text_font = pygame.font.SysFont("monospace", self.text_size)
        self.tab = "Actor prompt" if self.cursor.count else "Episode"
        self.scroll = 0
        self.running = True
        self.buttons = []
        self._text_cache = None
        self._panels_cache = None
        self._last_advance = 0
        self.draw()

    def _label(self, text, position, color=None, font=None):
        self.screen.blit((font or self.ui_font).render(str(text), True, color or self.TEXT), position)

    def _button(self, text, rect, callback, active=False):
        pygame = self.pg
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.screen, (42, 88, 88) if active else (43, 56, 75), rect, border_radius=6)
        image = self.ui_font.render(text, True, self.TEXT)
        self.screen.blit(image, image.get_rect(center=rect.center))
        self.buttons.append((rect, callback))

    def _select_tab(self, tab):
        self.tab = tab
        self.scroll = 0

    def _seek(self, index):
        self.cursor.seek(index)
        self.cursor.playing = False
        self.scroll = 0

    def _play(self):
        if self.cursor.count == 0:
            return
        if self.cursor.playing:
            self.cursor.playing = False
            return
        if self.cursor.index == self.cursor.count - 1:
            self.cursor.seek(0)
        self.cursor.playing = True
        self._last_advance = self.pg.time.get_ticks()

    def _toggle_phase(self):
        self.cursor.after = not self.cursor.after

    def _speed(self):
        choices = (2.0, 1.0, 0.5, 0.25)
        self.cursor.interval = choices[(choices.index(self.cursor.interval) + 1) % len(choices)]

    def _next_issue(self):
        for index in range(self.cursor.index + 1, self.cursor.count):
            step = self.trace.step(index)
            if step["collision"] or step.get("source") == "fallback" or (step.get("actor_result") or {}).get("error"):
                self._seek(index)
                return

    def _change_font(self, change):
        self.text_size = max(12, min(30, self.text_size + change))
        self.text_font = self.pg.font.SysFont("monospace", self.text_size)
        self.scroll = 0

    def _wrapped(self, text, width):
        # Monospace wrapping preserves indentation and explicit newlines, keeps
        # ASCII boards aligned, and splits unusually long model words/JSON keys.
        key = (text, width, self.text_size)
        if self._text_cache is not None and self._text_cache[0] == key:
            return self._text_cache[1]
        columns = max(1, width // self.text_font.size("M")[0])
        lines = []
        for line in text.expandtabs(4).split("\n"):
            while len(line) > columns:
                boundary = line.rfind(" ", 0, columns + 1)
                if boundary < columns // 3:
                    boundary = columns
                lines.append(line[:boundary])
                line = line[boundary:]
                if line.startswith(" "):
                    line = line[1:]
            lines.append(line)
        self._text_cache = (key, lines)
        return lines

    def draw(self):
        pygame = self.pg
        width, height = self.screen.get_size()
        self.buttons = []
        self.screen.fill(self.BACKGROUND)
        cursor = self.cursor
        step = self.trace.step(cursor.index)
        cycle = self.trace.cycle(cursor.index)
        settings = self.trace.episode["settings"]
        self._label("Freeway / trace replay", (20, 14), font=self.title_font)
        filename = self.filename
        while filename and self.ui_font.size(filename)[0] > width - 450:
            filename = filename[:-1]
        self._label(filename, (420, 23), self.MUTED)
        status = "Transitions verified" if self.trace.states else "No game state recorded"
        self._label(f"{status}  |  mode: {settings['context_mode']}  |  seed: {self.trace.episode.get('requested_seed')}",
                    (20, 55), self.ACCENT)
        error = self.trace.episode["summary"].get("error")
        self._label("Recorded episode error - see Episode tab" if error else
                    "Offline replay / original model text / no inference", (20, 81),
                    self.WARNING if error else self.MUTED)

        # The board is exactly the sprite-free renderer used in the live runner.
        # Snapshots come from verified raw simulator state, avoiding an inaccurate
        # conversion of the model's interpolated car_states coordinates.
        state = self.trace.state(cursor.index, cursor.after)
        board_x, board_y = 20, 153
        cell = max(20, min(48, (height - 380) // 10))
        left_width = max(400, 9 * cell + 20)
        self._label("AFTER ACTION" if cursor.after else "BEFORE ACTION", (board_x, 121), self.ACCENT)
        if state is not None:
            label = "GOAL REACHED" if self.trace.episode["summary"].get("success") else "TIME LIMIT"
            board = draw_freeway_surface(state, cell_size=cell, terminal_label=label)
            self.screen.blit(board, (board_x, board_y))
        else:
            self._label("Episode failed before reset.", (board_x, board_y + 30), self.WARNING)
        detail_y = board_y + 10 * cell + 14
        if step:
            action = {"U": "UP", "D": "DOWN", "S": "STAY"}[step["action"]]
            self._label(f"Step {cursor.index + 1} / {cursor.count}  |  action: {step['action']} ({action})",
                        (board_x, detail_y), font=self.title_font)
            self._label(f"Source: {step.get('source', 'not recorded')}  |  score after: {step['score']:g}",
                        (board_x, detail_y + 34))
            self._label(f"Collision: {'YES' if step['collision'] else 'no'}  |  terminal: {step['done']}",
                        (board_x, detail_y + 60), self.WARNING if step["collision"] else self.MUTED)
            cycle_text = f"Observer cycle: {cycle['id']}" if cycle else "Observer: unused"
            self._label(f"{cycle_text}  |  revealed: {step.get('revealed_token_count', 0)}",
                        (board_x, detail_y + 86), self.MUTED)
        else:
            self._label("No actor steps recorded", (board_x, detail_y), self.WARNING)

        panel_x = left_width + 30
        panel_width = width - panel_x - 20
        for index, name in enumerate(self.TABS):
            tab_width = (panel_width - 12) // 3
            rect = (panel_x + (index % 3) * (tab_width + 6), 118 + (index // 3) * 39,
                    tab_width, 33)
            self._button(name, rect, lambda tab=name: self._select_tab(tab), name == self.tab)
        self.text_rect = pygame.Rect(panel_x, 204, panel_width, height - 330)
        pygame.draw.rect(self.screen, self.PANEL, self.text_rect, border_radius=8)
        if self._panels_cache is None or self._panels_cache[0] != cursor.index:
            self._panels_cache = (cursor.index, self.trace.panels(cursor.index))
        text = self._panels_cache[1][self.tab]
        lines = self._wrapped(text, panel_width - 32)
        line_height = self.text_font.get_linesize() + 3
        visible = max(1, (self.text_rect.height - 24) // line_height)
        self.max_scroll = max(0, len(lines) - visible)
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        for offset, line in enumerate(lines[self.scroll:self.scroll + visible]):
            self._label(line, (panel_x + 12, self.text_rect.y + 12 + offset * line_height),
                        font=self.text_font)
        if self.max_scroll:
            track = pygame.Rect(self.text_rect.right - 8, self.text_rect.y + 8, 3, self.text_rect.height - 16)
            thumb_height = max(16, track.height * visible // len(lines))
            thumb_y = track.y + (track.height - thumb_height) * self.scroll // self.max_scroll
            pygame.draw.rect(self.screen, self.ACCENT, (track.x, thumb_y, 3, thumb_height))
        self._label(f"Lines {self.scroll + 1}-{min(self.scroll + visible, len(lines))} / {len(lines)}   |   wheel / PgUp / PgDn   |   +/- text size",
                    (panel_x, self.text_rect.bottom + 8), self.MUTED)

        # A seek bar provides random access with collision/fallback markers. The
        # last action can be viewed before or after, including its terminal board.
        self.timeline = pygame.Rect(20, height - 82, width - 40, 12)
        pygame.draw.rect(self.screen, (58, 71, 90), self.timeline, border_radius=4)
        for index, item in enumerate(self.trace.episode["steps"]):
            if item["collision"] or item.get("source") == "fallback":
                x = self.timeline.x + round(self.timeline.width * index / max(cursor.count - 1, 1))
                pygame.draw.line(self.screen, self.WARNING, (x, self.timeline.y), (x, self.timeline.bottom), 2)
        x = self.timeline.x + round(self.timeline.width * cursor.index / max(cursor.count - 1, 1))
        pygame.draw.circle(self.screen, self.ACCENT, (x, self.timeline.centery), 7)
        y = height - 56
        for label, x, w, callback in (
            ("|<", 20, 40, lambda: self._seek(0)),
            ("Prev", 66, 60, lambda: self._seek(cursor.index - 1)),
            ("Pause" if cursor.playing else "Play", 132, 65, self._play),
            ("Next", 203, 60, lambda: self._seek(cursor.index + 1)),
            (">|", 269, 40, lambda: self._seek(cursor.count - 1)),
            ("After" if not cursor.after else "Before", 321, 80, self._toggle_phase),
            (f"{1 / cursor.interval:g} step/s", 413, 100, self._speed),
            ("Next issue", 525, 110, self._next_issue),
        ):
            self._button(label, (x, y, w, 32), callback)
        self._label("Arrows step / Space play / B phase / Esc close", (650, y + 6), self.MUTED)
        pygame.display.flip()

    def handle_event(self, event):
        pygame = self.pg
        cursor = self.cursor
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(1140, event.w), max(760, event.h)), pygame.RESIZABLE)
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll -= event.y * 3
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.timeline.inflate(0, 14).collidepoint(event.pos):
                fraction = max(0, min(1, (event.pos[0] - self.timeline.x) / self.timeline.width))
                self._seek(round(fraction * max(cursor.count - 1, 0)))
            else:
                for rect, callback in self.buttons:
                    if rect.collidepoint(event.pos):
                        callback()
                        break
        elif event.type == pygame.KEYDOWN:
            commands = {
                pygame.K_ESCAPE: lambda: setattr(self, "running", False),
                pygame.K_LEFT: lambda: self._seek(cursor.index - 1),
                pygame.K_RIGHT: lambda: self._seek(cursor.index + 1),
                pygame.K_HOME: lambda: self._seek(0),
                pygame.K_END: lambda: self._seek(cursor.count - 1),
                pygame.K_SPACE: self._play,
                pygame.K_b: self._toggle_phase,
                pygame.K_n: self._next_issue,
                pygame.K_UP: lambda: setattr(self, "scroll", self.scroll - 3),
                pygame.K_DOWN: lambda: setattr(self, "scroll", self.scroll + 3),
                pygame.K_PAGEUP: lambda: setattr(self, "scroll", self.scroll - 20),
                pygame.K_PAGEDOWN: lambda: setattr(self, "scroll", self.scroll + 20),
                pygame.K_EQUALS: lambda: self._change_font(2),
                pygame.K_PLUS: lambda: self._change_font(2),
                pygame.K_MINUS: lambda: self._change_font(-2),
                pygame.K_TAB: lambda: self._select_tab(self.TABS[(self.TABS.index(self.tab) + 1) % len(self.TABS)]),
            }
            command = commands.get(event.key)
            if command:
                command()

    def run(self):
        clock = self.pg.time.Clock()
        try:
            while self.running:
                for event in self.pg.event.get():
                    self.handle_event(event)
                now = self.pg.time.get_ticks()
                if self.cursor.playing and now - self._last_advance >= math.ceil(self.cursor.interval * 1000):
                    self.cursor.advance()
                    self.scroll = 0
                    self._last_advance = now
                self.draw()
                clock.tick(30)
        finally:
            self.pg.display.quit()
