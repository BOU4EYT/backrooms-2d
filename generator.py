import random
import settings

BASE_COLS = 40
BASE_ROWS = 28
LEVEL_SIZE_GROWTH = 5
BASE_ROOM_COUNT = 10
ROOM_COUNT_GROWTH = 2
ROOM_ATTEMPT_MULTIPLIER = 200
MIN_ROOM_MARGIN = 2
ROOM_PADDING = 1
EXTRA_CONNECTION_ROOM_DIVISOR = 4
DEFAULT_SPAWN_TILE = (2, 2)
DEFAULT_ROOM_SIZE = (6, 6)
DEFAULT_ROOM_TYPE = "office_bay"
DEFAULT_HAZARD_DENSITY = 0.03

LEVEL_PALETTES = [
    {"wall": (190, 175, 100), "floor": (225, 210, 140)},
    {"wall": (70, 75, 80), "floor": (110, 115, 120)},
    {"wall": (40, 20, 10), "floor": (70, 50, 40)},
]
WALL_CELL = 1
FLOOR_CELL = 0
EXIT_CELL = 3

map_width, map_height = 0, 0
walls, floors, hazard_tiles, exit_tiles = [], [], [], []
wall_segments = []
room_lights = []
spawn_x, spawn_y = 100, 100
room_type_grid = []

ROOM_LIGHT_MIN_RADIUS = 90
ROOM_LIGHT_RADIUS_PADDING = 20
ROOM_LIGHT_SIZE_FACTOR = 0.75
LIGHT_FLICKER_ON_RANGE = (0.08, 0.35)   
LIGHT_FLICKER_OFF_RANGE = (0.05, 0.7)   


def update_room_lights(dt):
    """Tick each flickering light's independent on/off timer."""
    for light in room_lights:
        if light["state"] != "flicker":
            continue
        light["flicker_timer"] -= dt
        if light["flicker_timer"] <= 0:
            light["lit"] = not light["lit"]
            lo, hi = LIGHT_FLICKER_ON_RANGE if light["lit"] else LIGHT_FLICKER_OFF_RANGE
            light["flicker_timer"] = random.uniform(lo, hi)


def _extract_wall_segments(grid, cols, rows):
    """Return merged wall-edge segments facing walkable cells to minimize shadow passes."""
    tile_size = settings.TILE_SIZE
    segments = []

    def is_wall(x, y):
        if x < 0 or x >= cols or y < 0 or y >= rows:
            return True
        return grid[y][x] == WALL_CELL

    # Horizontal runs (North faces)
    for y in range(rows):
        run_start = None
        for x in range(cols + 1):
            faces_open = x < cols and is_wall(x, y) and not is_wall(x, y - 1)
            if faces_open and run_start is None:
                run_start = x
            elif not faces_open and run_start is not None:
                segments.append((run_start * tile_size, y * tile_size, x * tile_size, y * tile_size))
                run_start = None

        # South faces
        run_start = None
        for x in range(cols + 1):
            faces_open = x < cols and is_wall(x, y) and not is_wall(x, y + 1)
            if faces_open and run_start is None:
                run_start = x
            elif not faces_open and run_start is not None:
                segments.append((run_start * tile_size, (y + 1) * tile_size, x * tile_size, (y + 1) * tile_size))
                run_start = None

    # Vertical runs (West faces)
    for x in range(cols):
        run_start = None
        for y in range(rows + 1):
            faces_open = y < rows and is_wall(x, y) and not is_wall(x - 1, y)
            if faces_open and run_start is None:
                run_start = y
            elif not faces_open and run_start is not None:
                segments.append((x * tile_size, run_start * tile_size, x * tile_size, y * tile_size))
                run_start = None

        # East faces
        run_start = None
        for y in range(rows + 1):
            faces_open = y < rows and is_wall(x, y) and not is_wall(x + 1, y)
            if faces_open and run_start is None:
                run_start = y
            elif not faces_open and run_start is not None:
                segments.append(((x + 1) * tile_size, run_start * tile_size, (x + 1) * tile_size, y * tile_size))
                run_start = None

    return segments


def _weighted_room_type():
    names = [n for n in settings.ROOM_TYPES if settings.ROOM_TYPES[n]["weight"] > 0]
    weights = [settings.ROOM_TYPES[n]["weight"] for n in names]
    return random.choices(names, weights=weights, k=1)[0]


