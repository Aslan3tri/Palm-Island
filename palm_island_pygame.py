#!/usr/bin/env python3
"""Palm Island solo interface built with Pygame.

Run this file from any working directory. It imports the rules engine from
``palm_island_solo.py`` and reads the supplied card sheets in ``assets``.
No individual card image files are created.
"""

import random
from dataclasses import dataclass
from pathlib import Path

import pygame

import palm_island_solo as core


BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
LEADERBOARD_PATH = BASE_DIR / "Leaderboard.txt"
ACHIEVEMENTS_PATH = BASE_DIR / "Achievements.txt"

ATLAS_WIDTH = 3300
ATLAS_HEIGHT = 3824
ATLAS_COLUMNS = 5
CARD_WIDTH = 660
CARD_HEIGHT = 956
FEAT_X_CUTS = (0, 717, 1434, 2152, 2869, 3586)
FEAT_Y_CUTS = (0, 1039, 2078)
RULE_PAGE_SPREADS = tuple((page, page + 1) for page in range(2, 18, 2)) + ((30, 31),)

FPS = 60
WINDOW_SIZE = (1600, 900)

BG = (17, 37, 43)
BG_LIGHT = (25, 55, 62)
PANEL = (29, 61, 68)
PANEL_DARK = (22, 46, 52)
CREAM = (249, 239, 210)
MUTED = (172, 193, 191)
GOLD = (230, 185, 83)
GREEN = (69, 169, 110)
YELLOW = (219, 170, 54)
BLUE = (69, 137, 199)
GRAY = (116, 131, 139)
RED = (202, 76, 72)
OUTLINE = (91, 124, 125)
BRONZE = (176, 108, 55)
SILVER = (177, 194, 202)
DIAMOND = (101, 201, 239)

LEADERBOARD_HEADER = "score\tseed\tfeats"
LEGACY_LEADERBOARD_HEADER = "score\tseed"
ACHIEVEMENTS_HEADER = "unlocked_feats"
EMPTY_FEAT_MASK = "000000000"
ACHIEVEMENTS_RESET_MESSAGE = "Achievements.txt 有错误，已重置进度"
LEADERBOARD_FORMAT_MESSAGE = (
    "Failed to read leaderboard. Delete the existing Leaderboard.txt "
    "in the program folder to rebuild it."
)


@dataclass(frozen=True)
class ScoreRecord:
    score: int
    seed: int
    feats: str = EMPTY_FEAT_MASK


class LeaderboardFormatError(ValueError):
    """The on-disk leaderboard does not match this program's format."""


class Leaderboard:
    """Store all scores in descending order; stable sorting keeps later ties last."""

    def __init__(self, path: Path = LEADERBOARD_PATH) -> None:
        self.path = path

    def ensure_exists(self) -> None:
        if not self.path.exists():
            self.path.write_text(LEADERBOARD_HEADER + "\n", encoding="utf-8")
        elif self.path.read_text(encoding="utf-8").splitlines()[:1] == [LEGACY_LEADERBOARD_HEADER]:
            # Preserve scores written by the earlier two-column version.
            lines = self.path.read_text(encoding="utf-8").splitlines()
            migrated = [LEADERBOARD_HEADER]
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) != 2:
                    raise LeaderboardFormatError(LEADERBOARD_FORMAT_MESSAGE)
                try:
                    score, seed = int(parts[0]), int(parts[1])
                except ValueError as exc:
                    raise LeaderboardFormatError(LEADERBOARD_FORMAT_MESSAGE) from exc
                if score < 0 or str(score) != parts[0] or str(seed) != parts[1]:
                    raise LeaderboardFormatError(LEADERBOARD_FORMAT_MESSAGE)
                migrated.append(f"{score}\t{seed}\t{EMPTY_FEAT_MASK}")
            self._write_lines(migrated)

    def _write_lines(self, lines: list[str]) -> None:
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def read(self) -> list[ScoreRecord]:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != LEADERBOARD_HEADER:
            raise LeaderboardFormatError(LEADERBOARD_FORMAT_MESSAGE)

        records: list[ScoreRecord] = []
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) != 3:
                raise LeaderboardFormatError(LEADERBOARD_FORMAT_MESSAGE)
            try:
                score, seed = int(parts[0]), int(parts[1])
            except ValueError as exc:
                raise LeaderboardFormatError(LEADERBOARD_FORMAT_MESSAGE) from exc
            mask = parts[2]
            if (score < 0 or str(score) != parts[0] or str(seed) != parts[1]
                    or len(mask) != len(core.FEAT_NAMES)
                    or any(bit not in "01" for bit in mask)):
                raise LeaderboardFormatError(LEADERBOARD_FORMAT_MESSAGE)
            records.append(ScoreRecord(score, seed, mask))
        return sorted(records, key=lambda record: -record.score)

    def add(self, score: int, seed: int, feats: str = EMPTY_FEAT_MASK) -> None:
        if len(feats) != len(core.FEAT_NAMES) or any(bit not in "01" for bit in feats):
            raise ValueError("Feat mask must contain exactly nine binary digits")
        records = self.read()
        records.append(ScoreRecord(score, seed, feats))
        records.sort(key=lambda record: -record.score)
        self._write_lines([LEADERBOARD_HEADER] + [
            f"{record.score}\t{record.seed}\t{record.feats}" for record in records
        ])


class Achievements:
    """Persist permanent unlocks using the documented FEAT_NAMES bit order."""

    def __init__(self, path: Path = ACHIEVEMENTS_PATH) -> None:
        self.path = path

    def read_or_reset(self) -> tuple[set[str], bool]:
        if not self.path.exists():
            self.write(set())
            return set(), False
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if (len(lines) != 2 or lines[0] != ACHIEVEMENTS_HEADER
                    or len(lines[1]) != len(core.FEAT_NAMES)
                    or any(bit not in "01" for bit in lines[1])):
                raise ValueError("Malformed achievements file")
        except (UnicodeError, ValueError):
            self.write(set())
            return set(), True
        return {name for name, bit in zip(core.FEAT_NAMES, lines[1]) if bit == "1"}, False

    def write(self, unlocked: set[str]) -> None:
        if not unlocked.issubset(set(core.FEAT_NAMES)):
            raise ValueError("Unknown feat in unlock set")
        mask = feat_mask(unlocked)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(f"{ACHIEVEMENTS_HEADER}\n{mask}\n", encoding="utf-8")
        temporary.replace(self.path)


def feat_mask(feats: set[str] | tuple[str, ...]) -> str:
    """Bits always follow FEAT_NAMES, regardless of selected deck order."""

    selected = set(feats)
    return "".join("1" if name in selected else "0" for name in core.FEAT_NAMES)


class ExpansionHooks:
    """No-op extension points for future starting bonuses and achievements."""

    def on_new_game(self, game: core.Game, seed: int) -> None:
        pass

    def after_action(self, game: core.Game, option: core.Option,
                     events: list[str]) -> None:
        pass

    def bonus_points(self, game: core.Game) -> int:
        return 0

    def on_game_end(self, game: core.Game, final_score: int) -> None:
        pass


@dataclass
class PreviewObject:
    """A detached card copy used only in the browser screen."""

    number: int | str
    kind: str | None
    orientation: str


@dataclass
class PreviewAnimation:
    """A visual-only transition between two orientations of a preview copy."""

    action: str
    before_orientation: str
    after_orientation: str
    start_time: int
    duration_ms: int = 520


@dataclass
class ActionAnimation:
    option: core.Option
    card_number: int
    action: str
    start_time: int
    start_rect: pygame.Rect
    target_center: tuple[int, int]
    before_image: pygame.Surface
    after_image: pygame.Surface
    duration_ms: int = 720


class CardAtlas:
    """Access full physical cards as in-memory views of the two sprite sheets."""

    def __init__(self, asset_dir: Path = ASSET_DIR) -> None:
        paths = {
            "F": asset_dir / "basic_cards_0front.jpg",
            "B": asset_dir / "basic_cards_1back.jpg",
        }
        self.sheets: dict[str, pygame.Surface] = {}
        for side, path in paths.items():
            sheet = pygame.image.load(path).convert()
            if sheet.get_size() != (ATLAS_WIDTH, ATLAS_HEIGHT):
                raise ValueError(
                    f"Unexpected size for {path.name}: {sheet.get_size()}; "
                    f"expected {(ATLAS_WIDTH, ATLAS_HEIGHT)}"
                )
            self.sheets[side] = sheet
        feat_paths = {
            "F": asset_dir / "feats_0front.jpg",
            "B": asset_dir / "feats_1back.jpg",
        }
        self.feat_sheets: dict[str, pygame.Surface] = {}
        for side, path in feat_paths.items():
            sheet = pygame.image.load(path).convert()
            if sheet.get_size() != (FEAT_X_CUTS[-1], FEAT_Y_CUTS[-1]):
                raise ValueError(f"Unexpected size for {path.name}: {sheet.get_size()}")
            self.feat_sheets[side] = sheet
        self.cache: dict[tuple[int | str, str, bool, tuple[int, int]], pygame.Surface] = {}
        self.stored_quarter_cache: dict[tuple[int, str, tuple[int, int]], pygame.Surface] = {}

    def tile(self, number: int | str, side: str) -> pygame.Surface:
        if side not in self.sheets:
            raise ValueError("Unknown atlas side")
        feat_name = (number if isinstance(number, str) else
                     next((name for name, feat_id in core.FEAT_CARD_IDS.items()
                           if feat_id == number), None))
        if feat_name is not None:
            index = core.FEAT_NAMES.index(feat_name)
            row, column = divmod(index, 5)
            area = pygame.Rect(FEAT_X_CUTS[column], FEAT_Y_CUTS[row],
                               FEAT_X_CUTS[column + 1] - FEAT_X_CUTS[column],
                               FEAT_Y_CUTS[row + 1] - FEAT_Y_CUTS[row])
            return self.feat_sheets[side].subsurface(area)
        if not isinstance(number, int) or not 1 <= number <= 20:
            raise ValueError("Unknown atlas tile")
        row, column = divmod(number - 1, ATLAS_COLUMNS)
        area = pygame.Rect(column * CARD_WIDTH, row * CARD_HEIGHT,
                           CARD_WIDTH, CARD_HEIGHT)
        return self.sheets[side].subsurface(area)

    def render(self, number: int | str, orientation: str, stored: bool,
               box: tuple[int, int]) -> pygame.Surface:
        key = (number, orientation, stored, box)
        if key in self.cache:
            return self.cache[key]
        image = self.tile(number, orientation[0])
        if orientation[1] == "1":
            image = pygame.transform.rotate(image, 180)
        if stored:
            # Clockwise placement puts the active resource area on the right.
            image = pygame.transform.rotate(image, -90)
        scale = min(box[0] / image.get_width(), box[1] / image.get_height())
        size = (max(1, round(image.get_width() * scale)),
                max(1, round(image.get_height() * scale)))
        result = pygame.transform.smoothscale(image, size)
        self.cache[key] = result
        return result

    def stored_quarter(self, number: int, orientation: str,
                       box: tuple[int, int]) -> pygame.Surface:
        """Render only the resource-bearing right quarter of a stored card."""
        key = (number, orientation, box)
        if key in self.stored_quarter_cache:
            return self.stored_quarter_cache[key]
        image = self.tile(number, orientation[0])
        if orientation[1] == "1":
            image = pygame.transform.rotate(image, 180)
        image = pygame.transform.rotate(image, -90)
        quarter_width = image.get_width() // 4
        image = image.subsurface((image.get_width() - quarter_width, 0,
                                  quarter_width, image.get_height()))
        scale = min(box[0] / image.get_width(), box[1] / image.get_height())
        size = (max(1, round(image.get_width() * scale)),
                max(1, round(image.get_height() * scale)))
        result = pygame.transform.smoothscale(image, size)
        self.stored_quarter_cache[key] = result
        return result

    def cover(self, box: tuple[int, int]) -> pygame.Surface:
        # Tile 20 of the basic sheet is the cover, while playable Feat #20 has
        # its own image. Access the basic tile directly to avoid that collision.
        row, column = divmod(19, ATLAS_COLUMNS)
        area = pygame.Rect(column * CARD_WIDTH, row * CARD_HEIGHT,
                           CARD_WIDTH, CARD_HEIGHT)
        image = self.sheets["F"].subsurface(area)
        scale = min(box[0] / image.get_width(), box[1] / image.get_height())
        return pygame.transform.smoothscale(
            image, (max(1, round(image.get_width() * scale)),
                    max(1, round(image.get_height() * scale)))
        )


