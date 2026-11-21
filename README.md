# Terminal Heist

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/redbasecap)

A GTA-inspired heist game that runs in your terminal: three playable
protagonists (Marek, Lia, Rex), 18 missions, crew recruitment, heist
planning and ASCII-animated minigames such as hacking, safecracking,
lockpicking and car chases.

One Python file, standard library only. Python 3.10+ on macOS, Linux or
Windows.

## Play

```bash
git clone https://github.com/redbasecap/terminal-gta.git
cd terminal-gta
python3 game.py
```

Options:

```bash
python3 game.py --seed 12345   # deterministic randomness
python3 game.py --no-color     # accessibility mode, no ANSI colors
```

## Controls

| Where | Keys |
|-------|------|
| Main menu | `N` new game, `L` load, `E` exit |
| In game | `M` map, `Q` switch character, `H` heist planning, `I` inventory/shop |
| Everywhere | `WASD` move, `ENTER` confirm, `ESC` back |

Progress is saved to `savegame.json` in the current directory.
