#!/usr/bin/env python3
"""
TERMINAL HEIST - GTA-V-inspired Terminal Game
==============================================

A text-based, animated heist game with 3 playable protagonists, missions,
and ASCII animations. Play through tutorials, recruit crew members, plan heists,
and execute daring robberies!

CONTROLS:
  Main Menu:   N=New Game, L=Load, E=Exit
  In-Game:     M=Map, Q=Character Switch, H=Heist Planning, I=Inventory/Shop
               WASD=Movement, ENTER=Confirm, ESC=Back

REQUIREMENTS:
  Python 3.10+, Standard library only
  Works on Windows, macOS, Linux

USAGE:
  python game.py
  python game.py --seed 12345  (for deterministic randomness)
  python game.py --no-color    (accessibility mode)

SAVE FILE:
  savegame.json (created in same directory)
"""

# === IMPORTS ===
import sys
import os
import time
import json
import random
import textwrap
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Callable, Any
from enum import Enum, auto
import shutil

# === PLATFORM SETUP ===

# Enable ANSI escape sequences on Windows
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# Global flags
USE_COLOR = True
FRAME_RATE = 12  # FPS for animations

# === ANSI CODES ===

class Color:
    """ANSI color codes"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    INVERT = "\033[7m"

    # Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Backgrounds
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

def colorize(text: str, color: str) -> str:
    """Apply color to text if colors are enabled"""
    if not USE_COLOR:
        return text
    return f"{color}{text}{Color.RESET}"

# === CURSOR CONTROL ===

def clear_screen():
    """Clear the terminal screen"""
    if sys.platform == "win32":
        os.system('cls')
    else:
        os.system('clear')

def move_cursor(row: int, col: int):
    """Move cursor to position (1-indexed)"""
    print(f"\033[{row};{col}H", end="")

def hide_cursor():
    """Hide the cursor"""
    print("\033[?25l", end="")

def show_cursor():
    """Show the cursor"""
    print("\033[?25h", end="")

def clear_line():
    """Clear current line"""
    print("\033[2K", end="")

# === INPUT HANDLING ===

def get_terminal_size():
    """Get terminal dimensions"""
    size = shutil.get_terminal_size((80, 24))
    return size.lines, size.columns

def read_key() -> str:
    """Read a single keypress (non-blocking)"""
    if sys.platform == "win32":
        import msvcrt
        if msvcrt.kbhit():
            key = msvcrt.getch()
            return key.decode('utf-8', errors='ignore').upper()
        return ""
    else:
        import select
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            # Check if input is available (non-blocking)
            if select.select([sys.stdin], [], [], 0.01)[0]:
                key = sys.stdin.read(1)
                # Handle escape sequences
                if key == '\x1b':
                    # Read rest of escape sequence if available
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        key += sys.stdin.read(2)
                return key.upper()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ""

def read_key_blocking(timeout: float = 30.0) -> str:
    """Read a single keypress (blocking with timeout)"""
    if sys.platform == "win32":
        import msvcrt
        start = time.time()
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                return key.decode('utf-8', errors='ignore').upper()
            time.sleep(0.01)
        return ""
    else:
        import select
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            # Blocking read with timeout
            if select.select([sys.stdin], [], [], timeout)[0]:
                key = sys.stdin.read(1)
                # Handle escape sequences
                if key == '\x1b':
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        rest = sys.stdin.read(2)
                        key += rest
                    return 'ESC'
                elif key == '\r' or key == '\n':
                    return 'ENTER'
                return key.upper()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ""

def wait_for_key(valid_keys: List[str] = None, timeout: float = None) -> str:
    """Wait for a specific key press"""
    start_time = time.time()

    # Flush any pending input
    if sys.platform != "win32":
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)

    while True:
        # Use blocking read for better responsiveness
        remaining = None
        if timeout:
            remaining = timeout - (time.time() - start_time)
            if remaining <= 0:
                return ""

        key = read_key_blocking(timeout=remaining if remaining else 10.0)

        if key:
            # Normalize key
            if key == 'ESC' or key == '\x1b' or key.startswith('\x1b'):
                return 'ESC'
            elif key == 'ENTER' or key == '\r' or key == '\n':
                return 'ENTER'

            # Convert to uppercase for comparison
            key = key.upper()

            if valid_keys is None or key in valid_keys:
                return key

        if timeout and (time.time() - start_time >= timeout):
            return ""

# === DATA MODELS ===

class GameMode(Enum):
    """Game state modes"""
    MENU = auto()
    MAP = auto()
    FREE_ROAM = auto()
    MISSION = auto()
    HEIST_PLANNING = auto()
    SHOP = auto()
    DRIVING = auto()
    HACKING = auto()
    DIALOGUE = auto()

@dataclass
class CrewMember:
    """A recruitable crew member"""
    name: str
    role: str  # "driver", "hacker", "gunner"
    skill: int  # 1-10
    cost: int
    loyalty: int = 50  # 0-100
    recruited: bool = False
    available: bool = True

@dataclass
class Player:
    """Player character"""
    name: str
    role: str
    hp: int = 100
    max_hp: int = 100

    # Perks (multipliers)
    dodge_bonus: float = 0.0
    hack_speed_bonus: float = 0.0
    damage_bonus: float = 0.0

    # Upgrades
    vehicle_handling: int = 1  # 1-5
    hacking_level: int = 1     # 1-5
    armor_level: int = 1       # 1-5

@dataclass
class Mission:
    """Mission definition"""
    id: str
    name: str
    description: str
    required_mission: Optional[str] = None
    completed: bool = False
    available: bool = True
    payout: int = 0

@dataclass
class CityZone:
    """A zone on the city map"""
    name: str
    x: int
    y: int
    char: str
    color: str
    missions: List[str] = field(default_factory=list)

@dataclass
class GameState:
    """Complete game state"""
    schema_version: int = 1

    # Player state
    current_player: int = 0  # Index into players list
    players: List[Player] = field(default_factory=list)
    last_char_switch: float = 0.0

    # Progress
    cash: int = 1000
    heat: int = 0  # 0-5 stars
    current_zone: str = "downtown"

    # Missions
    current_mission: Optional[str] = None
    completed_missions: List[str] = field(default_factory=list)
    active_mission_state: Dict[str, Any] = field(default_factory=dict)

    # Crew
    crew_members: List[CrewMember] = field(default_factory=list)

    # Heist planning
    heist_plan: Optional[str] = None  # "stealth", "loud", "driver"
    heist_crew: Dict[str, Optional[str]] = field(default_factory=dict)

    # Game mode
    mode: str = "MENU"

    # Map cursor
    map_cursor_x: int = 5
    map_cursor_y: int = 5

# === GAME DATA ===

def create_initial_players() -> List[Player]:
    """Create the three protagonists"""
    return [
        Player(
            name="Marek",
            role="Driver",
            dodge_bonus=0.2,
            vehicle_handling=2
        ),
        Player(
            name="Lia",
            role="Hacker",
            hack_speed_bonus=0.25,
            hacking_level=2
        ),
        Player(
            name="Rex",
            role="Gunner",
            damage_bonus=0.15,
            armor_level=2
        )
    ]

def create_crew_pool() -> List[CrewMember]:
    """Create available crew members to recruit"""
    return [
        CrewMember("Eddie", "driver", 7, 5000),
        CrewMember("Nina", "hacker", 8, 7000),
        CrewMember("Viktor", "gunner", 6, 4000),
        CrewMember("Jade", "driver", 5, 3000),
        CrewMember("Zero", "hacker", 9, 10000),
    ]

def create_missions() -> List[Mission]:
    """Create all available missions"""
    return [
        # Starter missions
        Mission(
            id="tutorial",
            name="First Wheels",
            description="Steal a car and escape the cops. Learn the basics.",
            payout=500
        ),
        Mission(
            id="recruit_crew",
            name="Building the Team",
            description="Find and recruit crew members for future heists.",
            required_mission="tutorial",
            payout=1000
        ),
        Mission(
            id="mini_heist",
            name="Small Time Score",
            description="Rob a convenience store. Choose your approach.",
            required_mission="recruit_crew",
            payout=5000
        ),
        
        # Mid-tier missions
        Mission(
            id="bank_robbery",
            name="Bank Robbery",
            description="Hit a downtown bank. High risk, high reward.",
            required_mission="mini_heist",
            payout=30000
        ),
        Mission(
            id="jewelry_store",
            name="Diamond District",
            description="Smash and grab at a high-end jewelry store.",
            required_mission="mini_heist",
            payout=25000
        ),
        Mission(
            id="armory_heist",
            name="Armory Raid",
            description="Steal military-grade weapons from the armory.",
            required_mission="bank_robbery",
            payout=40000
        ),
        Mission(
            id="drug_deal",
            name="Drug Deal",
            description="Intercept a rival gang's drug shipment.",
            required_mission="jewelry_store",
            payout=20000
        ),
        Mission(
            id="kidnapping",
            name="Kidnapping",
            description="Kidnap a VIP and collect ransom.",
            required_mission="bank_robbery",
            payout=50000
        ),
        Mission(
            id="gang_war",
            name="Gang War",
            description="Defend your territory from rival gangs.",
            required_mission="drug_deal",
            payout=30000
        ),
        Mission(
            id="corrupt_cop",
            name="Corrupt Cop",
            description="Deal with a dirty cop who has dirt on you.",
            required_mission="gang_war",
            payout=15000
        ),
        
        # Advanced missions
        Mission(
            id="escape_prison",
            name="Prison Break",
            description="Break a crew member out of prison.",
            required_mission="corrupt_cop",
            payout=20000
        ),
        Mission(
            id="car_theft_ring",
            name="Car Theft Ring",
            description="Steal luxury cars for export.",
            required_mission="armory_heist",
            payout=40000
        ),
        Mission(
            id="smuggling",
            name="Smuggling Run",
            description="Transport contraband across the city.",
            required_mission="car_theft_ring",
            payout=45000
        ),
        Mission(
            id="casino_heist",
            name="Casino Heist",
            description="Ocean's Eleven style casino robbery.",
            required_mission="smuggling",
            payout=100000
        ),
        Mission(
            id="art_gallery",
            name="Art Gallery",
            description="Steal priceless paintings from a gallery.",
            required_mission="casino_heist",
            payout=60000
        ),
        
        # Epic finales
        Mission(
            id="prep_arcadia",
            name="Arcadia Prep",
            description="Scout the Arcadia vault and gather intel.",
            required_mission="art_gallery",
            payout=2000
        ),
        Mission(
            id="arcadia_heist",
            name="The Arcadia Job",
            description="Rob the legendary Arcadia vault.",
            required_mission="prep_arcadia",
            payout=150000
        ),
        Mission(
            id="final_showdown",
            name="Final Showdown",
            description="The ultimate heist. Everything is on the line.",
            required_mission="arcadia_heist",
            payout=200000
        )
    ]

def create_city_zones() -> List[CityZone]:
    """Create city map zones"""
    return [
        CityZone("Harbor", 2, 2, "H", Color.BLUE, [
            "mini_heist", "smuggling", "drug_deal"
        ]),
        CityZone("Downtown", 5, 5, "D", Color.YELLOW, [
            "tutorial", "bank_robbery", "jewelry_store", "arcadia_heist"
        ]),
        CityZone("Suburbs", 8, 3, "S", Color.GREEN, [
            "recruit_crew", "kidnapping", "car_theft_ring"
        ]),
        CityZone("Industrial", 7, 8, "I", Color.RED, [
            "prep_arcadia", "armory_heist", "gang_war"
        ]),
        CityZone("Uptown", 10, 6, "U", Color.CYAN, [
            "casino_heist", "art_gallery", "corrupt_cop"
        ]),
        CityZone("Prison", 1, 9, "P", Color.MAGENTA, [
            "escape_prison"
        ]),
        CityZone("Finale", 11, 11, "F", Color.BRIGHT_RED, [
            "final_showdown"
        ])
    ]

def create_city_zones() -> List[CityZone]:
    """Create city map zones"""
    return [
        CityZone("Harbor", 2, 2, "H", Color.BLUE, ["mini_heist"]),
        CityZone("Downtown", 5, 5, "D", Color.YELLOW, ["tutorial", "arcadia_heist"]),
        CityZone("Suburbs", 8, 3, "S", Color.GREEN, ["recruit_crew"]),
        CityZone("Industrial", 7, 8, "I", Color.RED, ["prep_arcadia"]),
    ]

# === RENDER SYSTEM ===

def draw_box(x: int, y: int, width: int, height: int, title: str = ""):
    """Draw a box at position"""
    move_cursor(y, x)
    print("┌" + "─" * (width - 2) + "┐", end="")

    for i in range(1, height - 1):
        move_cursor(y + i, x)
        print("│" + " " * (width - 2) + "│", end="")

    move_cursor(y + height - 1, x)
    print("└" + "─" * (width - 2) + "┘", end="")

    if title:
        move_cursor(y, x + 2)
        print(f"[ {title} ]", end="")

def draw_hud(state: GameState):
    """Draw the HUD at the top of screen"""
    height, width = get_terminal_size()

    move_cursor(1, 1)
    clear_line()

    player = state.players[state.current_player]
    hp_bar = "█" * (player.hp // 10) + "░" * ((100 - player.hp) // 10)
    heat_stars = "★" * state.heat + "☆" * (5 - state.heat)

    hud = f" {colorize(player.name, Color.BRIGHT_CYAN)} | "
    hud += f"{colorize('HP:', Color.GREEN)} {hp_bar} | "
    hud += f"{colorize('$', Color.YELLOW)}{state.cash:,} | "
    hud += f"{colorize('HEAT:', Color.RED)} {heat_stars}"

    if state.current_mission:
        mission = next((m for m in create_missions() if m.id == state.current_mission), None)
        if mission:
            hud += f" | {colorize('MISSION:', Color.CYAN)} {mission.name}"

    print(hud[:width-1], end="")
    sys.stdout.flush()

def draw_panel(y: int, lines: List[str], center: bool = False):
    """Draw a text panel"""
    height, width = get_terminal_size()

    for i, line in enumerate(lines):
        if y + i >= height:
            break
        move_cursor(y + i, 1)
        clear_line()
        if center:
            padding = (width - len(line)) // 2
            print(" " * padding + line, end="")
        else:
            print(line[:width-1], end="")

    sys.stdout.flush()

def animate_transition(text: str = ""):
    """Wipe transition effect"""
    height, width = get_terminal_size()

    for i in range(3, height):
        move_cursor(i, 1)
        print("█" * width, end="")
        sys.stdout.flush()
        time.sleep(0.02)

    time.sleep(0.3)
    clear_screen()

    if text:
        move_cursor(height // 2, 1)
        draw_panel(height // 2, [text], center=True)
        time.sleep(1)

# === MINIGAME: DRIVING ===

def minigame_driving(state: GameState, duration: int = 15, difficulty: int = 1) -> bool:
    """
    Driving minigame with scrolling road and obstacles.
    Returns True if successful, False if crashed/caught.
    """
    height, width = get_terminal_size()

    player = state.players[state.current_player]
    handling = player.vehicle_handling + (0.2 if player.dodge_bonus > 0 else 0)

    # Game state
    player_lane = 1  # 0=left, 1=center, 2=right
    score = 0
    obstacles = []  # (row, lane)
    hp = 100

    start_time = time.time()
    last_spawn = time.time()
    frame = 0

    hide_cursor()

    try:
        while time.time() - start_time < duration:
            frame += 1
            clear_screen()

            # Draw HUD
            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed

            move_cursor(1, 1)
            print(colorize(f"DRIVING: {remaining}s remaining | HP: {'█' * (hp // 10)} | Score: {score}", Color.BRIGHT_YELLOW))

            # Spawn obstacles
            if time.time() - last_spawn > max(0.5, 1.5 - difficulty * 0.2):
                lane = random.randint(0, 2)
                obstacles.append([3, lane])
                last_spawn = time.time()

            # Move obstacles
            new_obstacles = []
            for obs in obstacles:
                obs[0] += 1
                if obs[0] < height - 3:
                    new_obstacles.append(obs)
                elif obs[0] == height - 3:
                    # Check collision
                    if obs[1] == player_lane:
                        # Dodge check
                        if random.random() > handling * 0.3:
                            hp -= 20
                            move_cursor(height // 2, width // 2 - 5)
                            print(colorize("*CRASH*", Color.BRIGHT_RED))
                        else:
                            score += 10
                            move_cursor(height // 2, width // 2 - 5)
                            print(colorize("*DODGE*", Color.BRIGHT_GREEN))
                    else:
                        score += 5
            obstacles = new_obstacles

            if hp <= 0:
                move_cursor(height // 2, 1)
                draw_panel(height // 2, ["CAR DESTROYED!"], center=True)
                time.sleep(2)
                return False

            # Draw road
            road_width = 15
            road_start = (width - road_width) // 2

            for row in range(3, height - 2):
                move_cursor(row, road_start)

                # Lane markers
                if row % 3 == frame % 3:
                    print(colorize("║  |  |  ║", Color.WHITE))
                else:
                    print(colorize("║     |  ║", Color.WHITE))

            # Draw obstacles
            for obs_row, obs_lane in obstacles:
                if 3 <= obs_row < height - 2:
                    obs_x = road_start + 2 + obs_lane * 5
                    move_cursor(obs_row, obs_x)
                    print(colorize("XXX", Color.RED))

            # Draw player car
            car_row = height - 3
            car_x = road_start + 2 + player_lane * 5
            move_cursor(car_row, car_x)
            print(colorize("═╬═", Color.BRIGHT_CYAN))

            # Instructions
            move_cursor(height - 1, 1)
            print(colorize("A=Left | D=Right | ESC=Abort", Color.DIM))

            sys.stdout.flush()

            # Input
            key = read_key()
            if key == 'A' and player_lane > 0:
                player_lane -= 1
            elif key == 'D' and player_lane < 2:
                player_lane += 1
            elif key == 'ESC' or key == '\x1b':
                return False

            time.sleep(1 / FRAME_RATE)

        # Success!
        move_cursor(height // 2, 1)
        draw_panel(height // 2, [
            colorize("ESCAPE SUCCESSFUL!", Color.BRIGHT_GREEN),
            f"Score: {score}"
        ], center=True)
        time.sleep(2)
        return True

    finally:
        show_cursor()

# === MINIGAME: HACKING ===

def minigame_hacking(state: GameState, complexity: int = 3) -> bool:
    """
    Hacking minigame with timed sequence matching.
    Returns True if successful, False if failed.
    """
    height, width = get_terminal_size()

    player = state.players[state.current_player]
    hack_speed = player.hacking_level * (1 + player.hack_speed_bonus)

    # Generate sequence
    sequence = [random.choice("WASD") for _ in range(complexity)]
    time_limit = max(2, 5 - hack_speed)

    current_input = []
    start_time = time.time()

    hide_cursor()

    try:
        while True:
            elapsed = time.time() - start_time
            remaining = max(0, time_limit - elapsed)

            if remaining <= 0:
                clear_screen()
                move_cursor(height // 2, 1)
                draw_panel(height // 2, [colorize("HACK FAILED - TIMEOUT!", Color.BRIGHT_RED)], center=True)
                time.sleep(2)
                return False

            clear_screen()

            # Draw UI
            progress = int((1 - remaining / time_limit) * 40)
            bar = colorize("█" * progress, Color.GREEN) + colorize("░" * (40 - progress), Color.DIM)

            lines = [
                colorize("=== HACKING TERMINAL ===", Color.BRIGHT_CYAN),
                "",
                f"Time: {bar} {remaining:.1f}s",
                "",
                f"Sequence: {' '.join(sequence)}",
                f"Input:    {' '.join(current_input)}{'_' * (len(sequence) - len(current_input))}",
                "",
                colorize("Type the sequence using W, A, S, D", Color.YELLOW)
            ]

            draw_panel(height // 2 - 4, lines, center=True)
            sys.stdout.flush()

            # Input
            key = read_key()
            if key in "WASD":
                current_input.append(key)

                # Check correctness
                if len(current_input) <= len(sequence):
                    if current_input[-1] != sequence[len(current_input) - 1]:
                        # Wrong key
                        clear_screen()
                        move_cursor(height // 2, 1)
                        draw_panel(height // 2, [colorize("INCORRECT SEQUENCE!", Color.BRIGHT_RED)], center=True)
                        time.sleep(2)
                        return False

                # Check completion
                if len(current_input) == len(sequence):
                    clear_screen()
                    move_cursor(height // 2, 1)
                    draw_panel(height // 2, [
                        colorize("HACK SUCCESSFUL!", Color.BRIGHT_GREEN),
                        colorize("Access granted...", Color.GREEN)
                    ], center=True)
                    time.sleep(2)
                    return True

            time.sleep(0.05)

    finally:
        show_cursor()



# === ADDITIONAL MINIGAMES ===

def minigame_shooting(state: GameState, targets: int = 10, time_limit: int = 20) -> bool:
    """Shooting minigame - hit targets"""
    height, width = get_terminal_size()
    player = state.players[state.current_player]
    damage_bonus = player.damage_bonus if player.role == 'Gunner' else 0
    
    hits = 0
    misses = 0
    start_time = time.time()
    target_x = random.randint(10, 60)
    
    hide_cursor()
    try:
        while hits < targets and time.time() - start_time < time_limit:
            clear_screen()
            elapsed = time.time() - start_time
            remaining = time_limit - int(elapsed)
            
            move_cursor(1, 1)
            print(colorize(f"SHOOTING RANGE | Hits: {hits}/{targets} | Time: {remaining}s | Accuracy: {hits}/{hits+misses if hits+misses > 0 else 1}", Color.BRIGHT_RED))
            
            # Draw target
            target_row = height // 2
            move_cursor(target_row - 1, target_x)
            print(colorize("  ○  ", Color.RED))
            move_cursor(target_row, target_x)
            print(colorize(" /|\\ ", Color.RED))
            move_cursor(target_row + 1, target_x)
            print(colorize(" / \\ ", Color.RED))
            
            # Crosshair
            move_cursor(height // 2, width // 2)
            print(colorize("+", Color.BRIGHT_YELLOW))
            
            move_cursor(height - 1, 1)
            print(colorize("SPACE=Shoot | ESC=Abort", Color.DIM))
            
            sys.stdout.flush()
            
            key = read_key_blocking(timeout=0.1)
            if key == ' ':
                # Check hit
                if abs((width // 2) - (target_x + 2)) < 3:
                    hits += 1
                    target_x = random.randint(10, width - 10)
                else:
                    misses += 1
            elif key == 'ESC':
                return False
                
        return hits >= targets
    finally:
        show_cursor()

def minigame_stealth(state: GameState, guards: int = 5, duration: int = 30) -> bool:
    """Stealth minigame - avoid guards"""
    height, width = get_terminal_size()
    
    player_x, player_y = width // 2, height - 3
    guard_positions = [(random.randint(5, width-5), random.randint(5, height-5)) for _ in range(guards)]
    detected = False
    start_time = time.time()
    
    hide_cursor()
    try:
        while time.time() - start_time < duration and not detected:
            clear_screen()
            elapsed = time.time() - start_time
            remaining = duration - int(elapsed)
            
            move_cursor(1, 1)
            print(colorize(f"STEALTH MODE | Time: {remaining}s | Guards: {guards}", Color.GREEN))
            
            # Draw guards (move randomly)
            for i, (gx, gy) in enumerate(guard_positions):
                if random.random() < 0.3:
                    guard_positions[i] = (gx + random.randint(-1, 1), gy + random.randint(-1, 1))
                    guard_positions[i] = (max(3, min(width-3, guard_positions[i][0])), 
                                        max(3, min(height-3, guard_positions[i][1])))
                
                move_cursor(guard_positions[i][1], guard_positions[i][0])
                print(colorize("G", Color.RED))
                
                # Check detection
                dist = abs(player_x - guard_positions[i][0]) + abs(player_y - guard_positions[i][1])
                if dist < 3:
                    detected = True
            
            # Draw player
            move_cursor(player_y, player_x)
            print(colorize("@", Color.BRIGHT_GREEN))
            
            # Draw exit
            exit_x, exit_y = width - 5, 3
            move_cursor(exit_y, exit_x)
            print(colorize("EXIT", Color.BRIGHT_CYAN))
            
            # Check win
            if abs(player_x - exit_x) < 3 and abs(player_y - exit_y) < 2:
                return True
            
            move_cursor(height - 1, 1)
            print(colorize("WASD=Move | Stay quiet!", Color.DIM))
            sys.stdout.flush()
            
            key = read_key_blocking(timeout=0.1)
            if key == 'W' and player_y > 3:
                player_y -= 1
            elif key == 'S' and player_y < height - 2:
                player_y += 1
            elif key == 'A' and player_x > 3:
                player_x -= 1
            elif key == 'D' and player_x < width - 3:
                player_x += 1
            elif key == 'ESC':
                return False
                
        return not detected
    finally:
        show_cursor()

def minigame_safecracking(state: GameState, difficulty: int = 3) -> bool:
    """Safe cracking - find the combination"""
    height, width = get_terminal_size()
    
    combination = [random.randint(0, 9) for _ in range(difficulty)]
    current = [0] * difficulty
    position = 0
    attempts = 10
    
    hide_cursor()
    try:
        while attempts > 0:
            clear_screen()
            
            move_cursor(height // 2 - 5, 1)
            lines = [
                "",
                colorize("=== SAFE CRACKING ===", Color.BRIGHT_YELLOW),
                "",
                "Find the combination!",
                "",
                f"Attempts left: {colorize(str(attempts), Color.RED)}",
                "",
                "Combination: " + " ".join([
                    colorize(f"[{current[i]}]", Color.BRIGHT_YELLOW if i == position else Color.WHITE) 
                    for i in range(difficulty)
                ]),
                "",
                colorize("W/S=Change digit | A/D=Move | ENTER=Try | ESC=Abort", Color.DIM)
            ]
            draw_panel(height // 2 - 5, lines, center=True)
            
            key = wait_for_key(['W', 'S', 'A', 'D', 'ENTER', 'ESC'], timeout=30)
            
            if key == 'W':
                current[position] = (current[position] + 1) % 10
            elif key == 'S':
                current[position] = (current[position] - 1) % 10
            elif key == 'A' and position > 0:
                position -= 1
            elif key == 'D' and position < difficulty - 1:
                position += 1
            elif key == 'ENTER':
                if current == combination:
                    animate_transition("SAFE OPENED!")
                    return True
                else:
                    attempts -= 1
                    animate_transition(f"Wrong! {attempts} attempts left")
            elif key == 'ESC':
                return False
                
        return False
    finally:
        show_cursor()

def minigame_lockpicking(state: GameState) -> bool:
    """Lockpicking - time the pins"""
    height, width = get_terminal_size()
    
    pins = 4
    current_pin = 0
    pin_positions = [random.uniform(0.3, 0.7) for _ in range(pins)]
    
    hide_cursor()
    try:
        while current_pin < pins:
            clear_screen()
            
            move_cursor(height // 2 - 5, 1)
            lines = [
                "",
                colorize("=== LOCKPICKING ===", Color.BRIGHT_CYAN),
                "",
                f"Pin {current_pin + 1} / {pins}",
                ""
            ]
            draw_panel(height // 2 - 5, lines, center=True)
            
            # Animated pin
            start_anim = time.time()
            while time.time() - start_anim < 3:
                progress = (time.time() - start_anim) / 3.0
                bar_width = 40
                bar_pos = int(progress * bar_width)
                target_pos = int(pin_positions[current_pin] * bar_width)
                
                move_cursor(height // 2, (width - bar_width) // 2)
                bar = "[" + "=" * bar_pos + " " * (bar_width - bar_pos) + "]"
                print(bar)
                
                move_cursor(height // 2 + 1, (width - bar_width) // 2 + target_pos)
                print(colorize("v", Color.GREEN))
                
                move_cursor(height - 1, 1)
                print(colorize("Press SPACE when aligned!", Color.YELLOW))
                sys.stdout.flush()
                
                key = read_key_blocking(timeout=0.05)
                if key == ' ':
                    if abs(progress - pin_positions[current_pin]) < 0.1:
                        current_pin += 1
                        animate_transition("Pin set!")
                        break
                    else:
                        animate_transition("Missed!")
                        return False
                elif key == 'ESC':
                    return False
                    
            if current_pin < pins and time.time() - start_anim >= 3:
                animate_transition("Too slow!")
                return False
                
        animate_transition("Lock picked!")
        return True
    finally:
        show_cursor()


def minigame_chase_foot(state: GameState, duration: int = 20) -> bool:
    """Foot chase minigame"""
    height, width = get_terminal_size()
    
    player_pos = 0
    cop_pos = -10
    stamina = 100
    
    hide_cursor()
    start_time = time.time()
    try:
        while time.time() - start_time < duration and stamina > 0:
            clear_screen()
            elapsed = time.time() - start_time
            remaining = duration - int(elapsed)
            
            move_cursor(1, 1)
            print(colorize(f"FOOT CHASE | Distance: {player_pos - cop_pos} | Stamina: {'█' * (stamina // 10)} | Time: {remaining}s", Color.BRIGHT_YELLOW))
            
            # Draw chase
            chase_row = height // 2
            track_width = 60
            player_x = min(track_width - 5, player_pos % track_width)
            cop_x = max(0, cop_pos % track_width)
            
            move_cursor(chase_row, 5 + player_x)
            print(colorize("@", Color.BRIGHT_GREEN))
            move_cursor(chase_row, 5 + cop_x)
            print(colorize("P", Color.BRIGHT_RED))
            
            move_cursor(height - 1, 1)
            print(colorize("SPACE=Sprint | Keep running!", Color.DIM))
            sys.stdout.flush()
            
            key = read_key_blocking(timeout=0.1)
            if key == ' ' and stamina > 0:
                player_pos += 3
                stamina -= 2
            else:
                player_pos += 1
                if stamina < 100:
                    stamina += 1
            
            cop_pos += 2
            
            if cop_pos >= player_pos:
                return False
                
        return player_pos - cop_pos > 10
    finally:
        show_cursor()

def minigame_negotiation(state: GameState, difficulty: int = 3) -> bool:
    """Negotiation with timed responses"""
    height, width = get_terminal_size()
    
    trust = 50
    responses = [
        ("Threaten", -20, 10),
        ("Bribe", 15, -5),
        ("Reason", 10, 5),
        ("Intimidate", -10, 20),
    ]
    
    for round_num in range(difficulty):
        clear_screen()
        
        situation = random.choice([
            "They're getting nervous...",
            "They demand more money!",
            "They're reconsidering the deal...",
            "They want assurances..."
        ])
        
        lines = [
            "",
            colorize(f"=== NEGOTIATION Round {round_num + 1}/{difficulty} ===", Color.BRIGHT_CYAN),
            "",
            situation,
            "",
            f"Trust Level: {colorize('█' * (trust // 10), Color.GREEN if trust > 50 else Color.RED)}",
            "",
        ]
        
        for i, (option, trust_change, _) in enumerate(responses, 1):
            lines.append(f"{i}) {option} ({'+' if trust_change > 0 else ''}{trust_change} trust)")
        
        lines.append("")
        lines.append(colorize("Choose wisely! (5s)", Color.YELLOW))
        
        draw_panel(5, lines, center=True)
        
        choice = wait_for_key(['1', '2', '3', '4'], timeout=5.0)
        
        if not choice or choice not in ['1', '2', '3', '4']:
            trust -= 20
            animate_transition("You hesitated!")
        else:
            idx = int(choice) - 1
            trust += responses[idx][1]
            
        if trust <= 0:
            animate_transition("Negotiation failed!")
            return False
        elif trust >= 100:
            animate_transition("Deal accepted!")
            return True
            
    return trust >= 50

def minigame_bomb_defusal(state: GameState) -> bool:
    """Defuse a bomb by cutting wires"""
    height, width = get_terminal_size()
    
    wires = ["RED", "BLUE", "GREEN", "YELLOW", "WHITE"]
    correct_sequence = random.sample(wires, 3)
    cut_wires = []
    time_left = 30
    
    hide_cursor()
    start_time = time.time()
    try:
        while len(cut_wires) < 3 and time_left > 0:
            time_left = 30 - int(time.time() - start_time)
            clear_screen()
            
            lines = [
                "",
                colorize("=== BOMB DEFUSAL ===", Color.BRIGHT_RED),
                "",
                f"Time: {colorize(f'{time_left}s', Color.BRIGHT_RED if time_left < 10 else Color.YELLOW)}",
                "",
                "Wires:"
            ]
            
            for i, wire in enumerate(wires, 1):
                if wire in cut_wires:
                    lines.append(f"{i}) {colorize(f'[CUT] {wire}', Color.DIM)}")
                else:
                    color = Color.RED if wire == "RED" else Color.BLUE if wire == "BLUE" else Color.GREEN if wire == "GREEN" else Color.YELLOW if wire == "YELLOW" else Color.WHITE
                    lines.append(f"{i}) {colorize(wire, color)}")
            
            lines.append("")
            lines.append(colorize(f"Cut wire {len(cut_wires) + 1} (1-5)", Color.YELLOW))
            
            draw_panel(5, lines, center=True)
            
            choice = wait_for_key(['1', '2', '3', '4', '5'], timeout=1.0)
            
            if choice and choice in ['1', '2', '3', '4', '5']:
                idx = int(choice) - 1
                wire = wires[idx]
                
                if wire not in cut_wires:
                    cut_wires.append(wire)
                    
                    if len(cut_wires) <= len(correct_sequence):
                        if wire != correct_sequence[len(cut_wires) - 1]:
                            animate_transition("*BOOM*")
                            return False
                            
        if len(cut_wires) == 3:
            animate_transition("Bomb defused!")
            return True
        else:
            animate_transition("*BOOM* Time's up!")
            return False
    finally:
        show_cursor()

def minigame_alarm_disable(state: GameState) -> bool:
    """Disable alarm system"""
    height, width = get_terminal_size()
    player = state.players[state.current_player]
    hack_bonus = player.hack_speed_bonus if player.role == "Hacker" else 0
    
    nodes = 6
    connections = [(i, (i + 1) % nodes) for i in range(nodes)]
    connections.extend([(i, (i + 2) % nodes) for i in range(0, nodes, 2)])
    
    activated = [0]
    target = nodes - 1
    time_limit = max(10, 20 - int(hack_bonus * 10))
    
    start_time = time.time()
    
    hide_cursor()
    try:
        while time.time() - start_time < time_limit:
            clear_screen()
            remaining = time_limit - int(time.time() - start_time)
            
            lines = [
                "",
                colorize("=== ALARM SYSTEM ===", Color.BRIGHT_RED),
                "",
                f"Reach node {target} | Time: {remaining}s",
                "",
                "Network:"
            ]
            
            # Show nodes
            for i in range(nodes):
                status = colorize("█", Color.GREEN) if i in activated else colorize("○", Color.DIM)
                lines.append(f"  Node {i}: {status}")
            
            lines.append("")
            lines.append("Available moves:")
            
            current = activated[-1]
            available_moves = [conn[1] for conn in connections if conn[0] == current and conn[1] not in activated]
            
            for move in available_moves:
                lines.append(f"  {move}) Jump to node {move}")
            
            draw_panel(5, lines, center=True)
            
            if not available_moves:
                return False
            
            if current == target:
                animate_transition("Alarm disabled!")
                return True
            
            choice = wait_for_key([str(m) for m in available_moves], timeout=1.0)
            
            if choice and int(choice) in available_moves:
                activated.append(int(choice))
                
        return False
    finally:
        show_cursor()

def minigame_pickpocket(state: GameState, targets: int = 5) -> bool:
    """Pickpocket minigame"""
    height, width = get_terminal_size()
    
    stolen = 0
    caught = False
    
    for target_num in range(targets):
        clear_screen()
        
        # Random timing window
        perfect_time = random.uniform(0.5, 2.0)
        
        lines = [
            "",
            colorize(f"=== PICKPOCKET Target {target_num + 1}/{targets} ===", Color.BRIGHT_YELLOW),
            "",
            f"Stolen: {stolen}",
            "",
            "Wait for the right moment...",
            "",
            colorize("Press SPACE at the perfect time!", Color.GREEN)
        ]
        
        draw_panel(8, lines, center=True)
        time.sleep(random.uniform(1.0, 2.5))
        
        start = time.time()
        pressed_time = None
        
        while time.time() - start < 3.0:
            elapsed = time.time() - start
            
            move_cursor(height // 2, width // 2 - 10)
            bar = "█" * int(elapsed / 3.0 * 20)
            print(colorize(bar, Color.YELLOW))
            
            if not pressed_time:
                key = read_key()
                if key == ' ':
                    pressed_time = elapsed
                    break
            
            time.sleep(0.05)
        
        if pressed_time and abs(pressed_time - perfect_time) < 0.3:
            stolen += 1
            animate_transition("Got it!")
        elif pressed_time:
            animate_transition("CAUGHT!")
            caught = True
            break
        else:
            animate_transition("Too slow!")
            
    return stolen >= targets // 2 and not caught

def minigame_quick_time(state: GameState, events: int = 5) -> bool:
    """Quick time events"""
    height, width = get_terminal_size()
    
    success_count = 0
    
    for event_num in range(events):
        clear_screen()
        
        required_key = random.choice(['W', 'A', 'S', 'D'])
        reaction_time = 1.0
        
        lines = [
            "",
            colorize(f"=== QUICK TIME EVENT {event_num + 1}/{events} ===", Color.BRIGHT_RED),
            "",
            f"Success: {success_count}/{event_num if event_num > 0 else 1}",
            "",
            "",
            colorize(f"PRESS {required_key}!", Color.BRIGHT_YELLOW),
            ""
        ]
        
        draw_panel(8, lines, center=True)
        
        start = time.time()
        success = False
        
        while time.time() - start < reaction_time:
            key = read_key_blocking(timeout=0.05)
            if key == required_key:
                success = True
                success_count += 1
                animate_transition("Perfect!")
                break
        
        if not success:
            animate_transition("Missed!")
            
    return success_count >= events * 0.7

def minigame_motorcycle(state: GameState, duration: int = 15) -> bool:
    """Motorcycle chase"""
    height, width = get_terminal_size()
    player = state.players[state.current_player]
    handling = player.vehicle_handling * 1.5 if player.role == "Driver" else player.vehicle_handling
    
    player_lane = 1
    distance = 0
    obstacles = []
    crashes = 0
    max_crashes = 3
    
    start_time = time.time()
    hide_cursor()
    
    try:
        while time.time() - start_time < duration and crashes < max_crashes:
            clear_screen()
            elapsed = time.time() - start_time
            remaining = duration - int(elapsed)
            
            move_cursor(1, 1)
            print(colorize(f"MOTORCYCLE | Distance: {distance}m | Crashes: {crashes}/{max_crashes} | Time: {remaining}s", Color.BRIGHT_CYAN))
            
            # Spawn obstacles
            if random.random() < 0.3:
                obstacles.append([3, random.randint(0, 2)])
            
            # Draw road
            for row in range(3, height - 2):
                move_cursor(row, width // 2 - 10)
                print(colorize("║", Color.WHITE) + "     " * 2 + colorize("║", Color.WHITE))
            
            # Draw obstacles
            for obs in obstacles:
                if 3 <= obs[0] < height - 2:
                    obs_x = width // 2 - 8 + obs[1] * 5
                    move_cursor(obs[0], obs_x)
                    print(colorize("XXX", Color.RED))
                obs[0] += 1
            
            # Remove off-screen obstacles
            obstacles = [obs for obs in obstacles if obs[0] < height]
            
            # Draw motorcycle
            bike_row = height - 3
            bike_x = width // 2 - 8 + player_lane * 5
            move_cursor(bike_row, bike_x)
            print(colorize("═M═", Color.BRIGHT_YELLOW))
            
            # Check collision
            for obs in obstacles:
                if obs[0] == bike_row and obs[1] == player_lane:
                    if random.random() > handling * 0.2:
                        crashes += 1
                        obstacles.remove(obs)
                        move_cursor(height // 2, width // 2 - 5)
                        print(colorize("*CRASH*", Color.BRIGHT_RED))
                        time.sleep(0.5)
                        
            distance += 10
            
            move_cursor(height - 1, 1)
            print(colorize("A/D=Lane | Keep moving!", Color.DIM))
            sys.stdout.flush()
            
            key = read_key()
            if key == 'A' and player_lane > 0:
                player_lane -= 1
            elif key == 'D' and player_lane < 2:
                player_lane += 1
            elif key == 'ESC':
                return False
                
            time.sleep(1 / 15)
            
        return crashes < max_crashes
    finally:
        show_cursor()

def minigame_sniper(state: GameState, targets: int = 3) -> bool:
    """Sniper minigame - precision shooting"""
    height, width = get_terminal_size()
    player = state.players[state.current_player]
    accuracy_bonus = 1.2 if player.role == "Gunner" else 1.0
    
    hits = 0
    
    hide_cursor()
    try:
        for target_num in range(targets):
            target_x = random.randint(10, width - 10)
            target_y = random.randint(5, height - 10)
            scope_x = width // 2
            scope_y = height // 2
            
            time_limit = 10
            start = time.time()
            
            while time.time() - start < time_limit:
                clear_screen()
                remaining = time_limit - int(time.time() - start)
                
                move_cursor(1, 1)
                print(colorize(f"SNIPER | Target {target_num + 1}/{targets} | Hits: {hits} | Time: {remaining}s", Color.BRIGHT_GREEN))
                
                # Draw target
                move_cursor(target_y, target_x)
                print(colorize("◎", Color.RED))
                
                # Draw scope crosshair
                move_cursor(scope_y, scope_x - 1)
                print(colorize("─┼─", Color.BRIGHT_YELLOW))
                move_cursor(scope_y - 1, scope_x)
                print(colorize("│", Color.BRIGHT_YELLOW))
                move_cursor(scope_y + 1, scope_x)
                print(colorize("│", Color.BRIGHT_YELLOW))
                
                move_cursor(height - 1, 1)
                print(colorize("WASD=Aim | SPACE=Shoot | Hold steady!", Color.DIM))
                sys.stdout.flush()
                
                key = read_key_blocking(timeout=0.1)
                if key == 'W' and scope_y > 3:
                    scope_y -= 1
                elif key == 'S' and scope_y < height - 3:
                    scope_y += 1
                elif key == 'A' and scope_x > 3:
                    scope_x -= 1
                elif key == 'D' and scope_x < width - 3:
                    scope_x += 1
                elif key == ' ':
                    dist = abs(scope_x - target_x) + abs(scope_y - target_y)
                    if dist < 2 * accuracy_bonus:
                        hits += 1
                        animate_transition("HIT!")
                        break
                    else:
                        animate_transition("MISS!")
                        break
                elif key == 'ESC':
                    return False
                    
        return hits >= targets * 0.7
    finally:
        show_cursor()

def minigame_escape_building(state: GameState) -> bool:
    """Escape from building maze"""
    height, width = get_terminal_size()
    
    # Simple maze
    maze_size = 15
    player_x, player_y = 1, 1
    exit_x, exit_y = maze_size - 2, maze_size - 2
    
    walls = set()
    for i in range(maze_size):
        walls.add((i, 0))
        walls.add((i, maze_size - 1))
        walls.add((0, i))
        walls.add((maze_size - 1, i))
    
    # Add some random walls
    for _ in range(20):
        walls.add((random.randint(2, maze_size - 3), random.randint(2, maze_size - 3)))
    
    time_limit = 45
    start_time = time.time()
    
    hide_cursor()
    try:
        while time.time() - start_time < time_limit:
            clear_screen()
            remaining = time_limit - int(time.time() - start_time)
            
            move_cursor(1, 1)
            print(colorize(f"ESCAPE | Time: {remaining}s | Find the EXIT!", Color.BRIGHT_RED))
            
            # Draw maze
            offset_x = (width - maze_size * 2) // 2
            offset_y = 4
            
            for y in range(maze_size):
                move_cursor(offset_y + y, offset_x)
                for x in range(maze_size):
                    if (x, y) in walls:
                        print(colorize("█", Color.WHITE), end=" ")
                    elif x == player_x and y == player_y:
                        print(colorize("@", Color.BRIGHT_GREEN), end=" ")
                    elif x == exit_x and y == exit_y:
                        print(colorize("E", Color.BRIGHT_CYAN), end=" ")
                    else:
                        print(" ", end=" ")
            
            if player_x == exit_x and player_y == exit_y:
                animate_transition("ESCAPED!")
                return True
            
            move_cursor(height - 1, 1)
            print(colorize("WASD=Move | Find EXIT!", Color.DIM))
            sys.stdout.flush()
            
            key = read_key_blocking(timeout=0.1)
            new_x, new_y = player_x, player_y
            
            if key == 'W':
                new_y -= 1
            elif key == 'S':
                new_y += 1
            elif key == 'A':
                new_x -= 1
            elif key == 'D':
                new_x += 1
            elif key == 'ESC':
                return False
            
            if (new_x, new_y) not in walls:
                player_x, player_y = new_x, new_y
                
        return False
    finally:
        show_cursor()

def minigame_helicopter(state: GameState, duration: int = 20) -> bool:
    """Helicopter piloting"""
    height, width = get_terminal_size()
    
    heli_y = height // 2
    altitude_target = height // 2
    obstacles = []
    distance = 0
    crashed = False
    
    start_time = time.time()
    hide_cursor()
    
    try:
        while time.time() - start_time < duration and not crashed:
            clear_screen()
            elapsed = time.time() - start_time
            remaining = duration - int(elapsed)
            
            move_cursor(1, 1)
            print(colorize(f"HELICOPTER | Distance: {distance}m | Altitude: {heli_y} | Time: {remaining}s", Color.BRIGHT_BLUE))
            
            # Spawn obstacles
            if random.random() < 0.2:
                obstacles.append([width - 5, random.randint(5, height - 5), random.choice(["building", "bird"])])
            
            # Draw obstacles
            for obs in obstacles:
                if 5 <= obs[0] < width - 5:
                    move_cursor(obs[1], obs[0])
                    symbol = "█" if obs[2] == "building" else "V"
                    print(colorize(symbol, Color.RED))
                obs[0] -= 1
            
            obstacles = [obs for obs in obstacles if obs[0] > 0]
            
            # Draw helicopter
            heli_x = 10
            move_cursor(heli_y, heli_x)
            print(colorize("═╬═", Color.BRIGHT_YELLOW))
            
            # Check collision
            for obs in obstacles:
                if obs[0] == heli_x and abs(obs[1] - heli_y) < 2:
                    crashed = True
            
            # Check boundaries
            if heli_y < 3 or heli_y > height - 3:
                crashed = True
            
            distance += 5
            
            move_cursor(height - 1, 1)
            print(colorize("W=Up | S=Down | Stay airborne!", Color.DIM))
            sys.stdout.flush()
            
            key = read_key()
            if key == 'W' and heli_y > 3:
                heli_y -= 1
            elif key == 'S' and heli_y < height - 3:
                heli_y += 1
            elif key == 'ESC':
                return False
                
            # Gravity
            if random.random() < 0.3:
                heli_y += 1
                
            time.sleep(1 / 12)
            
        if crashed:
            animate_transition("CRASHED!")
            return False
        else:
            animate_transition("Landing successful!")
            return True
    finally:
        show_cursor()

def minigame_climbing(state: GameState, height_to_climb: int = 20) -> bool:
    """Climbing minigame"""
    height_screen, width = get_terminal_size()
    
    climbed = 0
    stamina = 100
    
    hide_cursor()
    try:
        while climbed < height_to_climb and stamina > 0:
            clear_screen()
            
            move_cursor(1, 1)
            print(colorize(f"CLIMBING | Height: {climbed}/{height_to_climb}m | Stamina: {'█' * (stamina // 10)}", Color.BRIGHT_CYAN))
            
            # Draw wall
            wall_x = width // 2 - 5
            for row in range(5, height_screen - 3):
                move_cursor(row, wall_x)
                print(colorize("│││││││││││", Color.WHITE))
            
            # Draw climber
            climber_y = height_screen - 5 - min(10, climbed)
            move_cursor(climber_y, wall_x + 5)
            print(colorize("@", Color.BRIGHT_GREEN))
            
            move_cursor(height_screen - 1, 1)
            print(colorize("SPACE=Climb | Wait=Rest | Don't fall!", Color.DIM))
            sys.stdout.flush()
            
            key = read_key_blocking(timeout=0.5)
            
            if key == ' ':
                if stamina >= 10:
                    climbed += 1
                    stamina -= 10
                    if random.random() < 0.1:  # Slip chance
                        animate_transition("Slipped!")
                        climbed = max(0, climbed - 2)
                else:
                    animate_transition("Too tired!")
            else:
                stamina = min(100, stamina + 5)
            
            if key == 'ESC':
                return False
                
        return climbed >= height_to_climb
    finally:
        show_cursor()

def minigame_swimming(state: GameState, distance: int = 50) -> bool:
    """Swimming/diving minigame"""
    height_screen, width = get_terminal_size()
    
    swum = 0
    oxygen = 100
    depth = height_screen // 2
    
    hide_cursor()
    try:
        while swum < distance and oxygen > 0:
            clear_screen()
            
            move_cursor(1, 1)
            print(colorize(f"SWIMMING | Distance: {swum}/{distance}m | O2: {'█' * (oxygen // 10)}", Color.BRIGHT_BLUE))
            
            # Draw water
            for row in range(3, height_screen - 2):
                move_cursor(row, 5)
                if row < depth:
                    print(colorize("~" * 60, Color.CYAN))
                else:
                    print(colorize("≈" * 60, Color.BLUE))
            
            # Draw swimmer
            move_cursor(depth, 30)
            print(colorize("@", Color.BRIGHT_YELLOW))
            
            # Draw sharks/obstacles
            if random.random() < 0.1:
                shark_y = random.randint(depth + 5, height_screen - 5)
                move_cursor(shark_y, 50)
                print(colorize("<)))><", Color.RED))
            
            move_cursor(height_screen - 1, 1)
            print(colorize("W=Up | S=Down | D=Swim | Surface for air!", Color.DIM))
            sys.stdout.flush()
            
            key = read_key_blocking(timeout=0.2)
            
            if key == 'W' and depth > 5:
                depth -= 1
                if depth < height_screen // 3:
                    oxygen = min(100, oxygen + 10)  # Surface = air
            elif key == 'S' and depth < height_screen - 5:
                depth += 1
            elif key == 'D':
                swum += 1
            elif key == 'ESC':
                return False
            
            if depth > height_screen // 2:
                oxygen -= 2
            else:
                oxygen -= 1
                
        return swum >= distance and oxygen > 0
    finally:
        show_cursor()

def minigame_interrogation(state: GameState) -> bool:
    """Interrogation minigame - get information"""
    height, width = get_terminal_size()
    
    stress = 50
    info_gained = 0
    target_info = 3
    
    questions = [
        ("Where is the money?", "aggressive", 15, -10),
        ("We can protect you...", "friendly", 10, 5),
        ("You're going to jail!", "intimidate", 20, -15),
        ("Let's make a deal.", "negotiate", 5, 10),
    ]
    
    for round_num in range(5):
        if info_gained >= target_info:
            break
            
        clear_screen()
        
        lines = [
            "",
            colorize("=== INTERROGATION ===", Color.BRIGHT_RED),
            "",
            f"Info gathered: {info_gained}/{target_info}",
            f"Target stress: {colorize('█' * (stress // 10), Color.RED if stress > 70 else Color.YELLOW)}",
            "",
            "Choose approach:"
        ]
        
        for i, (question, approach, stress_change, info_change) in enumerate(questions, 1):
            lines.append(f"{i}) {question} ({approach})")
        
        lines.append("")
        lines.append(colorize("What do you do?", Color.YELLOW))
        
        draw_panel(5, lines, center=True)
        
        choice = wait_for_key(['1', '2', '3', '4'], timeout=10.0)
        
        if choice and choice in ['1', '2', '3', '4']:
            idx = int(choice) - 1
            stress += questions[idx][2]
            
            if stress > 80:
                animate_transition("They shut down!")
                return False
            
            if random.random() < 0.5:
                info_gained += 1
                animate_transition("They're talking!")
            else:
                animate_transition("They resist...")
        else:
            stress -= 10
            
    return info_gained >= target_info

def minigame_disguise(state: GameState) -> bool:
    """Disguise and blend in"""
    height, width = get_terminal_size()
    
    suspicion = 0
    checkpoints = 3
    passed = 0
    
    disguises = ["Guard", "Janitor", "Executive", "Technician"]
    current_disguise = random.choice(disguises)
    
    for checkpoint in range(checkpoints):
        clear_screen()
        
        required_disguise = random.choice(disguises)
        
        lines = [
            "",
            colorize(f"=== CHECKPOINT {checkpoint + 1}/{checkpoints} ===", Color.BRIGHT_YELLOW),
            "",
            f"Your disguise: {colorize(current_disguise, Color.GREEN)}",
            f"They're looking for: {colorize(required_disguise, Color.RED)}",
            f"Suspicion: {colorize('█' * suspicion, Color.RED)}",
            "",
            "1) Walk confidently",
            "2) Avoid eye contact",
            "3) Show fake ID",
            "4) Change disguise",
            ""
        ]
        
        draw_panel(5, lines, center=True)
        
        choice = wait_for_key(['1', '2', '3', '4'], timeout=8.0)
        
        if current_disguise == required_disguise:
            passed += 1
            animate_transition("Passed!")
        elif choice == '4':
            current_disguise = random.choice([d for d in disguises if d != current_disguise])
            suspicion += 1
            animate_transition(f"Changed to {current_disguise}")
        elif choice == '1':
            if random.random() < 0.5:
                passed += 1
                animate_transition("Bluffed through!")
            else:
                suspicion += 2
                animate_transition("They're suspicious...")
        elif choice == '2':
            suspicion += 1
        elif choice == '3':
            if random.random() < 0.6:
                passed += 1
                animate_transition("ID accepted!")
            else:
                suspicion += 3
                animate_transition("Fake detected!")
        
        if suspicion >= 5:
            animate_transition("COVER BLOWN!")
            return False
            
    return passed >= checkpoints // 2

# === MISSIONS ===

def mission_tutorial(state: GameState) -> bool:
    """Tutorial mission: Steal a car and escape"""
    height, width = get_terminal_size()

    # Story intro
    clear_screen()
    draw_hud(state)

    story = [
        "",
        colorize("=== FIRST WHEELS ===", Color.BRIGHT_YELLOW),
        "",
        "You need cash, and fast.",
        "Time to borrow a car... permanently.",
        "",
        colorize("Press ENTER to continue", Color.DIM)
    ]

    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])

    # Choice
    clear_screen()
    draw_hud(state)

    choice_text = [
        "",
        "You spot two cars:",
        "",
        colorize("1)", Color.YELLOW) + " Sports car (fast, but alarm)",
        colorize("2)", Color.YELLOW) + " Old sedan (slow, quiet)",
        "",
        "Your choice? (1/2)"
    ]

    draw_panel(5, choice_text, center=True)
    choice = wait_for_key(['1', '2'])

    if choice == '1':
        state.heat = 2
        difficulty = 2
        animate_transition("*ALARM BLARING*")
    else:
        state.heat = 1
        difficulty = 1
        animate_transition("You hot-wire the sedan...")

    # Driving minigame
    success = minigame_driving(state, duration=10, difficulty=difficulty)

    if success:
        state.cash += 500
        state.completed_missions.append("tutorial")

        clear_screen()
        draw_hud(state)

        success_text = [
            "",
            colorize("MISSION COMPLETE!", Color.BRIGHT_GREEN),
            "",
            f"Earned: {colorize('$500', Color.YELLOW)}",
            "You've got the skills. Time to aim higher.",
            "",
            colorize("Press ENTER", Color.DIM)
        ]

        draw_panel(8, success_text, center=True)
        wait_for_key(['ENTER'])

        # Reset heat
        state.heat = 0
        return True
    else:
        # Failed but continue (fail-forward)
        state.cash += 100
        state.completed_missions.append("tutorial")
        state.players[state.current_player].hp = 50

        clear_screen()
        draw_hud(state)

        fail_text = [
            "",
            colorize("WRECKED!", Color.RED),
            "",
            "You barely escaped, but at least you learned something.",
            f"Earned: {colorize('$100', Color.YELLOW)}",
            "",
            colorize("Press ENTER", Color.DIM)
        ]

        draw_panel(8, fail_text, center=True)
        wait_for_key(['ENTER'])

        state.heat = 0
        return True

def mission_recruit_crew(state: GameState) -> bool:
    """Mission: Find and recruit crew members"""
    height, width = get_terminal_size()

    clear_screen()
    draw_hud(state)

    story = [
        "",
        colorize("=== BUILDING THE TEAM ===", Color.BRIGHT_YELLOW),
        "",
        "You can't pull big jobs alone.",
        "Time to assemble a crew.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]

    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])

    # Show available crew
    available_crew = [c for c in state.crew_members if not c.recruited and c.available]

    if not available_crew:
        # Initialize crew pool if empty
        state.crew_members = create_crew_pool()
        available_crew = state.crew_members[:3]

    recruited_count = 0

    for crew in available_crew[:3]:  # Show 3 options
        clear_screen()
        draw_hud(state)

        crew_info = [
            "",
            colorize(f"Meet {crew.name}", Color.BRIGHT_CYAN),
            "",
            f"Role: {colorize(crew.role.upper(), Color.YELLOW)}",
            f"Skill: {colorize('★' * crew.skill + '☆' * (10 - crew.skill), Color.YELLOW)}",
            f"Cost: {colorize(f'${crew.cost:,}', Color.YELLOW)}",
            "",
            "1) Recruit (pay upfront)",
            "2) Skip",
            "",
            f"Your cash: {colorize(f'${state.cash:,}', Color.GREEN)}"
        ]

        draw_panel(5, crew_info, center=True)
        choice = wait_for_key(['1', '2'])

        if choice == '1' and state.cash >= crew.cost:
            state.cash -= crew.cost
            crew.recruited = True
            crew.loyalty = 60
            recruited_count += 1

            animate_transition(f"{crew.name} joined the crew!")
        elif choice == '1':
            animate_transition("Not enough cash!")

    # Complete mission
    state.completed_missions.append("recruit_crew")
    state.cash += 1000

    clear_screen()
    draw_hud(state)

    result = [
        "",
        colorize("MISSION COMPLETE!", Color.BRIGHT_GREEN),
        "",
        f"Recruited: {recruited_count} crew members",
        f"Reward: {colorize('$1,000', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]

    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])

    return True

def mission_mini_heist(state: GameState) -> bool:
    """Mini heist with three approach options"""
    height, width = get_terminal_size()

    clear_screen()
    draw_hud(state)

    story = [
        "",
        colorize("=== SMALL TIME SCORE ===", Color.BRIGHT_YELLOW),
        "",
        "A jewelry store, light security.",
        "Time to test your skills.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]

    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])

    # Approach selection
    clear_screen()
    draw_hud(state)

    approaches = [
        "",
        colorize("Choose your approach:", Color.BRIGHT_CYAN),
        "",
        colorize("1) STEALTH", Color.GREEN) + " - Hack the alarm, sneak in",
        colorize("2) LOUD", Color.RED) + " - Smash and grab, fast escape",
        colorize("3) DRIVER", Color.YELLOW) + " - Distraction, quick getaway",
        "",
        "Your choice? (1/2/3)"
    ]

    draw_panel(6, approaches, center=True)
    choice = wait_for_key(['1', '2', '3'])

    success = False
    payout = 5000

    if choice == '1':
        # Stealth = hacking
        animate_transition("Bypassing alarm system...")
        success = minigame_hacking(state, complexity=3)
        if success:
            state.heat = 0
            payout = 7000  # Bonus for stealth
        else:
            state.heat = 3
            payout = 2000

    elif choice == '2':
        # Loud = driving escape
        animate_transition("*SMASH* Grab everything!")
        state.heat = 4
        success = minigame_driving(state, duration=12, difficulty=3)
        if success:
            payout = 6000
        else:
            payout = 3000

    else:
        # Driver approach
        animate_transition("Creating diversion...")
        state.heat = 2
        success = minigame_driving(state, duration=10, difficulty=2)
        if success:
            payout = 5000
        else:
            payout = 2500

    # Complete mission
    state.completed_missions.append("mini_heist")
    state.cash += payout

    clear_screen()
    draw_hud(state)

    result = [
        "",
        colorize("JOB DONE!", Color.BRIGHT_GREEN) if success else colorize("BARELY ESCAPED!", Color.YELLOW),
        "",
        f"Earned: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]

    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])

    # Decay heat
    state.heat = max(0, state.heat - 1)

    return True

def mission_prep_arcadia(state: GameState) -> bool:
    """Prep mission for the big heist"""
    height, width = get_terminal_size()

    clear_screen()
    draw_hud(state)

    story = [
        "",
        colorize("=== ARCADIA PREP ===", Color.BRIGHT_YELLOW),
        "",
        "The Arcadia vault. Big score.",
        "But first, you need intel.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]

    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])

    # Intel gathering (simple hacking)
    animate_transition("Accessing security network...")

    success = minigame_hacking(state, complexity=4)

    if success:
        clear_screen()
        draw_hud(state)

        intel = [
            "",
            colorize("INTEL ACQUIRED", Color.BRIGHT_GREEN),
            "",
            "• Vault has biometric locks",
            "• Guard rotation every 4 hours",
            "• Three entry points discovered",
            "• Backup power system identified",
            "",
            "You're ready for the big job.",
            "",
            colorize("Press ENTER", Color.DIM)
        ]

        draw_panel(6, intel, center=True)
        wait_for_key(['ENTER'])

    state.completed_missions.append("prep_arcadia")
    state.cash += 2000

    return True

def mission_arcadia_heist(state: GameState) -> bool:
    """The big heist with planning and execution"""
    height, width = get_terminal_size()

    # === PLANNING PHASE ===
    clear_screen()
    draw_hud(state)

    planning = [
        "",
        colorize("=== THE ARCADIA JOB ===", Color.BRIGHT_YELLOW),
        "",
        "This is it. The big one.",
        "Plan carefully.",
        "",
        colorize("Press ENTER to plan", Color.DIM)
    ]

    draw_panel(5, planning, center=True)
    wait_for_key(['ENTER'])

    # Choose approach
    clear_screen()
    draw_hud(state)

    approaches = [
        "",
        colorize("Choose your approach:", Color.BRIGHT_CYAN),
        "",
        colorize("1) STEALTH", Color.GREEN) + " - Hack systems, silent entry (high skill)",
        colorize("2) LOUD", Color.RED) + " - Heavy weapons, smash through (high risk)",
        colorize("3) DRIVER", Color.YELLOW) + " - Fast in/out, focus on escape (balanced)",
        "",
        "Your choice? (1/2/3)"
    ]

    draw_panel(6, approaches, center=True)
    approach = wait_for_key(['1', '2', '3'])

    if approach == '1':
        state.heist_plan = "stealth"
        animate_transition("Planning stealth approach...")
    elif approach == '2':
        state.heist_plan = "loud"
        animate_transition("Planning loud approach...")
    else:
        state.heist_plan = "driver"
        animate_transition("Planning driver approach...")

    # Assign crew
    recruited_crew = [c for c in state.crew_members if c.recruited]

    if recruited_crew:
        clear_screen()
        draw_hud(state)

        crew_list = [
            "",
            colorize("Assign crew members:", Color.BRIGHT_CYAN),
            ""
        ]

        for i, crew in enumerate(recruited_crew[:3], 1):
            crew_list.append(f"{i}) {crew.name} - {crew.role.upper()} (Skill: {crew.skill})")

        crew_list.append("")
        crew_list.append("Selection (e.g., 1,2) or ENTER to skip:")

        draw_panel(6, crew_list, center=True)

        # Simple selection (just press ENTER for now)
        wait_for_key(['ENTER'])

    # === EXECUTION PHASE ===

    animate_transition("Executing heist...")

    success_stage_1 = False
    success_stage_2 = False
    base_payout = 100000

    # Stage 1: Entry
    if state.heist_plan == "stealth":
        clear_screen()
        draw_hud(state)
        draw_panel(10, [colorize("Stage 1: Bypassing security...", Color.CYAN)], center=True)
        time.sleep(2)
        success_stage_1 = minigame_hacking(state, complexity=5)

        if not success_stage_1:
            state.heat = 5
            base_payout //= 2
            animate_transition("ALARM TRIGGERED!")
        else:
            state.heat = 1
            base_payout = int(base_payout * 1.5)

    elif state.heist_plan == "loud":
        animate_transition("Stage 1: Breaching vault!")
        state.heat = 5
        success_stage_1 = True  # Always succeeds but high heat

    else:  # driver
        animate_transition("Stage 1: Creating diversion!")
        state.heat = 3
        success_stage_1 = True

    # Stage 2: Escape
    clear_screen()
    draw_hud(state)
    draw_panel(10, [colorize("Stage 2: ESCAPE!", Color.BRIGHT_RED)], center=True)
    time.sleep(2)

    escape_duration = 20 if state.heat >= 4 else 15
    success_stage_2 = minigame_driving(state, duration=escape_duration, difficulty=state.heat)

    if not success_stage_2:
        base_payout //= 3
        state.players[state.current_player].hp = 30

    # Calculate final payout
    final_payout = base_payout

    # Apply crew bonuses
    for crew in recruited_crew:
        if crew.recruited:
            final_payout += crew.skill * 1000

    # Complete mission
    state.completed_missions.append("arcadia_heist")
    state.cash += final_payout

    # Results
    clear_screen()
    draw_hud(state)

    if success_stage_1 and success_stage_2:
        result = [
            "",
            colorize("╔═══════════════════════════╗", Color.BRIGHT_GREEN),
            colorize("║  HEIST COMPLETE - FLAWLESS  ║", Color.BRIGHT_GREEN),
            colorize("╚═══════════════════════════╝", Color.BRIGHT_GREEN),
            "",
            f"Total Payout: {colorize(f'${final_payout:,}', Color.BRIGHT_YELLOW)}",
            "",
            "You're a legend now.",
            "",
            colorize("Press ENTER", Color.DIM)
        ]
    else:
        result = [
            "",
            colorize("HEIST COMPLETE - MESSY", Color.YELLOW),
            "",
            f"Payout: {colorize(f'${final_payout:,}', Color.YELLOW)}",
            "",
            "You got away... barely.",
            "",
            colorize("Press ENTER", Color.DIM)
        ]

    draw_panel(7, result, center=True)
    wait_for_key(['ENTER'])

    # Reduce heat over time
    state.heat = max(0, state.heat - 2)

    return True

# === GAME MODES ===

# === ADDITIONAL MISSIONS ===

def mission_bank_robbery(state: GameState) -> bool:
    """Bank robbery mission"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== BANK ROBBERY ===", Color.BRIGHT_YELLOW),
        "",
        "A downtown bank, lightly guarded.",
        "Big risk, bigger reward.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Phase 1: Entry
    animate_transition("Approaching bank...")
    
    if not minigame_stealth(state, guards=4, duration=25):
        state.heat += 4
        animate_transition("ALARM!")
        payout = 10000
    else:
        state.heat += 1
        payout = 30000
    
    # Phase 2: Vault
    animate_transition("Cracking the vault...")
    
    if minigame_safecracking(state, difficulty=4):
        payout += 20000
    else:
        state.heat += 2
        payout = payout // 2
    
    # Phase 3: Escape
    if state.heat >= 3:
        animate_transition("POLICE INCOMING!")
        if not minigame_driving(state, duration=20, difficulty=state.heat):
            payout = payout // 3
            state.players[state.current_player].hp -= 30
    
    state.cash += payout
    state.completed_missions.append("bank_robbery")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("BANK ROBBED!", Color.BRIGHT_GREEN),
        "",
        f"Haul: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_jewelry_store(state: GameState) -> bool:
    """Smash and grab jewelry heist"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== DIAMOND DISTRICT ===", Color.BRIGHT_CYAN),
        "",
        "High-end jewelry store.",
        "Smash, grab, go!",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    animate_transition("*SMASH*")
    state.heat += 3
    
    # Quick grab
    if minigame_quick_time(state, events=6):
        payout = 25000
        animate_transition("Got the diamonds!")
    else:
        payout = 10000
        animate_transition("Dropped some!")
    
    # Escape
    animate_transition("RUN!")
    
    if minigame_chase_foot(state, duration=15):
        payout += 5000
    else:
        state.heat += 2
        payout = payout // 2
        state.players[state.current_player].hp -= 20
    
    state.cash += payout
    state.completed_missions.append("jewelry_store")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("JEWELRY HEIST COMPLETE!", Color.BRIGHT_GREEN),
        "",
        f"Value: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_armory_heist(state: GameState) -> bool:
    """Steal weapons from armory"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== ARMORY RAID ===", Color.BRIGHT_RED),
        "",
        "Military-grade weapons inside.",
        "Heavy security, heavy firepower.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Disable alarm
    animate_transition("Disabling security...")
    
    if minigame_alarm_disable(state):
        state.heat += 1
        payout = 40000
    else:
        state.heat += 5
        payout = 15000
        animate_transition("ALARM ACTIVE!")
    
    # Lockpicking
    if minigame_lockpicking(state):
        payout += 10000
    
    # Combat escape
    if state.heat >= 4:
        animate_transition("GUARDS INCOMING!")
        if minigame_shooting(state, targets=15, time_limit=25):
            payout += 5000
        else:
            payout = payout // 2
            state.players[state.current_player].hp -= 40
    
    state.cash += payout
    state.completed_missions.append("armory_heist")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("ARMORY CLEARED!", Color.BRIGHT_GREEN),
        "",
        f"Weapons sold: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 2)
    return True

