import random
import settings

map_width, map_height = 0, 0
walls, floors, hazard_tiles, exit_tiles = [], [], [], []
spawn_x, spawn_y = 100, 100
room_type_grid = []

def _weighted_room_type():
    names = [n for n in settings.ROOM_TYPES if settings.ROOM_TYPES[n]["weight"] > 0]
    weights = [settings.ROOM_TYPES[n]["weight"] for n in names]
    return random.choices(names, weights=weights, k=1)[0]

def generate_backrooms_level(level_id, player=None):
    global walls, floors, hazard_tiles, exit_tiles, spawn_x, spawn_y, map_width, map_height, room_type_grid

    cols = 40 + (level_id * 5)
    rows = 28 + (level_id * 5)
    map_width = cols * settings.TILE_SIZE
    map_height = rows * settings.TILE_SIZE

    walls, floors, hazard_tiles, exit_tiles = [], [], [], []

    if level_id % 3 == 0:
        settings.TILE_COLORS["wall"], settings.TILE_COLORS["floor"] = (190, 175, 100), (225, 210, 140)
    elif level_id % 3 == 1:
        settings.TILE_COLORS["wall"], settings.TILE_COLORS["floor"] = (70, 75, 80), (110, 115, 120)
    else:
        settings.TILE_COLORS["wall"], settings.TILE_COLORS["floor"] = (40, 20, 10), (70, 50, 40)

    grid = [[1 for _ in range(cols)] for _ in range(rows)]  
    room_type_grid = [[None for _ in range(cols)] for _ in range(rows)]

    rooms = []  
    target_room_count = 10 + level_id * 2
    attempts, max_attempts = 0, target_room_count * 200

    while len(rooms) < target_room_count and attempts < max_attempts:
        attempts += 1
        rtype = _weighted_room_type()
        spec = settings.ROOM_TYPES[rtype]
        rw, rh = random.randint(spec["min_size"][0], spec["max_size"][0]), random.randint(spec["min_size"][1], spec["max_size"][1])
        if cols - rw - 2 < 2 or rows - rh - 2 < 2: continue
        rx, ry = random.randint(1, cols - rw - 2), random.randint(1, rows - rh - 2)

        overlaps = False
        for r in rooms:
            ex, ey, ew, eh = r["rect"]
            if not (rx + rw + 1 <= ex or rx >= ex + ew + 1 or ry + rh + 1 <= ey or ry >= ey + eh + 1):
                overlaps = True; break
        if overlaps: continue

        rooms.append({"rect": (rx, ry, rw, rh), "type": rtype, "center": (rx + rw // 2, ry + rh // 2)})
        for yy in range(ry, ry + rh):
            for xx in range(rx, rx + rw):
                grid[yy][xx] = 0
                room_type_grid[yy][xx] = rtype

    if not rooms:
        rooms.append({"rect": (2, 2, 6, 6), "type": "office_bay", "center": (5, 5)})
        grid[2][2] = 0; room_type_grid[2][2] = "office_bay"

    scx, scy = rooms[0]["center"]
    spawn_x, spawn_y = scx * settings.TILE_SIZE, scy * settings.TILE_SIZE

    def carve_corridor(p1, p2):
        (x1, y1), (x2, y2) = p1, p2
        cx, cy = x1, y1
        horiz_first = random.random() < 0.5
        steps = [(x2, "x"), (y2, "y")] if horiz_first else [(y2, "y"), (x2, "x")]
        for target, axis in steps:
            while (cx if axis == "x" else cy) != target:
                grid[cy][cx] = 0
                if room_type_grid[cy][cx] is None: room_type_grid[cy][cx] = "corridor"
                cx += (1 if target > cx else -1) if axis == "x" else 0
                cy += (1 if target > cy else -1) if axis == "y" else 0
        grid[y2][x2] = 0

    connected, remaining = {0}, set(range(1, len(rooms)))
    while remaining:
        best, best_dist = None, None
        for a in connected:
            for b in remaining:
                ax, ay = rooms[a]["center"]; bx, by = rooms[b]["center"]
                d = abs(ax - bx) + abs(ay - by)
                if best_dist is None or d < best_dist: best, best_dist = (a, b), d
        a, b = best
        carve_corridor(rooms[a]["center"], rooms[b]["center"])
        connected.add(b)
        remaining.discard(b)

    for _ in range(max(1, len(rooms) // 4)):
        a, b = random.sample(range(len(rooms)), 2)
        carve_corridor(rooms[a]["center"], rooms[b]["center"])

    exit_room = max(rooms[1:], key=lambda r: abs(r["center"][0] - scx) + abs(r["center"][1] - scy)) if len(rooms) > 1 else rooms[0]
    ecx, ecy = exit_room["center"]
    grid[ecy][ecx] = 3
    room_type_grid[ecy][ecx] = exit_room["type"]

    for y in range(rows):
        for x in range(cols):
            rect = (x * settings.TILE_SIZE, y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
            cell = grid[y][x]
            if cell == 1: walls.append(rect)
            elif cell == 3: exit_tiles.append(rect)
            else:
                rtype = room_type_grid[y][x] or "office_bay"
                density = settings.ROOM_TYPES.get(rtype, {}).get("hazard_density", 0.03)
                if (x, y) != (scx, scy) and random.random() < density: hazard_tiles.append(rect)
                else: floors.append(rect)

    if player:
        player.x, player.y = spawn_x, spawn_y
        player.on_exit = False