def generate_backrooms_level(level_id, player=None):
    global walls, floors, hazard_tiles, exit_tiles, wall_segments, spawn_x, spawn_y, map_width, map_height, room_type_grid, room_lights

    cols = BASE_COLS + (level_id * LEVEL_SIZE_GROWTH)
    rows = BASE_ROWS + (level_id * LEVEL_SIZE_GROWTH)
    map_width = cols * settings.TILE_SIZE
    map_height = rows * settings.TILE_SIZE

    walls, floors, hazard_tiles, exit_tiles = [], [], [], []
    wall_segments, room_lights = [], []

    palette = LEVEL_PALETTES[level_id % len(LEVEL_PALETTES)]
    settings.TILE_COLORS["wall"] = palette["wall"]
    settings.TILE_COLORS["floor"] = palette["floor"]

    grid = [[WALL_CELL for _ in range(cols)] for _ in range(rows)]
    room_type_grid = [[None for _ in range(cols)] for _ in range(rows)]

    rooms = []
    target_room_count = BASE_ROOM_COUNT + level_id * ROOM_COUNT_GROWTH
    attempts, max_attempts = 0, target_room_count * ROOM_ATTEMPT_MULTIPLIER

    while len(rooms) < target_room_count and attempts < max_attempts:
        attempts += 1
        rtype = _weighted_room_type()
        spec = settings.ROOM_TYPES[rtype]
        rw = random.randint(spec["min_size"][0], spec["max_size"][0])
        rh = random.randint(spec["min_size"][1], spec["max_size"][1])
        
        if cols - rw - MIN_ROOM_MARGIN < MIN_ROOM_MARGIN or rows - rh - MIN_ROOM_MARGIN < MIN_ROOM_MARGIN: 
            continue
        rx = random.randint(ROOM_PADDING, cols - rw - MIN_ROOM_MARGIN)
        ry = random.randint(ROOM_PADDING, rows - rh - MIN_ROOM_MARGIN)

        overlaps = False
        for r in rooms:
            ex, ey, ew, eh = r["rect"]
            if not (rx + rw + ROOM_PADDING <= ex or rx >= ex + ew + ROOM_PADDING or ry + rh + ROOM_PADDING <= ey or ry >= ey + eh + ROOM_PADDING):
                overlaps = True
                break
        if overlaps: 
            continue

        rooms.append({"rect": (rx, ry, rw, rh), "type": rtype, "center": (rx + rw // 2, ry + rh // 2)})
        for yy in range(ry, ry + rh):
            for xx in range(rx, rx + rw):
                grid[yy][xx] = FLOOR_CELL
                room_type_grid[yy][xx] = rtype

    if not rooms:
        x, y = DEFAULT_SPAWN_TILE
        width, height = DEFAULT_ROOM_SIZE
        rooms.append({"rect": (x, y, width, height), "type": DEFAULT_ROOM_TYPE, "center": (x + width // 2, y + height // 2)})
        grid[y][x] = FLOOR_CELL
        room_type_grid[y][x] = DEFAULT_ROOM_TYPE

    scx, scy = rooms[0]["center"]
    spawn_x, spawn_y = scx * settings.TILE_SIZE, scy * settings.TILE_SIZE

    for r in rooms:
        rx, ry, rw, rh = r["rect"]
        weights = settings.ROOM_TYPES.get(r["type"], {}).get("light_weights", (70, 25, 5))
        state = random.choices(["normal", "flicker", "dark"], weights=weights, k=1)[0]
        radius = max(ROOM_LIGHT_MIN_RADIUS, int(max(rw, rh) * settings.TILE_SIZE * ROOM_LIGHT_SIZE_FACTOR) + ROOM_LIGHT_RADIUS_PADDING)
        lit = state != "dark"
        room_lights.append({
            "x": (rx + rw / 2) * settings.TILE_SIZE,
            "y": (ry + rh / 2) * settings.TILE_SIZE,
            "radius": radius,
            "state": state,
            "lit": lit,
            "flicker_timer": random.uniform(*LIGHT_FLICKER_ON_RANGE) if state == "flicker" else 0.0,
        })

    def carve_corridor(p1, p2):
        (x1, y1), (x2, y2) = p1, p2
        cx, cy = x1, y1
        horiz_first = random.random() < 0.5
        steps = [(x2, "x"), (y2, "y")] if horiz_first else [(y2, "y"), (x2, "x")]
        for target, axis in steps:
            while (cx if axis == "x" else cy) != target:
                grid[cy][cx] = FLOOR_CELL
                if room_type_grid[cy][cx] is None: 
                    room_type_grid[cy][cx] = "corridor"
                cx += (1 if target > cx else -1) if axis == "x" else 0
                cy += (1 if target > cy else -1) if axis == "y" else 0
        grid[y2][x2] = FLOOR_CELL

    connected, remaining = {0}, set(range(1, len(rooms)))
    while remaining:
        best, best_dist = None, None
        for a in connected:
            for b in remaining:
                ax, ay = rooms[a]["center"]
                bx, by = rooms[b]["center"]
                d = abs(ax - bx) + abs(ay - by)
                if best_dist is None or d < best_dist: 
                    best, best_dist = (a, b), d
        a, b = best
        carve_corridor(rooms[a]["center"], rooms[b]["center"])
        connected.add(b)
        remaining.discard(b)

    # BUGFIX: Prevent crash if layout generator only managed to yield 1 room total
    if len(rooms) > 1:
        for _ in range(max(1, len(rooms) // EXTRA_CONNECTION_ROOM_DIVISOR)):
            a, b = random.sample(range(len(rooms)), 2)
            carve_corridor(rooms[a]["center"], rooms[b]["center"])

    if len(rooms) > 1:
        exit_room = max(rooms[1:], key=lambda r: abs(r["center"][0] - scx) + abs(r["center"][1] - scy))
        ecx, ecy = exit_room["center"]
        grid[ecy][ecx] = EXIT_CELL
        room_type_grid[ecy][ecx] = exit_room["type"]
    # BUGFIX: previously fell back to rooms[0] (the spawn room) when only one
    # room existed, which stamps the exit tile directly onto the spawn cell -
    # an instant "level complete" the moment the level loads, with nothing to
    # explore. Since we already guard the single-room case elsewhere (see the
    # corridor bugfix above), just skip placing an exit tile in that scenario
    # instead of overwriting the spawn.

    for y in range(rows):
        for x in range(cols):
            rect = (x * settings.TILE_SIZE, y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
            cell = grid[y][x]
            if cell == WALL_CELL: 
                walls.append(rect)
            elif cell == EXIT_CELL: 
                exit_tiles.append(rect)
            else:
                rtype = room_type_grid[y][x] or DEFAULT_ROOM_TYPE
                density = settings.ROOM_TYPES.get(rtype, {}).get("hazard_density", DEFAULT_HAZARD_DENSITY)
                if (x, y) != (scx, scy) and random.random() < density: 
                    hazard_tiles.append(rect)
                else: 
                    floors.append(rect)

    wall_segments = _extract_wall_segments(grid, cols, rows)

    if player:
        player.x, player.y = spawn_x, spawn_y
        player.on_exit = False