class RulebookPages:
    """Load each supplied two-page spread as one image."""

    def __init__(self, asset_dir: Path) -> None:
        self.directory = asset_dir / "rule"
        self.cache: dict[tuple[int, int], pygame.Surface] = {}

    def get(self, pages: tuple[int, int]) -> pygame.Surface:
        if pages not in RULE_PAGE_SPREADS:
            raise ValueError("Unknown rulebook spread")
        if pages not in self.cache:
            first, last = pages
            spread = pygame.image.load(
                self.directory / f"rule{first}-{last}.jpg"
            ).convert()
            width, height = spread.get_size()
            if width != 1488 or height != 1039:
                raise ValueError(f"Unexpected rulebook spread size: {(width, height)}")
            self.cache[pages] = spread
        return self.cache[pages]


def tracker_orientation(round_number: int) -> str:
    """The tracker tile shows rounds 1/5, 2/6, 3/7 and 4/8."""

    return ("F0", "F1", "B1", "B0")[(round_number - 1) % 4]


def ease_in_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def blend(a: int, b: int, progress: float) -> int:
    return round(a + (b - a) * progress)


def dim(color: tuple[int, int, int], factor: float = 0.48) -> tuple[int, int, int]:
    return tuple(round(component * factor) for component in color)


def compact_resources(resource: core.Resource) -> str:
    parts = []
    for amount, label in ((resource.wood, "W"), (resource.fish, "F"),
                          (resource.stone, "S")):
        if amount:
            parts.append(f"{amount}{label}")
    return " ".join(parts) if parts else "None"


def card_action(menu_index: int) -> str:
    if menu_index == 0:
        return "pass"
    return ("store", "rotate", "flip")[(menu_index - 1) % 3]


def feat_orientation(name: str, unlocked: bool) -> str:
    """The unlocked marker is at the top left in this orientation."""

    if not unlocked:
        return "F0"
    return "F1" if name in (
        "Statue of Trust", "Strength of Spirit", "Horn of Honor"
    ) else "B0"


def rating_for(score: int) -> tuple[str, tuple[int, int, int]]:
    """The solo rating and its requested five-tier badge color."""

    if score < 10:
        return "Needs work", (12, 17, 20)
    if score < 20:
        return "Needs work", BRONZE
    if score < 30:
        return "Respectable", SILVER
    if score < 40:
        return "Exceptional", GOLD
    return "Astounding", DIAMOND


FEAT_DESCRIPTIONS = {
    "Statue of Trust": "Unlock: score 30 or more. Spend 1 wood + 1 fish to flip it into a wild-resource card. Later spend 1 of each resource to improve it.",
    "Heart of the Mountain": "Unlock: finish with 9 stored stone and at least 25 points. In future games it stores 1 stone for free.",
    "Strength of Spirit": "Unlock: upgrade no Temples and score 30 or more. In a later game, two level-3 Housing cards let it flip for points.",
    "Horn of Honor": "Unlock: reach level 2 with Market and Trade House and score 32 or more. Later it converts wood and fish into stone, or stone into wood and fish.",
    "Tooth of the Beast": "Unlock: all 3 Canoe Houses at level 2 and score 30 or more. At game start, upgrade a chosen Canoe House to level 1.",
    "Axe of Greatness": "Unlock: all 3 Loggers at level 2 or higher and score 34 or more. At game start, upgrade a chosen Logger to level 1.",
    "Vision Stone": "Unlock: score 40 or more. At game start, move any eligible card to the front of the deck.",
    "Monument of Glory": "Unlock: both Temples at level 3 or higher and score 30 or more. Store 1 wood + 1 fish + 1 stone for free once per game.",
    "Mark of Balance": "Unlock: all 16 basic cards at level 2 or higher. In future games it stores 1 wood + 1 fish for free.",
}

RULE_SECTIONS = (
    ("GOAL", "Build your island with 16 development cards over eight rounds. "
     "At the end, add the stars on their active faces."),
    ("YOUR TURN", "Use an action printed in the active upper half of either "
     "of the first two cards, or discard the first card. An acted-on card "
     "moves to the back of the deck."),
    ("STORE", "Turn a card sideways to keep its resource available. You may "
     "store up to four cards. If you store a fifth, release one first."),
    ("ROTATE AND FLIP", "Rotate turns a card 180 degrees. Flip changes to its "
     "other side without rotating it. Only the actions printed on the "
     "active face are available."),
    ("PAYING COSTS", "Spend whole stored cards that produce a needed resource. "
     "Choose one alternative when a cost says 'or'. Spent cards reset "
     "in place; excess resources are lost."),
    ("ROUNDS", "A stored card expires when it reaches the front. The round "
     "tracker advances the round when it reaches the front. The game ends "
     "after round eight."),
)