def mission_drug_deal(state: GameState) -> bool:
    """Intercept drug deal"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== DRUG DEAL ===", Color.BRIGHT_MAGENTA),
        "",
        "Rival gang has a big shipment.",
        "Take it, sell it, profit.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Negotiation (fake)
    animate_transition("Meeting with dealers...")
    
    if minigame_negotiation(state, difficulty=3):
        payout = 20000
        state.heat += 1
    else:
        animate_transition("DEAL GONE BAD!")
        state.heat += 3
        payout = 5000
        
        # Shootout
        if minigame_shooting(state, targets=10, time_limit=20):
            payout += 10000
        else:
            state.players[state.current_player].hp -= 30
    
    # Escape
    if state.heat >= 3:
        if minigame_motorcycle(state, duration=15):
            payout += 5000
        else:
            payout = payout // 2
    
    state.cash += payout
    state.completed_missions.append("drug_deal")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("DEAL DONE!", Color.BRIGHT_GREEN),
        "",
        f"Profit: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_kidnapping(state: GameState) -> bool:
    """Kidnap and ransom VIP"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== KIDNAPPING ===", Color.BRIGHT_RED),
        "",
        "Rich target, easy snatch.",
        "Get the ransom, release them.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Snatch
    animate_transition("Grabbing target...")
    
    if minigame_quick_time(state, events=4):
        animate_transition("Target secured!")
        payout = 50000
        state.heat += 2
    else:
        animate_transition("Target escaped!")
        return False
    
    # Escape
    if minigame_driving(state, duration=15, difficulty=3):
        payout += 10000
    else:
        state.heat += 2
        payout = payout // 2
    
    # Negotiation
    animate_transition("Negotiating ransom...")
    
    if minigame_negotiation(state, difficulty=4):
        payout = int(payout * 1.5)
    
    state.cash += payout
    state.completed_missions.append("kidnapping")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("RANSOM PAID!", Color.BRIGHT_GREEN),
        "",
        f"Ransom: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_gang_war(state: GameState) -> bool:
    """Gang territory war"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== GANG WAR ===", Color.BRIGHT_RED),
        "",
        "Rival gang moving in on your turf.",
        "Defend your territory!",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Combat phases
    animate_transition("GANG INCOMING!")
    
    phase1 = minigame_shooting(state, targets=12, time_limit=20)
    phase2 = minigame_quick_time(state, events=5)
    phase3 = minigame_shooting(state, targets=8, time_limit=15)
    
    if phase1 and phase2 and phase3:
        payout = 30000
        state.heat += 2
        animate_transition("TERRITORY SECURED!")
    elif phase1 or phase2:
        payout = 15000
        state.heat += 3
        state.players[state.current_player].hp -= 30
        animate_transition("Barely held them off!")
    else:
        payout = 5000
        state.heat += 4
        state.players[state.current_player].hp -= 50
        animate_transition("Territory lost!")
    
    state.cash += payout
    state.completed_missions.append("gang_war")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("GANG WAR OVER!", Color.BRIGHT_GREEN),
        "",
        f"Earnings: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_corrupt_cop(state: GameState) -> bool:
    """Bribe/blackmail corrupt cop"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== CORRUPT COP ===", Color.BRIGHT_BLUE),
        "",
        "A dirty cop has info on you.",
        "Turn them to your side.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Approach choice
    clear_screen()
    draw_hud(state)
    approach = [
        "",
        "How do you handle this?",
        "",
        colorize("1)", Color.YELLOW) + " Bribe them ($10,000)",
        colorize("2)", Color.YELLOW) + " Blackmail them (risky)",
        colorize("3)", Color.YELLOW) + " Intimidate them (violent)",
        ""
    ]
    draw_panel(8, approach, center=True)
    choice = wait_for_key(['1', '2', '3'])
    
    if choice == '1' and state.cash >= 10000:
        state.cash -= 10000
        state.heat = max(0, state.heat - 2)
        animate_transition("Cop is on your payroll!")
        payout = 0
    elif choice == '2':
        if minigame_pickpocket(state, targets=1):
            state.heat = max(0, state.heat - 3)
            animate_transition("Got the dirt on them!")
            payout = 15000
        else:
            state.heat += 3
            animate_transition("They caught you!")
            return False
    else:
        if minigame_intimidation(state):
            state.heat += 1
            animate_transition("They're scared!")
            payout = 10000
        else:
            state.heat += 4
            state.players[state.current_player].hp -= 25
            animate_transition("Cop fought back!")
            return False
    
    state.cash += payout
    state.completed_missions.append("corrupt_cop")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("COP HANDLED!", Color.BRIGHT_GREEN),
        "",
        f"Heat reduced! Future jobs easier.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    return True

