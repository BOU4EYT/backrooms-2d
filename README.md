# Backrooms 2D

A small top-down survival game prototype built with Python, pygame, and glpg. Explore procedurally generated Backrooms-style levels, avoid hazardous rooms, manage stamina and sanity, and find the exit to descend deeper.

## Features

- Procedural room-and-corridor level generation with themed room types.
- Increasing level size and room count as progression advances.
- Flashlight-based visibility with fog of war and wall-cast shadows.
- Health, stamina, and sanity meters.
- Sprinting, flashlight toggling, animated player sprites, ambient audio, and exit transitions.
- Texture/audio fallbacks so the game can still render with simple shapes when optional assets are missing.

## Requirements

- Python 3.10+
- `pygame`
- `glpg`

Install dependencies:

```bash
pip install pygame glpg
```

## Run

```bash
python main.py
```

## Controls

| Key | Action |
| --- | --- |
| `W` / `A` / `S` / `D` | Move |
| `Shift` | Sprint while moving |
| `F` | Toggle flashlight |
| `1`-`5` | Select hotbar slot |
| `Esc` | Quit |

## Project Structure

```text
assets/
  audio/       Optional sound effects and ambient loop
  textures/    Optional wall, floor, finish, and player textures
generator.py   Procedural level generation and tile lists
main.py        Game loop, drawing, camera, lighting, and transitions
player.py      Player movement, collisions, stats, animation, and HUD
settings.py    Window setup, constants, room definitions, and asset loading
```

## Gameplay Notes

- Red hazard tiles damage health and sanity.
- Turning the flashlight off drains sanity faster.
- Low sanity can cause flickering light and visual shiver.
- Reaching an exit tile fades to the next, larger generated level.

## Development

Run a syntax check before committing changes:

```bash
python -m py_compile main.py settings.py player.py generator.py
```

The game expects assets under `assets/textures` and `assets/audio`, but will fall back when many optional files are absent.