class PalmIslandApp:
    def __init__(self, *, asset_dir: Path = ASSET_DIR,
                 leaderboard_path: Path = LEADERBOARD_PATH,
                 achievements_path: Path = ACHIEVEMENTS_PATH,
                 window_size: tuple[int, int] | None = None,
                 hooks: ExpansionHooks | None = None) -> None:
        pygame.init()
        if window_size is None:
            display = pygame.display.Info()
            width = min(WINDOW_SIZE[0], max(1000, display.current_w - 80))
            height = min(WINDOW_SIZE[1], max(700, display.current_h - 80))
            window_size = (width, height)
        self.screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        pygame.display.set_caption("Palm Island")
        self.clock = pygame.time.Clock()
        self.fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self.atlas = CardAtlas(asset_dir)
        self.rulebook = RulebookPages(asset_dir)
        self.leaderboard = Leaderboard(leaderboard_path)
        self.leaderboard_startup_error = ""
        try:
            self.leaderboard.ensure_exists()
        except LeaderboardFormatError as exc:
            self.leaderboard_startup_error = str(exc)
        except UnicodeError:
            self.leaderboard_startup_error = LEADERBOARD_FORMAT_MESSAGE
        except OSError:
            self.leaderboard_startup_error = "Unable to create Leaderboard.txt in the program folder."
        self.achievements = Achievements(achievements_path)
        self.unlocked_feats, achievements_reset = self.achievements.read_or_reset()
        self.hooks = hooks if hooks is not None else ExpansionHooks()

        self.running = True
        self.mode = "achievement_error" if achievements_reset else "main"
        self.hotspots: list[tuple[pygame.Rect, str, object]] = []
        self.game: core.Game | None = None
        self.seed: int | None = None
        self.auto_demo = False
        self.auto_next_action_at = 0
        self.auto_turns = 0
        self.seed_text = ""
        self.seed_focused = False
        self.selected_feats: set[str] = set()
        self.active_feats: set[str] = set()
        self.feat_order_remaining: list[str] = []
        self.feat_order: list[str] = []
        self.setup_stage_index = 0
        self.setup_stage = ""
        self.setup_selected_card: int | None = None
        self.rule_page_index = 0
        self.preview_return_mode = "game"
        self.animation: ActionAnimation | None = None
        self.pending_options: list[core.Option] = []
        self.payment_selected: set[int] = set()
        self.preview: PreviewObject | None = None
        self.preview_animation: PreviewAnimation | None = None
        self.preview_slot = 0
        self.banner_round = 0
        self.banner_actions_left = 0
        self.toast = ""
        self.toast_color = RED
        self.toast_until = 0
        self.leaderboard_records: list[ScoreRecord] = []
        self.leaderboard_message = ""
        self.result_score = 0
        self.result_message = ""
        self.hover_message = ""

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.SysFont("Arial", size, bold=bold)
        return self.fonts[key]

    def chinese_font(self, size: int) -> pygame.font.Font:
        for name in ("PingFang SC", "Hiragino Sans GB", "Heiti SC", "Arial Unicode MS"):
            path = pygame.font.match_font(name)
            if path:
                return pygame.font.Font(path, size)
        return pygame.font.SysFont(None, size)

    def text(self, label: str, size: int, color: tuple[int, int, int],
             *, center: tuple[int, int] | None = None,
             topleft: tuple[int, int] | None = None,
             max_width: int | None = None, bold: bool = False) -> pygame.Rect:
        actual_size = size
        rendered = self.font(actual_size, bold).render(label, True, color)
        while max_width is not None and rendered.get_width() > max_width and actual_size > 11:
            actual_size -= 1
            rendered = self.font(actual_size, bold).render(label, True, color)
        rect = rendered.get_rect()
        if center is not None:
            rect.center = center
        elif topleft is not None:
            rect.topleft = topleft
        self.screen.blit(rendered, rect)
        return rect

    def wrapped_text(self, label: str, x: int, y: int, width: int,
                     size: int, color: tuple[int, int, int],
                     line_gap: int = 4) -> int:
        line = ""
        for word in label.split():
            candidate = f"{line} {word}".strip()
            if line and self.font(size).size(candidate)[0] > width:
                self.text(line, size, color, topleft=(x, y))
                y += size + line_gap
                line = word
            else:
                line = candidate
        if line:
            self.text(line, size, color, topleft=(x, y))
            y += size + line_gap
        return y

    def panel(self, rect: pygame.Rect, *, dark: bool = False,
              border: bool = True, radius: int = 20) -> None:
        pygame.draw.rect(self.screen, PANEL_DARK if dark else PANEL,
                         rect, border_radius=radius)
        if border:
            pygame.draw.rect(self.screen, OUTLINE, rect, 2, border_radius=radius)

    def button(self, rect: pygame.Rect, label: str,
               color: tuple[int, int, int], command: str,
               payload: object = None, *, dimmed: bool = False,
               size: int = 22) -> None:
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        fill = dim(color) if dimmed else color
        if hovered and not dimmed:
            fill = tuple(min(255, channel + 20) for channel in fill)
        pygame.draw.rect(self.screen, (8, 24, 29), rect.move(0, 4), border_radius=13)
        pygame.draw.rect(self.screen, fill, rect, border_radius=13)
        pygame.draw.rect(self.screen, dim(OUTLINE, 0.9), rect, 1, border_radius=13)
        lines = label.split("\n")
        line_height = size if len(lines) == 1 else size - 2
        start_y = rect.centery - (len(lines) * line_height) // 2 + line_height // 2
        label_color = ((13, 25, 28) if sum(color) > 650 and not dimmed
                       else (MUTED if dimmed else CREAM))
        for index, line in enumerate(lines):
            self.text(line, size if len(lines) == 1 else size - 2,
                      label_color,
                      center=(rect.centerx, start_y + index * line_height),
                      max_width=rect.width - 14, bold=True)
        self.hotspots.append((rect, command, payload))

    def draw_background(self) -> None:
        width, height = self.screen.get_size()
        self.screen.fill(BG)
        for y in range(0, height, 56):
            pygame.draw.line(self.screen, BG_LIGHT, (0, y), (width, y), 1)
        pygame.draw.circle(self.screen, (24, 68, 69),
                           (width - 120, -140), min(width, height) // 2)
        pygame.draw.circle(self.screen, BG, (width - 145, -180),
                           min(width, height) // 2 - 60)

    def show_toast(self, label: str, color: tuple[int, int, int] = RED,
                   duration_ms: int = 2200) -> None:
        self.toast = label
        self.toast_color = color
        self.toast_until = pygame.time.get_ticks() + duration_ms

    def draw_toast(self) -> None:
        if not self.toast or pygame.time.get_ticks() >= self.toast_until:
            return
        width, height = self.screen.get_size()
        rect = pygame.Rect(0, 0, min(width - 60, 740), 54)
        rect.center = (width // 2, height - 45)
        pygame.draw.rect(self.screen, (35, 30, 34), rect, border_radius=12)
        pygame.draw.rect(self.screen, self.toast_color, rect, 2, border_radius=12)
        self.text(self.toast, 22, self.toast_color, center=rect.center,
                  max_width=rect.width - 20, bold=True)

    def layout(self) -> dict[str, pygame.Rect]:
        width, height = self.screen.get_size()
        top = max(150, round(height * 0.18))
        button_height = max(45, round(height * 0.064))
        action_area = button_height * 2 + 31
        card_height = min(
            round(height * 0.51),
            round(width * 0.31 * CARD_HEIGHT / CARD_WIDTH),
            height - top - action_area - 85,
        )
        card_width = round(card_height * CARD_WIDTH / CARD_HEIGHT)
        first = pygame.Rect(0, top, card_width, card_height)
        first.centerx = round(width * 0.19)
        second = pygame.Rect(0, top, card_width, card_height)
        second.centerx = round(width * 0.51)
        deck_height = round(card_height * 0.75)
        deck_width = round(deck_height * CARD_WIDTH / CARD_HEIGHT)
        deck = pygame.Rect(0, top + 28, deck_width, deck_height)
        deck.centerx = round(width * 0.84)
        storage = pygame.Rect(round(width * 0.68), round(height * 0.66),
                              round(width * 0.30), round(height * 0.32))
        return {"first": first, "second": second, "deck": deck,
                "storage": storage}

    def card_at(self, position: int) -> tuple[int, str, bool, str]:
        assert self.game is not None
        number = self.game.deck[position]
        if number == core.TRACKER_ID:
            return number, tracker_orientation(self.game.round_number), False, "Round Tracker"
        card = self.game.cards[number]
        return number, card.orientation, card.stored, card.display_name

    def draw_card(self, number: int, orientation: str, stored: bool,
                  rect: pygame.Rect) -> pygame.Rect:
        image = self.atlas.render(number, orientation, stored, rect.size)
        area = image.get_rect(center=rect.center)
        shadow = area.move(6, 8)
        pygame.draw.rect(self.screen, (8, 24, 29), shadow, border_radius=12)
        self.screen.blit(image, area)
        pygame.draw.rect(self.screen, GOLD, area, 2, border_radius=10)
        return area

    def draw_lock(self, center: tuple[int, int], color: tuple[int, int, int]) -> None:
        x, y = center
        pygame.draw.lines(self.screen, color, False,
                          [(x - 6, y - 2), (x - 6, y - 9),
                           (x - 3, y - 12), (x + 3, y - 12),
                           (x + 6, y - 9), (x + 6, y - 2)], 2)
        pygame.draw.rect(self.screen, color, (x - 10, y - 2, 20, 14),
                         2, border_radius=3)
        pygame.draw.circle(self.screen, color, (x, y + 5), 2)

    def draw_feat_tile(self, name: str, cell: pygame.Rect) -> None:
        unlocked = name in self.unlocked_feats
        selected = name in self.selected_feats
        self.panel(cell, dark=True, radius=10)
        image_box = pygame.Rect(cell.x + 7, cell.y + 6,
                                cell.width - 14, cell.height - 36)
        image = self.atlas.render(name, feat_orientation(name, unlocked),
                                  False, image_box.size)
        area = image.get_rect(center=image_box.center)
        self.screen.blit(image, area)
        if not unlocked:
            shade = pygame.Surface(area.size, pygame.SRCALPHA)
            shade.fill((5, 12, 15, 170))
            self.screen.blit(shade, area)
        pygame.draw.rect(self.screen, GREEN if selected else
                         (GOLD if unlocked else GRAY), area,
                         3 if selected else 1, border_radius=7)
        self.hotspots.append((area, "feat_preview", name))

        checkbox = pygame.Rect(cell.right - 37, cell.bottom - 34, 27, 27)
        pygame.draw.rect(self.screen, CREAM if unlocked else dim(CREAM),
                         checkbox, border_radius=4)
        pygame.draw.rect(self.screen, (9, 18, 20), checkbox, 2, border_radius=4)
        if not unlocked:
            self.draw_lock(checkbox.center, CREAM)
        elif selected:
            pygame.draw.line(self.screen, GREEN,
                             (checkbox.x + 5, checkbox.y + 13),
                             (checkbox.x + 11, checkbox.y + 20), 4)
            pygame.draw.line(self.screen, GREEN,
                             (checkbox.x + 11, checkbox.y + 20),
                             (checkbox.x + 23, checkbox.y + 5), 4)
        if unlocked:
            self.hotspots.append((checkbox, "toggle_feat", name))
        self.text(name, 15, CREAM if unlocked else MUTED,
                  center=(cell.centerx - 13, cell.bottom - 20),
                  max_width=cell.width - 48, bold=True)

    def draw_feat_thumbnails(self, names: list[str] | tuple[str, ...],
                             area: pygame.Rect, *, clickable: bool = False,
                             max_height: int = 72,
                             max_width: int = 58) -> None:
        if not names:
            self.text("None", 17, MUTED, topleft=area.topleft)
            return
        count = len(names)
        cell_width = min(max_width, max(24, area.width // count))
        for index, name in enumerate(names):
            box = pygame.Rect(area.x + index * cell_width, area.y,
                              cell_width - 4, min(area.height, max_height))
            orientation = feat_orientation(name, True)
            image = self.atlas.render(name, orientation, False, box.size)
            image_rect = image.get_rect(center=box.center)
            self.screen.blit(image, image_rect)
            pygame.draw.rect(self.screen, GREEN, image_rect, 2, border_radius=4)
            if clickable:
                self.hotspots.append((image_rect, "active_feat_preview", name))

    def draw_main(self) -> None:
        width, height = self.screen.get_size()
        self.text("PALM ISLAND", 62, CREAM,
                  center=(round(width * 0.34), round(height * 0.17)), bold=True)
        self.text("A solo island-building card game", 23, MUTED,
                  center=(round(width * 0.34), round(height * 0.24)))
        cover = self.atlas.cover((round(width * 0.30), round(height * 0.70)))
        self.screen.blit(cover, cover.get_rect(center=(round(width * 0.78), height // 2)))
        options = (("START GAME", "open_seed", GREEN),
                   ("GAME RULES", "open_rules", BLUE),
                   ("LEADERBOARD", "open_leaderboard", GOLD),
                   ("QUIT GAME", "quit", GRAY))
        button_width = min(420, round(width * 0.38))
        button_height = min(70, round(height * 0.085))
        start_y = round(height * 0.34)
        for index, (label, command, color) in enumerate(options):
            rect = pygame.Rect(round(width * 0.34 - button_width / 2),
                               start_y + index * (button_height + 19),
                               button_width, button_height)
            self.button(rect, label, color, command, size=25)
        self.text("Artwork from the supplied Palm Island card sheets", 15, MUTED,
                  topleft=(24, height - 31))

    def draw_seed(self) -> None:
        width, height = self.screen.get_size()
        self.text("START A NEW GAME", 42, CREAM,
                  center=(width // 2, 61), bold=True)
        margin, gap = 28, 22
        left_width = max(350, round(width * 0.37))
        left = pygame.Rect(margin, 125, left_width, height - 155)
        right = pygame.Rect(left.right + gap, 105,
                            width - left.right - gap - margin, height - 155)
        self.panel(left)
        self.panel(right)
        self.text("SEED", 28, GOLD,
                  center=(left.centerx, left.y + 50), bold=True)
        self.wrapped_text("Leave the seed blank to start with a random seed.",
                          left.x + 24, left.y + 96, left.width - 48, 18, CREAM)
        field = pygame.Rect(left.x + 24, left.y + 180, left.width - 48, 62)
        pygame.draw.rect(self.screen, (12, 30, 37), field, border_radius=12)
        pygame.draw.rect(self.screen, GOLD if self.seed_focused else OUTLINE,
                         field, 3, border_radius=12)
        shown = self.seed_text if self.seed_text else "Optional integer seed"
        self.text(shown, 25, CREAM if self.seed_text else MUTED,
                  topleft=(field.x + 19, field.y + 17), max_width=field.width - 38)
        self.hotspots.append((field, "focus_seed", None))
        self.text(f"Selected Feats: {len(self.selected_feats)}", 19, CREAM,
                  center=(left.centerx, field.bottom + 45))
        start_rect = pygame.Rect(left.x + 24, field.bottom + 78,
                                 left.width - 48, 62)
        self.button(start_rect, "START NEW GAME", GREEN, "start_game", size=24)
        demo_rect = pygame.Rect(start_rect.x, start_rect.bottom + 10,
                                start_rect.width, 55)
        self.button(demo_rect, "AUTO DEMO", BLUE, "start_demo", size=23)
        back_rect = pygame.Rect(left.centerx - 100, demo_rect.bottom + 17, 200, 48)
        self.button(back_rect, "BACK", GRAY, "main_menu", size=20)

        self.text("FEATS", 30, GOLD,
                  center=(right.centerx, right.y + 32), bold=True)
        self.text("Click a card to browse; click its box to activate.", 16, MUTED,
                  center=(right.centerx, right.y + 67),
                  max_width=right.width - 25)
        inner = right.inflate(-22, -98)
        inner.y = right.y + 84
        inner.height = right.bottom - inner.y - 12
        gap = 7
        cell_width = (inner.width - 2 * gap) // 3
        cell_height = (inner.height - 2 * gap) // 3
        for index, name in enumerate(core.FEAT_NAMES):
            row, column = divmod(index, 3)
            cell = pygame.Rect(inner.x + column * (cell_width + gap),
                               inner.y + row * (cell_height + gap),
                               cell_width, cell_height)
            self.draw_feat_tile(name, cell)

    def draw_rules(self) -> None:
        width, height = self.screen.get_size()
        self.text("GAME RULES", 44, CREAM, center=(width // 2, 65), bold=True)
        margin = max(35, width // 30)
        gap = 18
        panel_width = (width - margin * 2 - gap) // 2
        panel_height = (height - 252 - gap * 2) // 3
        body_size = 19 if width >= 1250 else 16
        for index, (heading, body) in enumerate(RULE_SECTIONS):
            column = index % 2
            row = index // 2
            rect = pygame.Rect(margin + column * (panel_width + gap),
                               120 + row * (panel_height + gap),
                               panel_width, panel_height)
            self.panel(rect)
            self.text(heading, 24, GOLD, topleft=(rect.x + 22, rect.y + 18), bold=True)
            self.wrapped_text(body, rect.x + 22, rect.y + 55,
                              rect.width - 44, body_size, CREAM)
        full_rect = pygame.Rect(width // 2 - 145, height - 83, 290, 52)
        self.button(full_rect, "FULL RULEBOOK", (246, 246, 242),
                    "full_rules", size=20)
        back_rect = pygame.Rect(width - margin - 170, height - 83, 170, 52)
        self.button(back_rect, "BACK", GRAY, "main_menu", size=20)

    def draw_full_rules(self) -> None:
        width, height = self.screen.get_size()
        pages = RULE_PAGE_SPREADS[self.rule_page_index]
        self.text(f"FULL RULEBOOK", 34, CREAM,
                  center=(width // 2, 48), bold=True)
        source = self.rulebook.get(pages)
        max_height = height - 235
        max_width = width - 130
        scale = min(max_width / source.get_width(), max_height / source.get_height())
        size = (round(source.get_width() * scale),
                round(source.get_height() * scale))
        image = pygame.transform.smoothscale(source, size)
        image_rect = image.get_rect(center=(width // 2, 105 + max_height // 2))
        self.screen.blit(image, image_rect)
        pygame.draw.rect(self.screen, CREAM, image_rect, 2)
        controls_y = height - 115
        previous = pygame.Rect(width // 2 - 275, controls_y, 190, 47)
        following = pygame.Rect(width // 2 + 85, controls_y, 190, 47)
        self.button(previous, "PREVIOUS PAGE", GRAY, "rule_previous",
                    dimmed=self.rule_page_index == 0, size=18)
        self.button(following, "NEXT PAGE", GRAY, "rule_next",
                    dimmed=self.rule_page_index == len(RULE_PAGE_SPREADS) - 1,
                    size=18)
        back = pygame.Rect(width // 2 - 145, height - 59, 290, 47)
        self.button(back, "BACK TO RULES", (246, 246, 242),
                    "rules_back", size=19)

    def open_leaderboard(self) -> None:
        self.mode = "leaderboard"
        self.leaderboard_records = []
        self.leaderboard_message = self.leaderboard_startup_error
        if not self.leaderboard_message:
            try:
                self.leaderboard_records = self.leaderboard.read()[:10]
            except LeaderboardFormatError as exc:
                self.leaderboard_message = str(exc)
            except UnicodeError:
                self.leaderboard_message = LEADERBOARD_FORMAT_MESSAGE
            except OSError:
                self.leaderboard_message = "Unable to open Leaderboard.txt."

    def draw_leaderboard(self) -> None:
        width, height = self.screen.get_size()
        self.text("LEADERBOARD", 44, CREAM,
                  center=(width // 2, 70), bold=True)
        panel_width = min(1160, width - 80)
        panel_rect = pygame.Rect(0, 130, panel_width, height - 235)
        panel_rect.centerx = width // 2
        self.panel(panel_rect)
        if self.leaderboard_message:
            self.wrapped_text(self.leaderboard_message,
                              panel_rect.x + 40, panel_rect.y + 70,
                              panel_rect.width - 80, 23, RED)
        elif not self.leaderboard_records:
            self.text("No games recorded yet.", 27, MUTED,
                      center=panel_rect.center)
        else:
            self.text("RANK", 20, GOLD,
                      topleft=(panel_rect.x + 30, panel_rect.y + 27), bold=True)
            self.text("SCORE", 20, GOLD,
                      topleft=(panel_rect.x + 115, panel_rect.y + 27), bold=True)
            self.text("SEED", 20, GOLD,
                      topleft=(panel_rect.x + 250, panel_rect.y + 27), bold=True)
            self.text("ACTIVE FEATS", 20, GOLD,
                      topleft=(panel_rect.x + 510, panel_rect.y + 27), bold=True)
            row_height = min(53, max(35, (panel_rect.height - 90) // 10))
            for index, record in enumerate(self.leaderboard_records, 1):
                y = panel_rect.y + 70 + (index - 1) * row_height
                if index % 2 == 1:
                    row_rect = pygame.Rect(panel_rect.x + 20, y - 4,
                                           panel_rect.width - 40, row_height)
                    pygame.draw.rect(self.screen, PANEL_DARK, row_rect,
                                     border_radius=7)
                self.text(f"{index:02d}", 22, CREAM,
                          topleft=(panel_rect.x + 32, y))
                self.text(str(record.score), 22, CREAM,
                          topleft=(panel_rect.x + 118, y))
                self.text(str(record.seed), 21, CREAM,
                          topleft=(panel_rect.x + 250, y),
                          max_width=240)
                names = tuple(name for name, bit in zip(core.FEAT_NAMES, record.feats)
                              if bit == "1")
                self.draw_feat_thumbnails(
                    names,
                    pygame.Rect(panel_rect.x + 510, y - 3,
                                panel_rect.width - 545, row_height - 3),
                    max_height=row_height - 4, max_width=48,
                )
        back_rect = pygame.Rect(width // 2 - 110, height - 82, 220, 53)
        self.button(back_rect, "BACK", GRAY, "main_menu", size=21)

    def draw_hud(self) -> None:
        assert self.game is not None and self.seed is not None
        width, height = self.screen.get_size()
        rect = pygame.Rect(34, 23, min(550, round(width * 0.36)),
                           max(92, round(height * 0.11)))
        self.panel(rect, dark=True, radius=15)
        score = self.game.total_score() + self.hooks.bonus_points(self.game)
        stat_size = 24 if width >= 1250 else 20
        self.text(f"ROUND  {self.game.round_number} / 8", stat_size, CREAM,
                  topleft=(rect.x + 18, rect.y + 16), bold=True,
                  max_width=round(rect.width * 0.52))
        self.text(f"SCORE  {score}", stat_size, GOLD,
                  topleft=(rect.x + round(rect.width * 0.57), rect.y + 16),
                  bold=True, max_width=round(rect.width * 0.40))
        self.text(f"SEED  {self.seed}", 19 if width >= 1250 else 16, MUTED,
                  topleft=(rect.x + 18, rect.y + 55),
                  max_width=rect.width - 36)

    def draw_round_banner(self) -> None:
        if self.banner_actions_left <= 0:
            return
        width, height = self.screen.get_size()
        banner_width = min(350, max(260, round(width * 0.28)))
        rect = pygame.Rect(width - banner_width - 25, 25, banner_width, 74)
        pygame.draw.rect(self.screen, GOLD, rect, border_radius=17)
        self.text(f"ROUND {self.banner_round} BEGINS", 24, (34, 42, 41),
                  center=rect.center, max_width=rect.width - 20, bold=True)

    def draw_stored_cards(self, area: pygame.Rect, *, selectable: bool = False) -> None:
        """Draw adjacent resource quarters with their descriptions underneath."""
        assert self.game is not None
        cards = self.game.stored_cards()
        if not cards:
            self.text("No cards stored", 19, MUTED,
                      center=area.center)
            return
        gap = 2
        label_height = 74 if selectable else (56 if area.height >= 210 else 48)
        card_height = max(1, area.height - label_height - 5)
        card_width = max(1, round(card_height * (CARD_HEIGHT / 4) / CARD_WIDTH))
        maximum_width = max(1, (area.width - gap * (len(cards) - 1)) // len(cards))
        if card_width > maximum_width:
            card_width = maximum_width
            card_height = max(1, round(card_width * CARD_WIDTH / (CARD_HEIGHT / 4)))
        group_width = len(cards) * card_width + (len(cards) - 1) * gap
        first_x = area.centerx - group_width // 2
        text_size = (16 if card_width >= 85 else 14) if selectable else (
            12 if card_width >= 60 else 11 if card_width >= 42 else 9)
        for index, card in enumerate(cards):
            card_rect = pygame.Rect(first_x + index * (card_width + gap),
                                    area.y, card_width, card_height)
            image = self.atlas.stored_quarter(card.number, card.orientation,
                                              card_rect.size)
            self.screen.blit(image, image.get_rect(center=card_rect.center))
            selected = selectable and card.number in self.payment_selected
            pygame.draw.rect(self.screen, GREEN if selected else GOLD,
                             card_rect, 3 if selected else 1)
            if selectable:
                self.hotspots.append((card_rect, "toggle_payment_card", card.number))
            label_y = card_rect.bottom + 5
            self.text(f"#{card.number}", text_size + 1, GOLD,
                      center=(card_rect.centerx, label_y + text_size // 2),
                      bold=True)
            resource_lines = (card.gain_text.replace(" or ", "\n/")
                              .replace("+", "\n+").splitlines())
            for line_index, line in enumerate(resource_lines):
                self.text(line, text_size, CREAM,
                          center=(card_rect.centerx,
                                  label_y + text_size + 8
                                  + line_index * (text_size + 1)),
                          max_width=card_width + 2)

    def draw_stored(self, panel_rect: pygame.Rect) -> None:
        self.panel(panel_rect, dark=True, radius=17)
        self.text("STORED RESOURCES", 21, GOLD,
                  topleft=(panel_rect.x + 16, panel_rect.y + 10),
                  max_width=panel_rect.width - 25, bold=True)
        self.draw_stored_cards(pygame.Rect(panel_rect.x + 9, panel_rect.y + 42,
                                           panel_rect.width - 18,
                                           panel_rect.height - 48))

    def draw_action_buttons(self, position: int, card_rect: pygame.Rect,
                            entries: list[tuple[str, list[core.Option]]]) -> None:
        assert self.game is not None
        number = self.game.deck[position]
        if number == core.TRACKER_ID or self.game.cards[number].stored:
            return
        card = self.game.cards[number]
        definitions = [
            ("store", "STORE", GREEN, card.spec.store_cost),
            ("rotate", "ROTATE", YELLOW, card.spec.rotate_cost),
            ("flip", "FLIP", BLUE, card.spec.flip_cost),
        ]
        visible = []
        for offset, (action, label, color, cost) in enumerate(definitions, 1):
            if cost is None:
                continue
            if action == "store" and not card.gain_choices:
                continue
            menu_index = position * 3 + offset
            visible.append((menu_index, label, color, cost))
        if position == 0:
            visible.append((0, "DISCARD", GRAY, None))

        gap = 10
        button_width = (card_rect.width - gap) // 2
        button_height = max(45, round(self.screen.get_height() * 0.064))
        top = card_rect.bottom + 21
        for index, (menu_index, label, color, cost) in enumerate(visible):
            column, row = index % 2, index // 2
            rect = pygame.Rect(card_rect.x + column * (button_width + gap),
                               top + row * (button_height + 10),
                               button_width, button_height)
            variants = entries[menu_index][1]
            self.button(rect, label, color, "choose_action", menu_index,
                        dimmed=self.auto_demo or not bool(variants), size=19)
            if rect.collidepoint(pygame.mouse.get_pos()):
                if cost is None:
                    self.hover_message = "Discard the first card to the back of the deck."
                else:
                    issue = self.game.special_action_issue(
                        number, card_action(menu_index)
                    )
                    self.hover_message = (issue if issue else
                                          f"{core.ACTION_NAMES[card_action(menu_index)]} "
                                          f"cost: {core.cost_text(cost)}")

    def draw_game(self, *, register: bool = True) -> None:
        assert self.game is not None
        width, height = self.screen.get_size()
        layout = self.layout()
        self.hover_message = ""
        self.draw_hud()
        exit_width = min(230, round(width * 0.18))
        exit_rect = pygame.Rect((width - exit_width) // 2, 26, exit_width, 70)
        self.button(exit_rect, "EXIT GAME", RED, "request_exit",
                    dimmed=self.animation is not None, size=22)
        self.draw_stored(layout["storage"])

        for position, slot in ((0, "first"), (1, "second")):
            number, orientation, stored, name = self.card_at(position)
            rect = layout[slot]
            self.text(f"CARD {position + 1}  {name}", 21, CREAM,
                      center=(rect.centerx, rect.y - 17),
                      max_width=rect.width + 70, bold=True)
            if self.animation is None or self.animation.option.position != position:
                self.draw_card(number, orientation, stored, rect)
            if register and self.animation is None:
                self.hotspots.append((rect, "preview", position))
            if self.animation is not None and self.animation.option.position == position:
                # The first card travels underneath the second card.
                self.draw_animation()

        deck_rect = layout["deck"]
        for offset in (15, 9, 4):
            layer = deck_rect.move(offset, offset)
            pygame.draw.rect(self.screen, (9, 28, 35), layer, border_radius=9)
            pygame.draw.rect(self.screen, GOLD, layer, 1, border_radius=9)
        number, orientation, stored, name = self.card_at(2)
        self.text(f"DECK  {name}", 20, CREAM,
                  center=(deck_rect.centerx, deck_rect.y - 18),
                  max_width=deck_rect.width + 100, bold=True)
        self.draw_card(number, orientation, stored, deck_rect)
        if register and self.animation is None:
            self.hotspots.append((deck_rect, "preview", 2))

        if self.animation is None:
            entries = core.action_entries(self.game)
            self.draw_action_buttons(0, layout["first"], entries)
            self.draw_action_buttons(1, layout["second"], entries)
        if self.active_feats:
            names = [name for name in core.FEAT_NAMES if name in self.active_feats]
            self.text("ACTIVE FEATS", 15, GOLD,
                      topleft=(29, height - 114), bold=True)
            self.draw_feat_thumbnails(
                names, pygame.Rect(28, height - 92,
                                   min(round(width * 0.58), 590), 78),
                clickable=register and self.animation is None,
                max_height=72, max_width=60,
            )
        self.text(self.hover_message or "Click one of the first three cards to browse it.",
                  17, MUTED, center=(width // 2, height - 20),
                  max_width=width - 80)
        self.draw_round_banner()

    def draw_animation(self) -> None:
        assert self.animation is not None
        animation = self.animation
        progress = min(1.0, (pygame.time.get_ticks() - animation.start_time)
                       / animation.duration_ms)
        effect_fraction = 0.43
        if progress < effect_fraction:
            local = ease_in_out(progress / effect_fraction)
            image = animation.before_image
            if animation.action == "rotate":
                image = pygame.transform.rotozoom(image, -180 * local, 1.0)
            elif animation.action == "store":
                image = pygame.transform.rotozoom(image, -90 * local, 1.0)
            elif animation.action == "flip":
                if local < 0.5:
                    image = animation.before_image
                    width = max(1, round(image.get_width() * (1.0 - 2.0 * local)))
                else:
                    image = animation.after_image
                    width = max(1, round(image.get_width() * (2.0 * local - 1.0)))
                image = pygame.transform.smoothscale(image,
                                                     (width, image.get_height()))
            center = animation.start_rect.center
        else:
            local = ease_in_out((progress - effect_fraction) /
                                (1.0 - effect_fraction))
            scale = 1.0 - 0.37 * local
            source = animation.after_image
            image = pygame.transform.smoothscale(
                source,
                (max(1, round(source.get_width() * scale)),
                 max(1, round(source.get_height() * scale))),
            )
            center = (
                blend(animation.start_rect.centerx, animation.target_center[0], local),
                blend(animation.start_rect.centery, animation.target_center[1], local),
            )
        rect = image.get_rect(center=center)
        self.screen.blit(image, rect)

    def selected_payment_option(self) -> core.Option | None:
        """Use the engine's legal variants to validate the selected cards."""
        selected = self.payment_selected
        for option in self.pending_options:
            required = set(option.payment)
            if option.release is not None:
                required.add(option.release)
            if required == selected:
                return option
        return None

    def draw_payment(self) -> None:
        assert self.game is not None and self.pending_options
        self.draw_game(register=False)
        self.hotspots.clear()
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((4, 18, 22, 198))
        self.screen.blit(overlay, (0, 0))
        width, height = self.screen.get_size()
        modal = pygame.Rect(0, 0, min(1120, width - 60), min(740, height - 50))
        modal.center = (width // 2, height // 2)
        self.panel(modal)
        action = self.pending_options[0].action
        position = self.pending_options[0].position
        number = self.game.deck[position]
        card = self.game.cards[number]
        releasing = all(option.release is not None
                        for option in self.pending_options)
        heading = "CHOOSE A CARD TO RELEASE" if releasing else "CHOOSE A PAYMENT"
        self.text(heading, 32, CREAM,
                  center=(modal.centerx, modal.y + 39), bold=True)

        gap = 22
        left_width = round((modal.width - 70 - gap) * 0.39)
        body_height = modal.height - 172
        left = pygame.Rect(modal.x + 25, modal.y + 78,
                           left_width, body_height)
        right = pygame.Rect(left.right + gap, left.y,
                            modal.right - left.right - gap - 25, body_height)
        self.panel(left, dark=True, radius=12)
        self.text(f"CARD {card.display_name}", 20, GOLD,
                  center=(left.centerx, left.y + 23),
                  max_width=left.width - 20, bold=True)
        card_height = min(left.height - 65,
                          round((left.width - 26) * CARD_HEIGHT / CARD_WIDTH))
        card_width = round(card_height * CARD_WIDTH / CARD_HEIGHT)
        card_box = pygame.Rect(0, 0, card_width, card_height)
        card_box.center = (left.centerx, left.y + 42 + (left.height - 55) // 2)
        self.draw_card(number, card.orientation, False, card_box)

        self.panel(right, dark=True, radius=12)
        cost = getattr(card.spec, f"{action}_cost")
        self.text(f"COST: {core.cost_text(cost)}", 22, CREAM,
                  topleft=(right.x + 17, right.y + 14),
                  max_width=right.width - 34, bold=True)
        instruction = ("Select one stored card to release."
                       if releasing else "Click stored cards to spend; click again to deselect.")
        self.text(instruction, 17, MUTED,
                  topleft=(right.x + 17, right.y + 51),
                  max_width=right.width - 34)
        storage = pygame.Rect(right.x + 13, right.y + 86,
                              right.width - 26, right.height - 100)
        self.draw_stored_cards(storage, selectable=True)

        valid = self.selected_payment_option()
        if valid is not None:
            self.text("Ready to release" if releasing else "Ready to pay", 17, GREEN,
                      topleft=(modal.x + 30, modal.bottom - 85), bold=True)
        pay_color = {"rotate": YELLOW, "flip": BLUE, "store": GREEN}[action]
        pay = pygame.Rect(modal.x + 28, modal.bottom - 62, 220, 46)
        back = pygame.Rect(modal.right - 248, modal.bottom - 62, 220, 46)
        self.button(pay, "PAY", pay_color, "payment_pay",
                    dimmed=valid is None, size=19)
        self.button(back, "BACK", GRAY, "payment_back", size=19)

    def draw_exit_confirmation(self) -> None:
        """Block the game controls until the player keeps or abandons this game."""

        self.draw_game(register=False)
        self.hotspots.clear()
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((4, 18, 22, 205))
        self.screen.blit(overlay, (0, 0))
        width, height = self.screen.get_size()
        modal = pygame.Rect(0, 0, min(720, width - 70), min(355, height - 90))
        modal.center = (width // 2, height // 2)
        self.panel(modal)
        self.text("EXIT THIS GAME?", 36, CREAM,
                  center=(modal.centerx, modal.y + 60), bold=True)
        warning = "If you exit, you cannot return to this game."
        self.text(warning, 23, RED,
                  center=(modal.centerx, modal.y + 130),
                  max_width=modal.width - 50, bold=True)
        self.text("Your current progress will be lost.", 20, MUTED,
                  center=(modal.centerx, modal.y + 174),
                  max_width=modal.width - 50)
        gap = 20
        button_width = min(260, (modal.width - 65 - gap) // 2)
        button_y = modal.bottom - 91
        left = modal.centerx - button_width - gap // 2
        self.button(pygame.Rect(left, button_y, button_width, 58),
                    "KEEP PLAYING", GREEN, "cancel_exit", size=21)
        self.button(pygame.Rect(left + button_width + gap, button_y,
                                button_width, 58),
                    "EXIT GAME", RED, "confirm_exit", size=21)

    def draw_preview_animation(self, box: pygame.Rect) -> None:
        """Animate the browser copy without changing the game or preview state."""

        assert self.preview is not None and self.preview_animation is not None
        animation = self.preview_animation
        progress = ease_in_out(
            (pygame.time.get_ticks() - animation.start_time)
            / animation.duration_ms
        )
        before = self.atlas.render(self.preview.number,
                                   animation.before_orientation, False, box.size)
        if animation.action == "rotate":
            # Alpha keeps the newly exposed corners transparent during rotation.
            scale = 1.0 - 0.18 * (4.0 * progress * (1.0 - progress))
            image = pygame.transform.rotozoom(
                before.convert_alpha(), -180 * progress, scale
            )
        else:
            if progress < 0.5:
                source = before
                width_fraction = 1.0 - 2.0 * progress
            else:
                source = self.atlas.render(self.preview.number,
                                            animation.after_orientation, False,
                                            box.size)
                width_fraction = 2.0 * progress - 1.0
            image = pygame.transform.smoothscale(
                source,
                (max(1, round(source.get_width() * width_fraction)),
                 source.get_height()),
            )
        rect = image.get_rect(center=box.center)
        self.screen.blit(image, rect)

    def draw_preview(self) -> None:
        assert self.preview is not None
        width, height = self.screen.get_size()
        preview = self.preview
        if isinstance(preview.number, str):
            title = f"FEAT  {preview.number}"
        else:
            title = (f"CARD {self.preview_slot}  #{preview.number} "
                     + (preview.kind or "Round Tracker"))
        self.text("CARD BROWSER", 43, CREAM,
                  center=(width // 2, 62), bold=True)
        self.text(title, 20, MUTED,
                  center=(width // 2, 107), max_width=width - 100)
        preview_top = max(142, round(height * 0.16))
        preview_height = min(round(height * 0.64), height - 128 - preview_top)
        box = pygame.Rect(0, preview_top, round(width * 0.38), preview_height)
        box.centerx = round(width * 0.32)
        if self.preview_animation is None:
            self.draw_card(preview.number, preview.orientation, False, box)
        else:
            self.draw_preview_animation(box)

        info = pygame.Rect(round(width * 0.61), round(height * 0.18),
                           round(width * 0.33), round(height * 0.55))
        self.panel(info)
        self.text("CURRENT PREVIEW", 23, GOLD,
                  topleft=(info.x + 24, info.y + 22), bold=True)
        self.text(f"Orientation: {preview.orientation}", 20, CREAM,
                  topleft=(info.x + 24, info.y + 68))
        if preview.kind is None:
            assert self.game is not None
            self.wrapped_text(
                f"This is the round tracker. The game is in round "
                f"{self.game.round_number} of eight. Preview rotation "
                f"does not advance the round.",
                info.x + 24, info.y + 113, info.width - 48, 18, CREAM,
            )
        elif preview.kind not in core.CARD_KINDS:
            self.wrapped_text(
                FEAT_DESCRIPTIONS[preview.kind],
                info.x + 24, info.y + 115, info.width - 48, 19, CREAM,
            )
        else:
            spec = core.CARD_KINDS[preview.kind].faces[preview.orientation]
            shown_card = core.Card(-1, preview.kind, preview.orientation)
            rows = (
                f"Face: {spec.label}",
                f"Points: {spec.points}",
                f"Store: {core.cost_text(spec.store_cost)}",
                f"Resource: {shown_card.gain_text if spec.store_cost is not None else 'none'}",
                f"Rotate cost: {core.cost_text(spec.rotate_cost)}",
                f"Flip cost: {core.cost_text(spec.flip_cost)}",
            )
            row_y = info.y + 112
            for row in rows:
                row_y = self.wrapped_text(row, info.x + 24, row_y,
                                          info.width - 48, 18, CREAM) + 7
            if preview.kind in core.FEAT_NAMES:
                self.wrapped_text(FEAT_DESCRIPTIONS[preview.kind],
                                  info.x + 24, row_y + 5,
                                  info.width - 48, 15, MUTED)
        self.text("Preview only; the original card is unchanged.",
                  14, MUTED, topleft=(info.x + 24, info.bottom - 27),
                  max_width=info.width - 48)

        button_y = height - 102
        button_width = min(250, round(width * 0.23))
        gap = 18
        total_width = button_width * 3 + gap * 2
        start_x = (width - total_width) // 2
        self.button(pygame.Rect(start_x, button_y, button_width, 60),
                    "ROTATE", YELLOW, "preview_rotate",
                    dimmed=self.preview_animation is not None, size=21)
        self.button(pygame.Rect(start_x + button_width + gap, button_y,
                                button_width, 60),
                    "FLIP", BLUE, "preview_flip",
                    dimmed=self.preview_animation is not None, size=21)
        self.button(pygame.Rect(start_x + 2 * (button_width + gap), button_y,
                                button_width, 60),
                    "EXIT BROWSER", RED, "preview_exit", size=20)

    def draw_result(self) -> None:
        assert self.game is not None and self.seed is not None
        width, height = self.screen.get_size()
        self.text("GAME OVER", 44, CREAM,
                  center=(width // 2, 64), bold=True)
        self.text("Complete deck, top to bottom", 20, MUTED,
                  topleft=(35, 110))
        grid_left = 35
        grid_top = 145
        grid_width = round(width * 0.68) - grid_left - 12
        grid_height = height - 180
        columns = max(6, (len(self.game.deck) + 3) // 4)
        rows = (len(self.game.deck) + columns - 1) // columns
        cell_width = grid_width // columns
        cell_height = grid_height // rows
        for index, number in enumerate(self.game.deck):
            row, column = divmod(index, columns)
            cell = pygame.Rect(grid_left + column * cell_width,
                               grid_top + row * cell_height,
                               cell_width - 9, cell_height - 8)
            if number == core.TRACKER_ID:
                orientation, stored = tracker_orientation(self.game.round_number), False
            else:
                card = self.game.cards[number]
                orientation, stored = card.orientation, card.stored
            card_box = pygame.Rect(cell.x + 5, cell.y + 4,
                                   cell.width - 10, cell.height - 30)
            image = self.atlas.render(number, orientation, stored, card_box.size)
            self.screen.blit(image, image.get_rect(center=card_box.center))
            self.text(f"{index + 1}. #{number}", 15, CREAM,
                      center=(cell.centerx, cell.bottom - 14),
                      max_width=cell.width - 5)

        summary = pygame.Rect(round(width * 0.70), 145,
                              round(width * 0.27), height - 175)
        self.panel(summary)
        self.text("FINAL SCORE", 25, GOLD,
                  center=(summary.centerx, summary.y + 35), bold=True)
        self.text(str(self.result_score), 65, CREAM,
                  center=(summary.centerx, summary.y + 92), bold=True)
        rating_label, tier_color = rating_for(self.result_score)
        badge = pygame.Rect(summary.x + 22, summary.y + 132,
                            summary.width - 44, 47)
        pygame.draw.rect(self.screen, (251, 247, 234), badge, border_radius=11)
        pygame.draw.rect(self.screen, tier_color, badge, 3, border_radius=11)
        self.text(rating_label.upper(), 21, tier_color,
                  center=badge.center, max_width=badge.width - 10, bold=True)
        self.text("SEED", 20, GOLD,
                  center=(summary.centerx, summary.y + 213), bold=True)
        self.text(str(self.seed), 19, CREAM,
                  center=(summary.centerx, summary.y + 243),
                  max_width=summary.width - 25)
        self.text("ACTIVE FEATS", 17, GOLD,
                  topleft=(summary.x + 22, summary.y + 278), bold=True)
        active_names = tuple(name for name in core.FEAT_NAMES
                             if name in self.active_feats)
        self.draw_feat_thumbnails(active_names,
                                  pygame.Rect(summary.x + 22,
                                              summary.y + 305,
                                              summary.width - 44, 62),
                                  max_height=60, max_width=43)
        message_color = RED if self.result_message.startswith("Failed") else MUTED
        self.wrapped_text(self.result_message, summary.x + 24,
                          summary.y + 378, summary.width - 48, 16, message_color)
        button_width = max(150, summary.width - 50)
        self.button(pygame.Rect(summary.centerx - button_width // 2,
                                summary.bottom - 112, button_width, 45),
                    "NEW GAME", GREEN, "open_seed", size=19)
        self.button(pygame.Rect(summary.centerx - button_width // 2,
                                summary.bottom - 57, button_width, 45),
                    "MAIN MENU", GRAY, "main_menu", size=19)

    def begin_game(self, *, auto_demo: bool = False) -> None:
        entered = self.seed_text.strip()
        if entered:
            if entered == "-" or not all(
                character in "0123456789" for character in entered.lstrip("-")
            ):
                self.show_toast("Enter an integer seed.")
                return
            seed = int(entered)
        else:
            seed = random.getrandbits(64)
        pygame.key.stop_text_input()
        self.seed_focused = False
        self.seed = seed
        self.auto_demo = auto_demo
        self.auto_turns = 0
        self.game = core.Game.new(seed)
        self.active_feats = set(self.selected_feats)
        self.feat_order = []
        self.feat_order_remaining = [name for name in core.DECK_FEATS
                                     if name in self.active_feats]
        self.setup_stage_index = 0
        self.setup_stage = ""
        self.setup_selected_card = None
        if auto_demo:
            # Use an independent seeded shuffle so the same seed and selection
            # produce the same setup without changing the base deck shuffle.
            random.Random(seed).shuffle(self.feat_order_remaining)
            for name in self.feat_order_remaining:
                self.game.add_feat_card(name)
            self.feat_order = self.feat_order_remaining[:]
            self.feat_order_remaining.clear()
            for kind, name, orientation in (
                ("Canoe House", "Tooth of the Beast", "F1"),
                ("Logger", "Axe of Greatness", "F1"),
            ):
                if name in self.active_feats:
                    eligible = {"Canoe House": (1, 2, 3),
                                "Logger": (4, 5, 6)}[kind]
                    number = next(number for number in self.game.deck
                                  if number in eligible)
                    self.game.apply_starting_upgrade(kind, number, orientation)
            # Vision Stone would move the already-frontmost eligible card to
            # the front, so its automatic setup effect is intentionally skipped.
            self.finish_setup()
            return
        if self.feat_order_remaining:
            self.mode = "setup_order"
        else:
            self.advance_start_effects()

    def choose_feat_order(self, name: str) -> None:
        assert self.game is not None
        if name not in self.feat_order_remaining:
            return
        try:
            self.game.add_feat_card(name)
        except core.RuleError as exc:
            self.show_toast(str(exc), RED)
            return
        self.feat_order.append(name)
        self.feat_order_remaining.remove(name)
        if not self.feat_order_remaining:
            self.advance_start_effects()

    def advance_start_effects(self) -> None:
        while self.setup_stage_index < len(core.START_FEATS):
            name = core.START_FEATS[self.setup_stage_index]
            if name in self.active_feats:
                self.setup_stage = name
                self.mode = "setup_target"
                return
            self.setup_stage_index += 1
        self.finish_setup()

    def finish_setup(self) -> None:
        assert self.game is not None and self.seed is not None
        self.hooks.on_new_game(self.game, self.seed)
        self.animation = None
        self.banner_round = 0
        self.banner_actions_left = 0
        self.mode = "game"
        self.auto_next_action_at = pygame.time.get_ticks() + 500
        label = "Automatic demo" if self.auto_demo else "New game"
        self.show_toast(f"{label} started. Seed: {self.seed}", GOLD, 2500)

    def setup_card_eligible(self, number: int) -> bool:
        assert self.game is not None
        if number == core.TRACKER_ID:
            return False
        if self.setup_stage == "Tooth of the Beast":
            return number in (1, 2, 3)
        if self.setup_stage == "Axe of Greatness":
            return number in (4, 5, 6)
        return number in self.game.cards

    def choose_setup_target(self, number: int) -> None:
        assert self.game is not None
        if not self.setup_card_eligible(number):
            return
        if self.setup_stage == "Tooth of the Beast":
            self.setup_selected_card = number
            self.mode = "setup_canoe_direction"
            return
        try:
            if self.setup_stage == "Axe of Greatness":
                self.game.apply_starting_upgrade("Logger", number, "F1")
            else:
                self.game.apply_vision_stone(number)
        except core.RuleError as exc:
            self.show_toast(str(exc), RED)
            return
        self.setup_stage_index += 1
        self.advance_start_effects()

    def choose_canoe_direction(self, orientation: str) -> None:
        assert self.game is not None and self.setup_selected_card is not None
        try:
            self.game.apply_starting_upgrade(
                "Canoe House", self.setup_selected_card, orientation
            )
        except core.RuleError as exc:
            self.show_toast(str(exc), RED)
            return
        self.setup_selected_card = None
        self.setup_stage_index += 1
        self.advance_start_effects()

    def draw_setup_order(self) -> None:
        width, height = self.screen.get_size()
        self.text("ARRANGE YOUR FEATS", 40, CREAM,
                  center=(width // 2, 52), bold=True)
        self.text("Click each Feat in the order it should go at the back of the deck.",
                  20, MUTED, center=(width // 2, 101), max_width=width - 80)
        self.text("Selected cards are placed after the round tracker.",
                  17, GOLD, center=(width // 2, 132))
        count = len(self.feat_order_remaining)
        columns = min(3, max(1, count))
        rows = (count + columns - 1) // columns
        cell_width = min(260, (width - 180) // columns - 14)
        cell_height = min(250, (height - 325) // max(rows, 1) - 12)
        start_x = (width - columns * (cell_width + 16) + 16) // 2
        for index, name in enumerate(self.feat_order_remaining):
            row, column = divmod(index, columns)
            cell = pygame.Rect(start_x + column * (cell_width + 16),
                               170 + row * (cell_height + 16),
                               cell_width, cell_height)
            self.panel(cell, dark=True, radius=10)
            box = cell.inflate(-20, -36)
            box.height -= 13
            image = self.atlas.render(name, feat_orientation(name, True),
                                      False, box.size)
            area = image.get_rect(center=box.center)
            self.screen.blit(image, area)
            pygame.draw.rect(self.screen, GREEN, area, 2, border_radius=6)
            self.text(name, 17, CREAM,
                      center=(cell.centerx, cell.bottom - 20),
                      max_width=cell.width - 12, bold=True)
            self.hotspots.append((cell, "order_feat", name))
        self.text("ORDERED", 18, GOLD,
                  topleft=(34, height - 127), bold=True)
        if self.feat_order:
            self.draw_feat_thumbnails(self.feat_order,
                                      pygame.Rect(34, height - 102,
                                                  min(width - 68, 560), 78))
        else:
            self.text("Choose the first Feat.", 17, MUTED,
                      topleft=(34, height - 94))
        self.button(pygame.Rect(width - 220, height - 75, 180, 49),
                    "BACK", GRAY, "setup_back", size=20)

    def draw_setup_target(self) -> None:
        assert self.game is not None
        width, height = self.screen.get_size()
        prompts = {
            "Tooth of the Beast": "Select a Canoe House to upgrade to level 1.",
            "Axe of Greatness": "Select a Logger to upgrade to level 1.",
            "Vision Stone": "Select one card to move to the front of the deck.",
        }
        self.text(self.setup_stage.upper(), 38, CREAM,
                  center=(width // 2, 48), bold=True)
        self.text(prompts[self.setup_stage], 20, GOLD,
                  center=(width // 2, 98), max_width=width - 80)
        self.text("The complete deck is shown; unavailable cards are dimmed.",
                  17, MUTED, center=(width // 2, 127))
        deck = self.game.deck
        columns = min(8, max(6, (len(deck) + 3) // 4))
        rows = (len(deck) + columns - 1) // columns
        grid = pygame.Rect(40, 155, width - 80, height - 255)
        cell_width = grid.width // columns
        cell_height = grid.height // rows
        for index, number in enumerate(deck):
            row, column = divmod(index, columns)
            cell = pygame.Rect(grid.x + column * cell_width,
                               grid.y + row * cell_height,
                               cell_width - 8, cell_height - 8)
            if number == core.TRACKER_ID:
                orientation = tracker_orientation(self.game.round_number)
            else:
                orientation = self.game.cards[number].orientation
            box = pygame.Rect(cell.x + 4, cell.y + 3,
                              cell.width - 8, cell.height - 27)
            image = self.atlas.render(number, orientation, False, box.size)
            area = image.get_rect(center=box.center)
            self.screen.blit(image, area)
            eligible = self.setup_card_eligible(number)
            if not eligible:
                shade = pygame.Surface(area.size, pygame.SRCALPHA)
                shade.fill((4, 14, 18, 175))
                self.screen.blit(shade, area)
            pygame.draw.rect(self.screen, GREEN if eligible else GRAY,
                             area, 2 if eligible else 1)
            self.text(f"{index + 1}. #{number}", 14,
                      CREAM if eligible else MUTED,
                      center=(cell.centerx, cell.bottom - 12))
            if eligible:
                self.hotspots.append((cell, "setup_target", number))
        self.button(pygame.Rect(width // 2 - 100, height - 74, 200, 50),
                    "BACK", GRAY, "setup_back", size=20)

    def draw_setup_canoe_direction(self) -> None:
        assert self.setup_selected_card is not None
        width, height = self.screen.get_size()
        self.text("CHOOSE CANOE HOUSE UPGRADE", 39, CREAM,
                  center=(width // 2, 67), bold=True)
        self.text(f"Card #{self.setup_selected_card}: choose its level 1 path.",
                  21, GOLD, center=(width // 2, 116))
        choices = (("F1", "DOUBLE FISH"), ("B0", "FISH + WOOD"))
        card_height = min(540, height - 260)
        card_width = round(card_height * CARD_WIDTH / CARD_HEIGHT)
        gap = 75
        first_x = width // 2 - card_width - gap // 2
        for index, (orientation, label) in enumerate(choices):
            card_rect = pygame.Rect(first_x + index * (card_width + gap),
                                    155, card_width, card_height)
            self.draw_card(self.setup_selected_card, orientation, False, card_rect)
            self.button(pygame.Rect(card_rect.x, card_rect.bottom + 14,
                                    card_rect.width, 52),
                        label, BLUE, "canoe_direction", orientation, size=19)
        self.button(pygame.Rect(width // 2 - 100, height - 68, 200, 47),
                    "BACK", GRAY, "canoe_back", size=19)

    def draw_achievement_error(self) -> None:
        self.draw_main()
        self.hotspots.clear()
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((4, 12, 14, 210))
        self.screen.blit(overlay, (0, 0))
        width, height = self.screen.get_size()
        modal = pygame.Rect(0, 0, min(760, width - 70), 270)
        modal.center = (width // 2, height // 2)
        self.panel(modal)
        pygame.draw.rect(self.screen, RED, modal, 4, border_radius=20)
        self.text("ACHIEVEMENTS RESET", 30, RED,
                  center=(modal.centerx, modal.y + 57), bold=True)
        message = self.chinese_font(24).render(
            ACHIEVEMENTS_RESET_MESSAGE, True, RED
        )
        self.screen.blit(message, message.get_rect(center=(modal.centerx,
                                                         modal.y + 129)))
        self.button(pygame.Rect(modal.centerx - 95, modal.bottom - 76,
                                190, 49), "OK", RED, "dismiss_achievement_error",
                    size=20)

    def choose_action(self, menu_index: int) -> None:
        if self.game is None or self.animation is not None or self.auto_demo:
            return
        _, variants = core.action_entries(self.game)[menu_index]
        if not variants:
            position = 0 if menu_index <= 3 else 1
            number = self.game.deck[position]
            issue = self.game.special_action_issue(number, card_action(menu_index))
            self.show_toast(issue or "Insufficient resources", RED)
        elif len(variants) == 1:
            self.start_action(variants[0])
        else:
            self.pending_options = variants
            self.payment_selected.clear()
            self.mode = "payment"

    def advance_auto_demo(self) -> None:
        """Choose the next action using the rules engine's demo priorities."""

        if (not self.auto_demo or self.mode != "game" or self.game is None
                or self.game.finished or self.animation is not None
                or pygame.time.get_ticks() < self.auto_next_action_at):
            return
        options = self.game.legal_options()
        upgrades = [option for option in options
                    if option.action in ("rotate", "flip")]
        stores = [option for option in options if option.action == "store"]
        if upgrades:
            chosen = min(upgrades, key=lambda option:
                         (len(option.payment), option.position))
        elif stores:
            chosen = min(stores, key=lambda option:
                         (len(option.payment), option.position))
        else:
            chosen = options[0]
        self.start_action(chosen)
        assert self.animation is not None
        self.animation.duration_ms = 340
        self.auto_turns += 1
        if self.auto_turns > 5000:
            raise RuntimeError("Demo exceeded 5,000 actions; check deck progression")

    def start_action(self, option: core.Option) -> None:
        assert self.game is not None
        card_number = self.game.deck[option.position]
        card = self.game.cards[card_number]
        start_rect = self.layout()["first" if option.position == 0 else "second"]
        before_image = self.atlas.render(card.number, card.orientation, False,
                                         start_rect.size)
        orientation = card.orientation
        if option.action == "rotate":
            orientation = core.ROTATE_TO[orientation]
        elif option.action == "flip":
            orientation = core.FLIP_TO[orientation]
        after_image = self.atlas.render(card.number, orientation,
                                        option.action == "store", start_rect.size)
        deck_rect = self.layout()["deck"]
        self.animation = ActionAnimation(
            option=option,
            card_number=card_number,
            action=option.action,
            start_time=pygame.time.get_ticks(),
            start_rect=start_rect.copy(),
            target_center=(deck_rect.centerx + 12, deck_rect.centery + 12),
            before_image=before_image,
            after_image=after_image,
        )
        self.mode = "game"
        self.pending_options = []
        self.payment_selected.clear()

    def finish_action(self) -> None:
        assert self.animation is not None and self.game is not None
        animation = self.animation
        previous_round = self.game.round_number
        self.animation = None
        try:
            events = self.game.play(animation.option)
        except core.RuleError as exc:
            self.show_toast(str(exc), RED)
            return
        self.hooks.after_action(self.game, animation.option, events)

        if self.game.finished:
            self.result_score = (self.game.total_score()
                                 + self.hooks.bonus_points(self.game))
            if self.auto_demo:
                self.result_message = (
                    "Automatic demo completed. Its score is not added to the "
                    "leaderboard and it cannot unlock Feats."
                )
                self.mode = "result"
                return
            self.hooks.on_game_end(self.game, self.result_score)
            newly_met = set(self.game.check_unlocked_feats())
            new_unlocks = newly_met - self.unlocked_feats
            achievement_error = ""
            if new_unlocks:
                self.unlocked_feats.update(new_unlocks)
                try:
                    self.achievements.write(self.unlocked_feats)
                except OSError:
                    achievement_error = "Unable to save Achievements.txt."
            if self.leaderboard_startup_error:
                self.result_message = self.leaderboard_startup_error
            else:
                try:
                    assert self.seed is not None
                    self.leaderboard.add(self.result_score, self.seed,
                                         feat_mask(self.active_feats))
                    self.result_message = "This game was added to the leaderboard."
                except LeaderboardFormatError as exc:
                    self.result_message = str(exc)
                except UnicodeError:
                    self.result_message = LEADERBOARD_FORMAT_MESSAGE
                except OSError:
                    self.result_message = "Unable to save this game to Leaderboard.txt."
            if new_unlocks:
                self.result_message += (" New Feats unlocked: "
                                        + ", ".join(name for name in core.FEAT_NAMES
                                                    if name in new_unlocks) + ".")
            if achievement_error:
                self.result_message += " " + achievement_error
            self.mode = "result"
            return

        if self.auto_demo:
            self.auto_next_action_at = pygame.time.get_ticks() + 100
        if self.game.round_number != previous_round:
            self.banner_round = self.game.round_number
            self.banner_actions_left = 3
            self.show_toast(f"Round {self.banner_round} begins", GOLD)
        else:
            if self.banner_actions_left > 0:
                self.banner_actions_left -= 1
            verb = {"pass": "Discarded", "store": "Stored",
                    "rotate": "Rotated", "flip": "Flipped"}[animation.action]
            self.show_toast(f"{verb} card #{animation.card_number}", GOLD, 1400)

    def open_preview(self, position: int) -> None:
        assert self.game is not None
        self.preview_animation = None
        self.preview_return_mode = "game"
        number = self.game.deck[position]
        if number == core.TRACKER_ID:
            self.preview = PreviewObject(number, None,
                                         tracker_orientation(self.game.round_number))
        else:
            original = self.game.cards[number]
            self.preview = PreviewObject(original.number, original.kind,
                                         original.orientation)
        self.preview_slot = position + 1
        self.mode = "preview"

    def open_feat_preview(self, name: str, return_mode: str) -> None:
        if name not in core.FEAT_NAMES:
            return
        self.preview_animation = None
        self.preview_return_mode = return_mode
        self.preview = PreviewObject(name, name,
                                     feat_orientation(name,
                                                      name in self.unlocked_feats))
        self.preview_slot = 0
        self.mode = "preview"

    def start_preview_animation(self, action: str) -> None:
        if self.preview is None or self.preview_animation is not None:
            return
        before = self.preview.orientation
        after = (core.ROTATE_TO[before] if action == "rotate"
                 else core.FLIP_TO[before])
        self.preview_animation = PreviewAnimation(
            action=action,
            before_orientation=before,
            after_orientation=after,
            start_time=pygame.time.get_ticks(),
        )

    def finish_preview_animation(self) -> None:
        animation = self.preview_animation
        if animation is None:
            return
        if self.mode == "preview" and self.preview is not None:
            self.preview.orientation = animation.after_orientation
        self.preview_animation = None

    def go_main(self) -> None:
        if self.mode == "seed":
            pygame.key.stop_text_input()
        self.seed_focused = False
        self.preview_animation = None
        self.mode = "main"

    def abandon_game(self) -> None:
        """Discard an unfinished game without submitting a leaderboard score."""

        self.game = None
        self.seed = None
        self.auto_demo = False
        self.auto_next_action_at = 0
        self.auto_turns = 0
        self.animation = None
        self.pending_options = []
        self.payment_selected.clear()
        self.preview = None
        self.preview_animation = None
        self.active_feats.clear()
        self.feat_order.clear()
        self.feat_order_remaining.clear()
        self.banner_round = 0
        self.banner_actions_left = 0
        self.toast = ""
        self.go_main()

    def activate(self, command: str, payload: object) -> None:
        if command == "quit":
            self.running = False
        elif command == "dismiss_achievement_error":
            self.mode = "main"
        elif command == "main_menu":
            self.go_main()
        elif command == "open_seed":
            self.seed_text = ""
            self.selected_feats.clear()
            self.seed_focused = True
            pygame.key.start_text_input()
            self.mode = "seed"
        elif command == "focus_seed":
            self.seed_focused = True
            pygame.key.start_text_input()
        elif command == "start_game":
            self.begin_game()
        elif command == "start_demo":
            self.begin_game(auto_demo=True)
        elif command == "toggle_feat" and self.mode == "seed":
            name = str(payload)
            if name in self.unlocked_feats:
                if name in self.selected_feats:
                    self.selected_feats.remove(name)
                else:
                    self.selected_feats.add(name)
        elif command == "feat_preview" and self.mode == "seed":
            self.open_feat_preview(str(payload), "seed")
        elif command == "active_feat_preview" and self.mode == "game":
            self.open_feat_preview(str(payload), "game")
        elif command == "setup_back" and self.mode in ("setup_order", "setup_target"):
            self.game = None
            self.active_feats.clear()
            self.feat_order.clear()
            self.feat_order_remaining.clear()
            self.mode = "seed"
            self.seed_focused = False
        elif command == "order_feat" and self.mode == "setup_order":
            self.choose_feat_order(str(payload))
        elif command == "setup_target" and self.mode == "setup_target":
            self.choose_setup_target(int(payload))
        elif command == "canoe_direction" and self.mode == "setup_canoe_direction":
            self.choose_canoe_direction(str(payload))
        elif command == "canoe_back" and self.mode == "setup_canoe_direction":
            self.setup_selected_card = None
            self.mode = "setup_target"
        elif command == "open_rules":
            self.mode = "rules"
        elif command == "full_rules":
            self.rule_page_index = 0
            self.mode = "full_rules"
        elif command == "rule_previous" and self.mode == "full_rules":
            self.rule_page_index = max(0, self.rule_page_index - 1)
        elif command == "rule_next" and self.mode == "full_rules":
            self.rule_page_index = min(len(RULE_PAGE_SPREADS) - 1,
                                       self.rule_page_index + 1)
        elif command == "rules_back" and self.mode == "full_rules":
            self.mode = "rules"
        elif command == "open_leaderboard":
            self.open_leaderboard()
        elif command == "choose_action" and self.mode == "game":
            self.choose_action(int(payload))
        elif command == "request_exit" and self.mode == "game":
            self.mode = "confirm_exit"
            self.hotspots.clear()
        elif command == "cancel_exit" and self.mode == "confirm_exit":
            self.mode = "game"
        elif command == "confirm_exit" and self.mode == "confirm_exit":
            self.abandon_game()
        elif command == "payment_back":
            self.pending_options = []
            self.payment_selected.clear()
            self.mode = "game"
        elif command == "toggle_payment_card" and self.mode == "payment":
            number = int(payload)
            assert self.game is not None
            if any(card.number == number for card in self.game.stored_cards()):
                if number in self.payment_selected:
                    self.payment_selected.remove(number)
                else:
                    self.payment_selected.add(number)
        elif command == "payment_pay" and self.mode == "payment":
            option = self.selected_payment_option()
            if option is not None:
                self.start_action(option)
        elif command == "preview":
            self.open_preview(int(payload))
        elif command == "preview_rotate" and self.preview is not None:
            self.start_preview_animation("rotate")
        elif command == "preview_flip" and self.preview is not None:
            self.start_preview_animation("flip")
        elif command == "preview_exit":
            self.preview = None
            self.preview_animation = None
            self.mode = self.preview_return_mode

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(
                (max(1000, event.w), max(700, event.h)), pygame.RESIZABLE
            )
            return
        if self.mode == "seed":
            if event.type == pygame.TEXTINPUT and self.seed_focused:
                proposed = self.seed_text + event.text
                digits = proposed[1:] if proposed.startswith("-") else proposed
                if (len(proposed) <= 22
                        and all(character in "0123456789" for character in digits)):
                    self.seed_text = proposed
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE and self.seed_focused:
                    self.seed_text = self.seed_text[:-1]
                    return
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.begin_game()
                    return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.mode == "payment":
                self.pending_options = []
                self.payment_selected.clear()
                self.mode = "game"
            elif self.mode == "confirm_exit":
                self.mode = "game"
            elif self.mode == "preview":
                self.preview = None
                self.preview_animation = None
                self.mode = self.preview_return_mode
            elif self.mode == "full_rules":
                self.mode = "rules"
            elif self.mode == "achievement_error":
                self.mode = "main"
            elif self.mode == "setup_canoe_direction":
                self.setup_selected_card = None
                self.mode = "setup_target"
            elif self.mode in ("setup_order", "setup_target"):
                self.game = None
                self.active_feats.clear()
                self.mode = "seed"
            elif self.mode in ("seed", "rules", "leaderboard"):
                self.go_main()
            return
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.animation is None):
            for rect, command, payload in reversed(self.hotspots):
                if rect.collidepoint(event.pos):
                    self.activate(command, payload)
                    break

    def draw(self) -> None:
        self.hotspots.clear()
        self.draw_background()
        if self.mode == "main":
            self.draw_main()
        elif self.mode == "achievement_error":
            self.draw_achievement_error()
        elif self.mode == "seed":
            self.draw_seed()
        elif self.mode == "rules":
            self.draw_rules()
        elif self.mode == "full_rules":
            self.draw_full_rules()
        elif self.mode == "leaderboard":
            self.draw_leaderboard()
        elif self.mode == "setup_order":
            self.draw_setup_order()
        elif self.mode == "setup_target":
            self.draw_setup_target()
        elif self.mode == "setup_canoe_direction":
            self.draw_setup_canoe_direction()
        elif self.mode == "game":
            self.draw_game()
        elif self.mode == "payment":
            self.draw_payment()
        elif self.mode == "confirm_exit":
            self.draw_exit_confirmation()
        elif self.mode == "preview":
            self.draw_preview()
        elif self.mode == "result":
            self.draw_result()
        if self.mode in ("seed", "game", "payment", "setup_order",
                         "setup_target", "setup_canoe_direction"):
            self.draw_toast()
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            if (self.animation is not None
                    and pygame.time.get_ticks() - self.animation.start_time
                    >= self.animation.duration_ms):
                self.finish_action()
            if (self.preview_animation is not None
                    and pygame.time.get_ticks() - self.preview_animation.start_time
                    >= self.preview_animation.duration_ms):
                self.finish_preview_animation()
            self.advance_auto_demo()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


def main() -> None:
    try:
        PalmIslandApp().run()
    except (pygame.error, OSError, ValueError) as exc:
        pygame.quit()
        print(f"Unable to start Palm Island: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