# Alias for interrogation
def minigame_intimidation(state: GameState) -> bool:
    return minigame_interrogation(state)

def mission_escape_prison(state: GameState) -> bool:
    """Break crew member out of prison"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== PRISON BREAK ===", Color.BRIGHT_YELLOW),
        "",
        "One of your crew is locked up.",
        "Time to break them out!",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Phase 1: Infiltrate
    animate_transition("Getting inside...")
    
    if not minigame_disguise(state):
        state.heat += 5
        animate_transition("COVER BLOWN!")
        return False
    
    # Phase 2: Find cell
    animate_transition("Navigating prison...")
    
    if not minigame_escape_building(state):
        state.heat += 4
        animate_transition("LOST!")
        return False
    
    # Phase 3: Break out
    animate_transition("Freeing prisoner...")
    
    if minigame_lockpicking(state):
        animate_transition("They're free!")
    else:
        state.heat += 3
        animate_transition("Alarm triggered!")
    
    # Phase 4: Escape
    if minigame_driving(state, duration=25, difficulty=5):
        payout = 20000
        state.heat += 2
    else:
        payout = 0
        state.heat += 5
        state.players[state.current_player].hp -= 40
    
    state.cash += payout
    state.completed_missions.append("escape_prison")
    
    # Free a random crew member
    locked_crew = [c for c in state.crew_members if c.recruited and not c.available]
    if locked_crew:
        locked_crew[0].available = True
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("PRISON BREAK SUCCESS!", Color.BRIGHT_GREEN),
        "",
        "Crew member freed!",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    return True

def mission_car_theft_ring(state: GameState) -> bool:
    """Steal luxury cars for export"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== CAR THEFT RING ===", Color.BRIGHT_CYAN),
        "",
        "List of high-value cars to steal.",
        "More cars = more money!",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    cars_stolen = 0
    target_cars = 5
    
    for car_num in range(target_cars):
        animate_transition(f"Stealing car {car_num + 1}/{target_cars}...")
        
        # Steal car
        if minigame_lockpicking(state):
            cars_stolen += 1
            
            # Evade police
            if random.random() < 0.4:
                state.heat += 1
                if not minigame_driving(state, duration=10, difficulty=2):
                    cars_stolen -= 1
                    state.heat += 1
        else:
            state.heat += 1
            
        if state.heat >= 5:
            animate_transition("Too hot! Aborting!")
            break
    
    payout = cars_stolen * 8000
    state.cash += payout
    state.completed_missions.append("car_theft_ring")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("CARS DELIVERED!", Color.BRIGHT_GREEN),
        "",
        f"Cars stolen: {cars_stolen}/{target_cars}",
        f"Payment: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_smuggling(state: GameState) -> bool:
    """Smuggle contraband across the city"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== SMUGGLING RUN ===", Color.BRIGHT_MAGENTA),
        "",
        "Illegal goods need transport.",
        "Don't get caught!",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Long drive with checkpoints
    animate_transition("Loading cargo...")
    
    checkpoints_passed = 0
    total_checkpoints = 3
    
    for checkpoint in range(total_checkpoints):
        animate_transition(f"Checkpoint {checkpoint + 1}/{total_checkpoints}...")
        
        # Random encounter
        if random.random() < 0.5:
            animate_transition("POLICE CHECKPOINT!")
            
            if minigame_disguise(state):
                checkpoints_passed += 1
            else:
                state.heat += 2
                
                # Chase
                if minigame_driving(state, duration=15, difficulty=3):
                    checkpoints_passed += 1
                else:
                    state.heat += 2
                    break
        else:
            checkpoints_passed += 1
            animate_transition("Clear!")
    
    payout = checkpoints_passed * 15000
    state.cash += payout
    state.completed_missions.append("smuggling")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("SMUGGLING COMPLETE!", Color.BRIGHT_GREEN),
        "",
        f"Checkpoints: {checkpoints_passed}/{total_checkpoints}",
        f"Payment: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_casino_heist(state: GameState) -> bool:
    """Rob a casino - Ocean's Eleven style"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== CASINO HEIST ===", Color.BRIGHT_YELLOW),
        "",
        "The big score.",
        "Plan carefully, execute perfectly.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Planning phase
    animate_transition("Planning the heist...")
    
    # Phase 1: Disguise entry
    if not minigame_disguise(state):
        state.heat += 5
        animate_transition("Bounced by security!")
        return False
    
    # Phase 2: Disable security
    animate_transition("Disabling cameras...")
    
    if minigame_alarm_disable(state):
        payout = 100000
    else:
        state.heat += 3
        payout = 50000
        animate_transition("Partial disable!")
    
    # Phase 3: Vault
    animate_transition("Cracking vault...")
    
    if minigame_safecracking(state, difficulty=5):
        payout += 50000
    else:
        state.heat += 3
        payout = payout // 2
    
    # Phase 4: Escape
    animate_transition("SECURITY ALERTED!")
    
    if minigame_stealth(state, guards=8, duration=40):
        payout += 25000
    else:
        state.heat += 4
        if not minigame_driving(state, duration=25, difficulty=5):
            payout = payout // 3
            state.players[state.current_player].hp -= 40
    
    state.cash += payout
    state.completed_missions.append("casino_heist")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("╔═══════════════════════════╗", Color.BRIGHT_YELLOW),
        colorize("║  CASINO HEIST SUCCESS!    ║", Color.BRIGHT_YELLOW),
        colorize("╚═══════════════════════════╝", Color.BRIGHT_YELLOW),
        "",
        f"Total haul: {colorize(f'${payout:,}', Color.BRIGHT_GREEN)}",
        "",
        "Living large!",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(6, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 2)
    return True

def mission_art_gallery(state: GameState) -> bool:
    """Steal priceless art"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== ART GALLERY ===", Color.BRIGHT_CYAN),
        "",
        "Priceless paintings, minimal security.",
        "A collector is paying top dollar.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    # Stealth mission
    animate_transition("Infiltrating gallery...")
    
    if not minigame_stealth(state, guards=6, duration=35):
        state.heat += 4
        animate_transition("DETECTED!")
        return False
    
    # Disable alarms
    animate_transition("Disabling alarms...")
    
    if minigame_alarm_disable(state):
        payout = 60000
    else:
        state.heat += 3
        payout = 30000
    
    # Grab art
    animate_transition("Taking the paintings...")
    
    if minigame_quick_time(state, events=5):
        payout += 20000
    else:
        state.heat += 2
    
    # Escape
    if state.heat >= 3:
        if not minigame_escape_building(state):
            payout = payout // 2
            state.heat += 2
    
    state.cash += payout
    state.completed_missions.append("art_gallery")
    
    clear_screen()
    draw_hud(state)
    result = [
        "",
        colorize("ART STOLEN!", Color.BRIGHT_GREEN),
        "",
        f"Art value: {colorize(f'${payout:,}', Color.YELLOW)}",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    draw_panel(8, result, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = max(0, state.heat - 1)
    return True

def mission_final_showdown(state: GameState) -> bool:
    """Final epic mission"""
    height, width = get_terminal_size()
    
    clear_screen()
    draw_hud(state)
    
    story = [
        "",
        colorize("=== THE FINAL SHOWDOWN ===", Color.BRIGHT_RED),
        "",
        "Everything has led to this.",
        "One last job. The biggest yet.",
        "",
        "All your skills will be tested.",
        "",
        colorize("Press ENTER when ready", Color.BRIGHT_YELLOW)
    ]
    draw_panel(5, story, center=True)
    wait_for_key(['ENTER'])
    
    payout = 200000
    phases_completed = 0
    total_phases = 6
    
    # Phase 1: Infiltration
    animate_transition("Phase 1: Infiltration")
    if minigame_disguise(state):
        phases_completed += 1
        payout += 50000
    else:
        state.heat += 2
    
    # Phase 2: Hacking
    animate_transition("Phase 2: Security Systems")
    if minigame_hacking(state, complexity=5):
        phases_completed += 1
        payout += 50000
    else:
        state.heat += 2
    
    # Phase 3: Combat
    animate_transition("Phase 3: Hostile Contact!")
    if minigame_shooting(state, targets=20, time_limit=30):
        phases_completed += 1
        payout += 50000
    else:
        state.players[state.current_player].hp -= 30
    
    # Phase 4: Vault
    animate_transition("Phase 4: The Vault")
    if minigame_safecracking(state, difficulty=5):
        phases_completed += 1
        payout += 100000
    else:
        state.heat += 3
    
    # Phase 5: Extraction
    animate_transition("Phase 5: Escape Route")
    if minigame_escape_building(state):
        phases_completed += 1
        payout += 50000
    else:
        state.heat += 2
    
    # Phase 6: Final Chase
    animate_transition("Phase 6: THE ENTIRE CITY IS AFTER YOU!")
    state.heat = 5
    
    if minigame_driving(state, duration=30, difficulty=5):
        phases_completed += 1
        payout += 100000
        animate_transition("YOU MADE IT!")
    else:
        payout = payout // 2
        state.players[state.current_player].hp -= 50
        animate_transition("Barely escaped with your life!")
    
    state.cash += payout
    state.completed_missions.append("final_showdown")
    
    # Epic finale
    clear_screen()
    
    finale = [
        "",
        colorize("╔══════════════════════════════════╗", Color.BRIGHT_YELLOW),
        colorize("║                                  ║", Color.BRIGHT_YELLOW),
        colorize("║     CONGRATULATIONS!             ║", Color.BRIGHT_YELLOW),
        colorize("║                                  ║", Color.BRIGHT_YELLOW),
        colorize("╚══════════════════════════════════╝", Color.BRIGHT_YELLOW),
        "",
        colorize("YOU COMPLETED TERMINAL HEIST!", Color.BRIGHT_GREEN),
        "",
        f"Phases completed: {colorize(f'{phases_completed}/{total_phases}', Color.CYAN)}",
        f"Final haul: {colorize(f'${payout:,}', Color.BRIGHT_YELLOW)}",
        f"Total wealth: {colorize(f'${state.cash:,}', Color.BRIGHT_GREEN)}",
        "",
        f"Missions completed: {len(state.completed_missions)}",
        f"Character: {state.players[state.current_player].name}",
        "",
        "You're a legend now.",
        "",
        colorize("Press ENTER", Color.DIM)
    ]
    
    draw_panel(3, finale, center=True)
    wait_for_key(['ENTER'])
    
    state.heat = 0
    return True


def show_main_menu(state: GameState) -> str:
    """Show main menu and return choice"""
    height, width = get_terminal_size()

    clear_screen()

    title = [
        "",
        colorize("╔════════════════════════════════╗", Color.BRIGHT_CYAN),
        colorize("║      TERMINAL HEIST            ║", Color.BRIGHT_CYAN),
        colorize("║                                ║", Color.BRIGHT_CYAN),
        colorize("║  GTA-inspired Heist Game       ║", Color.YELLOW),
        colorize("╚════════════════════════════════╝", Color.BRIGHT_CYAN),
        "",
        "",
        colorize("N", Color.BRIGHT_YELLOW) + ") New Game",
        colorize("L", Color.BRIGHT_YELLOW) + ") Load Game",
        colorize("E", Color.BRIGHT_YELLOW) + ") Exit",
        "",
        "",
        colorize("Your choice?", Color.DIM)
    ]

    draw_panel(3, title, center=True)

    choice = wait_for_key(['N', 'L', 'E'])
    return choice

def show_map(state: GameState):
    """Show city map with zones"""
    height, width = get_terminal_size()

    zones = create_city_zones()
    missions = create_missions()

    # Show first-time hint
    first_time = len(state.completed_missions) == 0
    if first_time:
        clear_screen()
        hint = [
            "",
            colorize("=== QUICK START ===", Color.BRIGHT_CYAN),
            "",
            "You're at Downtown (D on the map).",
            "Press ENTER to start your first mission!",
            "",
            colorize("Tip: WASD to move, Q to switch character, I for shop", Color.DIM),
            "",
            colorize("Press any key to continue", Color.YELLOW)
        ]
        draw_panel(height // 2 - 5, hint, center=True)
        wait_for_key(timeout=10.0)

    while True:
        clear_screen()
        draw_hud(state)

        # Draw map grid
        map_size = 12
        map_start_y = 4
        map_start_x = (width - map_size * 2) // 2

        move_cursor(map_start_y - 1, map_start_x)
        print(colorize("=== CITY MAP ===", Color.BRIGHT_CYAN))

        # Draw grid
        for y in range(map_size):
            move_cursor(map_start_y + y, map_start_x)
            for x in range(map_size):
                char = "·"
                color = Color.DIM

                # Check for zones
                for zone in zones:
                    if zone.x == x and zone.y == y:
                        char = zone.char
                        color = zone.color
                        break

                # Check for cursor
                if x == state.map_cursor_x and y == state.map_cursor_y:
                    print(colorize("█", Color.BRIGHT_WHITE), end=" ")
                else:
                    print(colorize(char, color), end=" ")

        # Show zone info
        current_zone = None
        for zone in zones:
            if zone.x == state.map_cursor_x and zone.y == state.map_cursor_y:
                current_zone = zone
                break

        info_y = map_start_y + map_size + 2

        if current_zone:
            info = [
                f"Location: {colorize(current_zone.name, Color.BRIGHT_YELLOW)}",
                ""
            ]

            # Show available missions
            available = False
            for mission_id in current_zone.missions:
                mission = next((m for m in missions if m.id == mission_id), None)
                if mission and mission_id not in state.completed_missions:
                    # Check if required mission is complete
                    if not mission.required_mission or mission.required_mission in state.completed_missions:
                        info.append(colorize(f"► {mission.name}", Color.BRIGHT_GREEN))
                        info.append(f"  {mission.description}")
                        available = True

            if available:
                info.append("")
                info.append(colorize(">>> Press ENTER to start! <<<", Color.BRIGHT_YELLOW))
            else:
                info.append(colorize("No missions available here.", Color.DIM))

            draw_panel(info_y, info, center=True)
        else:
            draw_panel(info_y, [
                colorize("Move cursor to a zone marker (H/D/S/I)", Color.DIM),
                "",
                "H=Harbor, D=Downtown, S=Suburbs, I=Industrial"
            ], center=True)

        # Controls
        move_cursor(height - 2, 1)
        print(colorize("WASD=Move | ENTER=Select | ESC=Back | Q=Char Switch | I=Shop", Color.DIM))

        sys.stdout.flush()

        # Input - use blocking read for better control
        key = read_key_blocking(timeout=0.1)

        if not key:
            continue

        # Handle movement
        if key == 'W' and state.map_cursor_y > 0:
            state.map_cursor_y -= 1
        elif key == 'S' and state.map_cursor_y < map_size - 1:
            state.map_cursor_y += 1
        elif key == 'A' and state.map_cursor_x > 0:
            state.map_cursor_x -= 1
        elif key == 'D' and state.map_cursor_x < map_size - 1:
            state.map_cursor_x += 1

        # Handle actions
        elif key == 'ENTER' or key == '\r' or key == '\n':
            # Start mission if available
            if current_zone:
                mission_started = False
                for mission_id in current_zone.missions:
                    mission = next((m for m in missions if m.id == mission_id), None)
                    if mission and mission_id not in state.completed_missions:
                        if not mission.required_mission or mission.required_mission in state.completed_missions:
                            state.current_mission = mission_id
                            animate_transition(f"Starting: {mission.name}")
                            start_mission(state, mission_id)
                            mission_started = True
                            break
                if not mission_started and current_zone:
                    animate_transition("No missions available here!")

        elif key == 'ESC' or key == '\x1b' or key.startswith('\x1b'):
            break
        elif key == 'Q':
            try_character_switch(state)
        elif key == 'I':
            show_shop(state)
        elif key == 'H':
            show_heist_planning(state)

def show_shop(state: GameState):
    """Show upgrade shop"""
    height, width = get_terminal_size()

    upgrades = [
        ("Vehicle Handling", "vehicle_handling", 2000, 5),
        ("Hacking Level", "hacking_level", 3000, 5),
        ("Armor Level", "armor_level", 2500, 5),
        ("Med Kit (Restore 50 HP)", "medkit", 500, 999),
    ]

    while True:
        clear_screen()
        draw_hud(state)

        player = state.players[state.current_player]

        shop_lines = [
            "",
            colorize("=== UPGRADE SHOP ===", Color.BRIGHT_CYAN),
            "",
            f"Your Cash: {colorize(f'${state.cash:,}', Color.YELLOW)}",
            ""
        ]

        for i, (name, attr, cost, max_level) in enumerate(upgrades, 1):
            if attr == "medkit":
                shop_lines.append(f"{i}) {name} - {colorize(f'${cost}', Color.YELLOW)}")
            else:
                current = getattr(player, attr)
                if current < max_level:
                    shop_lines.append(f"{i}) {name} Lv{current} → Lv{current+1} - {colorize(f'${cost}', Color.YELLOW)}")
                else:
                    shop_lines.append(f"{i}) {name} - {colorize('MAX', Color.GREEN)}")

        shop_lines.append("")
        shop_lines.append(colorize("Choose upgrade (1-4) or ESC to exit", Color.DIM))

        draw_panel(5, shop_lines, center=True)

        choice = wait_for_key(['1', '2', '3', '4'])

        if choice == 'ESC' or choice == '\x1b' or not choice:
            break

        if choice in ['1', '2', '3', '4']:
            idx = int(choice) - 1
            name, attr, cost, max_level = upgrades[idx]

            if attr == "medkit":
                if state.cash >= cost:
                    state.cash -= cost
                    player.hp = min(player.max_hp, player.hp + 50)
                    animate_transition("HP Restored!")
                else:
                    animate_transition("Not enough cash!")
            else:
                current = getattr(player, attr)
                if current < max_level and state.cash >= cost:
                    state.cash -= cost
                    setattr(player, attr, current + 1)
                    animate_transition(f"{name} upgraded!")
                elif current >= max_level:
                    animate_transition("Already at max level!")
                else:
                    animate_transition("Not enough cash!")

        time.sleep(0.1)

def show_heist_planning(state: GameState):
    """Show heist planning screen"""
    height, width = get_terminal_size()

    # Check if Arcadia prep is complete
    if "prep_arcadia" not in state.completed_missions:
        animate_transition("No heists available yet!")
        return

    if "arcadia_heist" in state.completed_missions:
        animate_transition("You already completed the big heist!")
        return

    clear_screen()
    draw_hud(state)

    planning = [
        "",
        colorize("=== HEIST PLANNING ===", Color.BRIGHT_CYAN),
        "",
        "Ready to hit the Arcadia vault?",
        "",
        colorize("1)", Color.YELLOW) + " Start the heist",
        colorize("2)", Color.YELLOW) + " Not yet",
        ""
    ]

    draw_panel(8, planning, center=True)

    choice = wait_for_key(['1', '2'])

    if choice == '1':
        state.current_mission = "arcadia_heist"
        start_mission(state, "arcadia_heist")

def try_character_switch(state: GameState):
    """Try to switch character with cooldown"""
    current_time = time.time()
    cooldown = 10.0

    if current_time - state.last_char_switch < cooldown:
        remaining = cooldown - (current_time - state.last_char_switch)
        animate_transition(f"Character switch on cooldown: {remaining:.1f}s")
        return

    # Switch to next character
    state.current_player = (state.current_player + 1) % len(state.players)
    state.last_char_switch = current_time

    player = state.players[state.current_player]
    animate_transition(f"Switched to {player.name} ({player.role})")

def start_mission(state: GameState, mission_id: str):
    """Start a specific mission"""
    mission_funcs = {
        "tutorial": mission_tutorial,
        "recruit_crew": mission_recruit_crew,
        "mini_heist": mission_mini_heist,
        "bank_robbery": mission_bank_robbery,
        "jewelry_store": mission_jewelry_store,
        "armory_heist": mission_armory_heist,
        "drug_deal": mission_drug_deal,
        "kidnapping": mission_kidnapping,
        "gang_war": mission_gang_war,
        "corrupt_cop": mission_corrupt_cop,
        "escape_prison": mission_escape_prison,
        "car_theft_ring": mission_car_theft_ring,
        "smuggling": mission_smuggling,
        "casino_heist": mission_casino_heist,
        "art_gallery": mission_art_gallery,
        "prep_arcadia": mission_prep_arcadia,
        "arcadia_heist": mission_arcadia_heist,
        "final_showdown": mission_final_showdown,
    }


    func = mission_funcs.get(mission_id)
    if func:
        state.current_mission = mission_id
        func(state)
        state.current_mission = None

        # HP regeneration after mission
        for player in state.players:
            player.hp = min(player.max_hp, player.hp + 20)

# === PERSISTENCE ===

def save_game(state: GameState, filename: str = "savegame.json"):
    """Save game state to JSON"""
    try:
        # Convert to dict
        data = {
            "schema_version": state.schema_version,
            "current_player": state.current_player,
            "players": [asdict(p) for p in state.players],
            "last_char_switch": state.last_char_switch,
            "cash": state.cash,
            "heat": state.heat,
            "current_zone": state.current_zone,
            "current_mission": state.current_mission,
            "completed_missions": state.completed_missions,
            "active_mission_state": state.active_mission_state,
            "crew_members": [asdict(c) for c in state.crew_members],
            "heist_plan": state.heist_plan,
            "heist_crew": state.heist_crew,
            "mode": state.mode,
            "map_cursor_x": state.map_cursor_x,
            "map_cursor_y": state.map_cursor_y,
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        return True
    except Exception as e:
        print(f"Save failed: {e}")
        return False

def load_game(filename: str = "savegame.json") -> Optional[GameState]:
    """Load game state from JSON"""
    try:
        if not os.path.exists(filename):
            return None

        with open(filename, 'r') as f:
            data = json.load(f)

        # Reconstruct state
        state = GameState()
        state.schema_version = data.get("schema_version", 1)
        state.current_player = data.get("current_player", 0)

        # Reconstruct players
        state.players = [Player(**p) for p in data.get("players", [])]
        if not state.players:
            state.players = create_initial_players()

        state.last_char_switch = data.get("last_char_switch", 0.0)
        state.cash = data.get("cash", 1000)
        state.heat = data.get("heat", 0)
        state.current_zone = data.get("current_zone", "downtown")
        state.current_mission = data.get("current_mission")
        state.completed_missions = data.get("completed_missions", [])
        state.active_mission_state = data.get("active_mission_state", {})

        # Reconstruct crew
        state.crew_members = [CrewMember(**c) for c in data.get("crew_members", [])]
        if not state.crew_members:
            state.crew_members = create_crew_pool()

        state.heist_plan = data.get("heist_plan")
        state.heist_crew = data.get("heist_crew", {})
        state.mode = data.get("mode", "MENU")
        state.map_cursor_x = data.get("map_cursor_x", 5)
        state.map_cursor_y = data.get("map_cursor_y", 5)

        return state

    except Exception as e:
        print(f"Load failed: {e}")
        return None

# === MAIN GAME LOOP ===

def new_game() -> GameState:
    """Create a new game state"""
    state = GameState()
    state.players = create_initial_players()
    state.crew_members = create_crew_pool()
    state.mode = "MAP"
    state.cash = 1000
    state.heat = 0
    state.current_player = 0
    state.completed_missions = []

    # Start at Downtown (where tutorial mission is)
    state.map_cursor_x = 5
    state.map_cursor_y = 5

    # Show intro
    height, width = get_terminal_size()
    clear_screen()

    intro = [
        "",
        colorize("Welcome to Terminal Heist", Color.BRIGHT_CYAN),
        "",
        "You are a crew of three:",
        "",
        colorize("MAREK", Color.YELLOW) + " - The Driver (+20% dodge)",
        colorize("LIA", Color.YELLOW) + " - The Hacker (-25% hack time)",
        colorize("REX", Color.YELLOW) + " - The Gunner (+15% damage)",
        "",
        "Build your crew, plan heists, get rich.",
        "",
        "Use WASD to move, ENTER to start missions.",
        "",
        colorize("Press ENTER to start", Color.DIM)
    ]

    draw_panel(5, intro, center=True)
    wait_for_key(['ENTER'])

    return state

def game_loop():
    """Main game loop"""
    global USE_COLOR

    # Parse command line args
    if "--no-color" in sys.argv:
        USE_COLOR = False

    if "--seed" in sys.argv:
        idx = sys.argv.index("--seed")
        if idx + 1 < len(sys.argv):
            seed = int(sys.argv[idx + 1])
            random.seed(seed)

    state = None

    try:
        while True:
            choice = show_main_menu(state or GameState())

            if choice == 'N':
                state = new_game()
                show_map(state)

            elif choice == 'L':
                loaded = load_game()
                if loaded:
                    state = loaded
                    animate_transition("Game loaded!")
                    show_map(state)
                else:
                    animate_transition("No save file found!")

            elif choice == 'E':
                # Offer to save
                if state and state.mode != "MENU":
                    clear_screen()
                    height, width = get_terminal_size()

                    save_prompt = [
                        "",
                        "Save before exit?",
                        "",
                        colorize("Y", Color.GREEN) + ") Yes",
                        colorize("N", Color.RED) + ") No",
                        ""
                    ]

                    draw_panel(height // 2 - 3, save_prompt, center=True)

                    save_choice = wait_for_key(['Y', 'N'])

                    if save_choice == 'Y':
                        if save_game(state):
                            animate_transition("Game saved!")
                        else:
                            animate_transition("Save failed!")

                clear_screen()
                show_cursor()
                print(colorize("Thanks for playing Terminal Heist!", Color.BRIGHT_CYAN))
                break

            time.sleep(0.1)

    except KeyboardInterrupt:
        clear_screen()
        show_cursor()
        print("\nGame interrupted. Goodbye!")
    except Exception as e:
        clear_screen()
        show_cursor()
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

# === ENTRY POINT ===

if __name__ == "__main__":
    try:
        game_loop()
    finally:
        show_cursor()
        print(Color.RESET)
