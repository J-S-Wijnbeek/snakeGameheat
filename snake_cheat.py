#!/usr/bin/env python3
"""
Snake Game Cheat – Transparent Overlay Bot
===========================================
Automatically steers the snake towards food while avoiding walls and its own
body, using BFS (breadth-first search) pathfinding.  A semi-transparent
always-on-top overlay draws the planned path in real time.

Quick-start
-----------
1.  pip install -r requirements.txt
2.  Open your snake game in a browser or application window.
3.  python snake_cheat.py
4.  Follow the three-step setup wizard that appears.

Controls inside the cheat window
---------------------------------
  Step 1 – Select Game Area  : click-and-drag a rectangle around the game.
  Step 2 – Configure Colors  : click on the snake head, body, food, and
                               background in the screenshot shown.
  Step 3 – Start Cheat       : launches the overlay and begins playing.
  Esc / Ctrl-C               : stop at any time.
"""

import sys
import time
import threading
import platform
import tkinter as tk
from tkinter import messagebox
from collections import deque

try:
    import pyautogui
except ImportError:
    sys.exit("Missing dependency: pip install pyautogui")

try:
    from PIL import ImageGrab, Image
except ImportError:
    sys.exit("Missing dependency: pip install Pillow")

# ── pyautogui safety settings ────────────────────────────────────────────────
pyautogui.PAUSE = 0.01       # minimal delay – enough to avoid overwhelming the OS
pyautogui.FAILSAFE = True    # move mouse to corner to abort

# ── Grid-cell type constants ──────────────────────────────────────────────────
CELL_EMPTY = 0   # passable background
CELL_BODY  = 1   # snake body (blocked)
CELL_WALL  = 2   # wall (blocked)
DIRECTIONS = ["UP", "DOWN", "LEFT", "RIGHT"]

DIR_VECTOR = {
    "UP":    ( 0, -1),
    "DOWN":  ( 0,  1),
    "LEFT":  (-1,  0),
    "RIGHT": ( 1,  0),
}

OPPOSITE = {
    "UP": "DOWN", "DOWN": "UP",
    "LEFT": "RIGHT", "RIGHT": "LEFT",
}

PYAUTOGUI_KEY = {
    "UP": "up", "DOWN": "down",
    "LEFT": "left", "RIGHT": "right",
}

# ── Default configuration ─────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    # pixels per grid cell (auto-detected or set manually)
    "cell_size": 20,
    # seconds the cheat waits between sending key presses
    "move_interval": 0.12,
    # colour-matching tolerance (Euclidean RGB distance)
    "color_tolerance": 40,
    # RGB colours – overridden by the colour-picker wizard
    "snake_head_color": [0, 200, 0],
    "snake_body_color": [0, 140, 0],
    "food_color":       [220, 50, 50],
    "background_color": [0, 0, 0],
    "wall_color":       [80, 80, 80],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Colour utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _color_dist(c1, c2):
    """Euclidean distance between two RGB tuples."""
    return (sum((a - b) ** 2 for a, b in zip(c1, c2))) ** 0.5


def _color_match(pixel, reference, tolerance):
    return _color_dist(pixel[:3], reference[:3]) <= tolerance


# ═══════════════════════════════════════════════════════════════════════════════
# Screen analyser – reads the game state from a screenshot
# ═══════════════════════════════════════════════════════════════════════════════

class GameState:
    """Snapshot of the grid at a single moment in time."""

    def __init__(self):
        self.grid = []       # rows × cols; 0 = empty, 1 = snake body, 2 = wall
        self.head = None     # (col, row)
        self.food = None     # (col, row)
        self.rows = 0
        self.cols = 0


class ScreenAnalyser:
    """Captures a screenshot of the game region and extracts the game state."""

    def __init__(self, region, config):
        """
        Parameters
        ----------
        region : (left, top, width, height)
        config : dict matching DEFAULT_CONFIG layout
        """
        self.region = region
        self.config = config
        l, t, w, h = region
        cs = config["cell_size"]
        self.cols = max(1, w // cs)
        self.rows = max(1, h // cs)

    def capture(self):
        l, t, w, h = self.region
        return ImageGrab.grab(bbox=(l, t, l + w, t + h))

    def analyse(self, img):
        cfg = self.config
        tol = cfg["color_tolerance"]
        head_c  = tuple(cfg["snake_head_color"])
        body_c  = tuple(cfg["snake_body_color"])
        food_c  = tuple(cfg["food_color"])
        wall_c  = tuple(cfg["wall_color"])
        cs = cfg["cell_size"]

        state = GameState()
        state.rows = self.rows
        state.cols = self.cols
        state.grid = [[CELL_EMPTY] * self.cols for _ in range(self.rows)]

        for row in range(self.rows):
            for col in range(self.cols):
                px = col * cs + cs // 2
                py = row * cs + cs // 2
                if px >= img.width or py >= img.height:
                    continue
                pixel = img.getpixel((px, py))

                if _color_match(pixel, head_c, tol):
                    state.head = (col, row)
                    # head cell stays CELL_EMPTY so pathfinder can step off it
                elif _color_match(pixel, body_c, tol):
                    state.grid[row][col] = CELL_BODY
                elif _color_match(pixel, food_c, tol):
                    state.food = (col, row)
                elif _color_match(pixel, wall_c, tol):
                    state.grid[row][col] = CELL_WALL

        return state


# ═══════════════════════════════════════════════════════════════════════════════
# Pathfinder – BFS from head to food
# ═══════════════════════════════════════════════════════════════════════════════

class PathFinder:
    """Finds the shortest safe path from snake head to food using BFS."""

    def find_path(self, state):
        """
        Returns a list of direction strings (e.g. ["RIGHT", "DOWN", "RIGHT"])
        or None when no safe route exists.
        """
        if state.head is None or state.food is None:
            return None

        start = state.head
        goal  = state.food
        grid  = state.grid
        rows  = state.rows
        cols  = state.cols

        # BFS
        visited = {start}
        queue   = deque([(start, [])])

        while queue:
            (col, row), path = queue.popleft()

            for direction in DIRECTIONS:
                dc, dr = DIR_VECTOR[direction]
                nc, nr = col + dc, row + dr

                if not (0 <= nc < cols and 0 <= nr < rows):
                    continue
                if (nc, nr) in visited:
                    continue
                if grid[nr][nc] != CELL_EMPTY:    # body or wall
                    continue

                new_path = path + [direction]

                if (nc, nr) == goal:
                    return new_path

                visited.add((nc, nr))
                queue.append(((nc, nr), new_path))

        return None     # no path

    def flood_fill_size(self, grid, start_col, start_row, rows, cols):
        """Count cells reachable from (start_col, start_row)."""
        visited = {(start_col, start_row)}
        queue   = deque([(start_col, start_row)])
        while queue:
            c, r = queue.popleft()
            for dc, dr in DIR_VECTOR.values():
                nc, nr = c + dc, r + dr
                if (nc, nr) in visited:
                    continue
                if not (0 <= nc < cols and 0 <= nr < rows):
                    continue
                if grid[nr][nc] != CELL_EMPTY:
                    continue
                visited.add((nc, nr))
                queue.append((nc, nr))
        return len(visited)

    def survival_move(self, state, current_direction):
        """
        When BFS finds no path to food, pick the direction that maximises
        the open space ahead (flood-fill heuristic).
        """
        if state.head is None:
            return None

        col, row = state.head
        grid  = state.grid
        rows  = state.rows
        cols  = state.cols

        best_dir   = None
        best_space = -1

        for direction in DIRECTIONS:
            if direction == OPPOSITE.get(current_direction):
                continue
            dc, dr = DIR_VECTOR[direction]
            nc, nr = col + dc, row + dr
            if not (0 <= nc < cols and 0 <= nr < rows):
                continue
            if grid[nr][nc] != CELL_EMPTY:
                continue
            space = self.flood_fill_size(grid, nc, nr, rows, cols)
            if space > best_space:
                best_space = space
                best_dir   = direction

        return best_dir


# ═══════════════════════════════════════════════════════════════════════════════
# Overlay window – semi-transparent tkinter window drawn on top of the game
# ═══════════════════════════════════════════════════════════════════════════════

_TRANSPARENT_COLOR = "black"     # colour treated as fully transparent


class OverlayWindow:
    """
    A borderless, always-on-top, semi-transparent tkinter window that
    visualises the planned path, snake head, and food positions.

    Must be started in its own thread because tkinter mainloop is blocking.
    """

    def __init__(self, region, cell_size):
        self.region    = region
        self.cell_size = cell_size

        # shared state (written by cheat thread, read by UI thread)
        self._lock       = threading.Lock()
        self._head       = None
        self._food       = None
        self._path       = []
        self._status     = "Initialising…"

        self._root   = None
        self._canvas = None
        self._status_var = None
        self._ready  = threading.Event()

    # ── public API (called from cheat thread) ─────────────────────────────────

    def start(self):
        """Launch the overlay in a daemon thread."""
        t = threading.Thread(target=self._run, name="overlay", daemon=True)
        t.start()
        self._ready.wait(timeout=3)     # wait until tkinter is up

    def update(self, head, food, path, status=""):
        with self._lock:
            self._head   = head
            self._food   = food
            self._path   = list(path) if path else []
            self._status = status

    def stop(self):
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    # ── private ───────────────────────────────────────────────────────────────

    def _run(self):
        l, t, w, h = self.region
        self._root = tk.Tk()
        self._root.geometry(f"{w}x{h}+{l}+{t}")
        self._root.overrideredirect(True)         # no title bar / border
        self._root.attributes("-topmost", True)   # always on top

        # Platform-specific transparency
        os_name = platform.system()
        if os_name == "Windows":
            self._root.attributes("-alpha", 0.5)
            self._root.attributes("-transparentcolor", _TRANSPARENT_COLOR)
        elif os_name == "Darwin":   # macOS
            self._root.attributes("-alpha", 0.5)
            self._root.attributes("-transparent", True)
            self._root.config(bg="systemTransparent")
        else:                       # Linux / X11
            self._root.attributes("-alpha", 0.45)
            self._root.config(bg=_TRANSPARENT_COLOR)

        self._canvas = tk.Canvas(
            self._root, width=w, height=h,
            bg=_TRANSPARENT_COLOR, highlightthickness=0,
        )
        self._canvas.pack()

        self._status_var = tk.StringVar(value=self._status)
        status_lbl = tk.Label(
            self._root,
            textvariable=self._status_var,
            bg="#111111", fg="#00ff88",
            font=("Consolas", 9, "bold"),
            padx=4, pady=2,
        )
        status_lbl.place(x=4, y=4)

        self._ready.set()
        self._root.after(80, self._draw_loop)
        self._root.mainloop()

    def _draw_loop(self):
        self._redraw()
        if self._root:
            try:
                self._root.after(80, self._draw_loop)
            except Exception:
                pass

    def _redraw(self):
        if self._canvas is None:
            return

        with self._lock:
            head   = self._head
            food   = self._food
            path   = list(self._path)
            status = self._status

        try:
            self._status_var.set(f"🐍 {status}")
        except Exception:
            pass

        self._canvas.delete("all")
        cs = self.cell_size

        # ── Draw planned path cells ──────────────────────────────────────────
        if head and path:
            col, row = head
            for direction in path:
                dc, dr = DIR_VECTOR[direction]
                col += dc
                row += dr
                x1, y1 = col * cs + 3, row * cs + 3
                x2, y2 = col * cs + cs - 3, row * cs + cs - 3
                self._canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill="#00cc66", outline="#00ff88", width=1,
                )

        # ── Draw snake head marker ───────────────────────────────────────────
        if head:
            col, row = head
            x1, y1 = col * cs + 1, row * cs + 1
            x2, y2 = col * cs + cs - 1, row * cs + cs - 1
            self._canvas.create_rectangle(
                x1, y1, x2, y2, fill="#00ff44", outline="#ffffff", width=2,
            )

        # ── Draw food marker ─────────────────────────────────────────────────
        if food:
            col, row = food
            cx = col * cs + cs // 2
            cy = row * cs + cs // 2
            r  = max(3, cs // 2 - 2)
            self._canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill="#ff3333", outline="#ffaaaa", width=2,
            )

        # ── Draw path arrows ─────────────────────────────────────────────────
        if head and len(path) > 1:
            col, row = head
            for i, direction in enumerate(path[:-1]):
                dc, dr = DIR_VECTOR[direction]
                col += dc
                row += dr
                cx = col * cs + cs // 2
                cy = row * cs + cs // 2
                # small dot along the path
                self._canvas.create_oval(
                    cx - 2, cy - 2, cx + 2, cy + 2,
                    fill="#ffffff", outline="",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Region selector – full-screen click-and-drag
# ═══════════════════════════════════════════════════════════════════════════════

def select_region():
    """
    Show a semi-transparent full-screen overlay where the user can
    click-and-drag to select the game region.

    Returns (left, top, width, height) or None if cancelled.
    """
    result = [None]

    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.35)
    root.attributes("-topmost", True)
    root.overrideredirect(True)
    root.config(bg="gray15")

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    canvas = tk.Canvas(root, bg="gray15", highlightthickness=0,
                       width=sw, height=sh)
    canvas.pack(fill="both", expand=True)

    canvas.create_text(
        sw // 2, 50,
        text="Click and drag to select the SNAKE GAME area – then release",
        fill="white", font=("Arial", 18, "bold"),
    )
    canvas.create_text(
        sw // 2, 85,
        text="Press Esc to cancel",
        fill="#aaaaaa", font=("Arial", 12),
    )

    _sx = _sy = 0
    _rect = [None]

    def on_press(e):
        nonlocal _sx, _sy
        _sx, _sy = e.x, e.y
        _rect[0] = canvas.create_rectangle(
            _sx, _sy, _sx, _sy,
            outline="#00ff44", width=3, fill="#00ff44", stipple="gray25",
        )

    def on_drag(e):
        if _rect[0]:
            canvas.coords(_rect[0], _sx, _sy, e.x, e.y)

    def on_release(e):
        x1 = min(_sx, e.x)
        y1 = min(_sy, e.y)
        x2 = max(_sx, e.x)
        y2 = max(_sy, e.y)
        if x2 - x1 > 20 and y2 - y1 > 20:
            result[0] = (x1, y1, x2 - x1, y2 - y1)
        root.quit()

    canvas.bind("<ButtonPress-1>",   on_press)
    canvas.bind("<B1-Motion>",       on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>",            lambda e: root.quit())

    root.mainloop()
    root.destroy()
    return result[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Colour picker wizard
# ═══════════════════════════════════════════════════════════════════════════════

def pick_colors(region, config):
    """
    Show a screenshot of the selected region and ask the user to click on
    the snake head, body, food, and background colours in turn.

    Returns an updated copy of *config*.
    """
    try:
        from PIL import ImageTk
    except ImportError:
        messagebox.showwarning(
            "Pillow ImageTk missing",
            "Cannot show colour picker.\n"
            "Install Pillow with Tk support: pip install Pillow\n"
            "Using default colours instead.",
        )
        return config

    l, t, w, h = region
    screenshot = ImageGrab.grab(bbox=(l, t, l + w, t + h))

    new_config = config.copy()

    TARGETS = [
        ("snake_head_color", "Click on the SNAKE HEAD"),
        ("snake_body_color", "Click on the SNAKE BODY"),
        ("food_color",       "Click on the FOOD"),
        ("background_color", "Click on the BACKGROUND"),
    ]
    idx = [0]

    root = tk.Tk()
    root.title("Colour Configuration – Snake Cheat")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    tk_img = ImageTk.PhotoImage(screenshot)

    canvas = tk.Canvas(root, width=w, height=h, highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, anchor="nw", image=tk_img)

    info_var = tk.StringVar()
    info_lbl = tk.Label(
        root, textvariable=info_var,
        bg="#1a1a2e", fg="#ffcc00", font=("Arial", 11, "bold"),
        padx=8, pady=6,
    )
    info_lbl.pack(fill="x")

    def _update_label():
        if idx[0] < len(TARGETS):
            _, msg = TARGETS[idx[0]]
            info_var.set(f"{msg}  (step {idx[0]+1}/{len(TARGETS)})")
        else:
            info_var.set("All colours set! Window closes automatically…")

    _update_label()

    def on_click(e):
        if idx[0] >= len(TARGETS):
            root.quit()
            return
        key, _ = TARGETS[idx[0]]
        pixel = screenshot.getpixel((e.x, e.y))[:3]
        new_config[key] = list(pixel)
        # mark the clicked pixel
        canvas.create_oval(
            e.x - 9, e.y - 9, e.x + 9, e.y + 9,
            outline="#ffffff", width=2,
        )
        idx[0] += 1
        _update_label()
        if idx[0] >= len(TARGETS):
            root.after(900, root.quit)

    canvas.bind("<Button-1>", on_click)
    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass
    return new_config


# ═══════════════════════════════════════════════════════════════════════════════
# Main cheat engine
# ═══════════════════════════════════════════════════════════════════════════════

class SnakeCheat:
    """
    Ties together screen analysis, pathfinding, overlay rendering, and
    keyboard control.  The cheat loop runs in a background thread so that
    the tkinter overlay can use the main thread.
    """

    def __init__(self, region, config):
        self.region    = region
        self.config    = config
        self.running   = False

        cs = config["cell_size"]
        self._analyser    = ScreenAnalyser(region, config)
        self._pathfinder  = PathFinder()
        self._overlay     = OverlayWindow(region, cs)
        self._current_dir = "RIGHT"
        self._thread      = None

    def start(self):
        self.running = True
        self._overlay.start()
        time.sleep(0.4)   # let the overlay window appear
        self._thread = threading.Thread(
            target=self._loop, name="cheat-loop", daemon=True,
        )
        self._thread.start()

    def stop(self):
        self.running = False
        self._overlay.stop()

    # ── cheat loop ────────────────────────────────────────────────────────────

    def _loop(self):
        # Click the game area once to make sure it has keyboard focus
        l, t, w, h = self.region
        pyautogui.click(l + w // 2, t + h // 2)
        time.sleep(0.25)

        interval = self.config["move_interval"]

        while self.running:
            try:
                img   = self._analyser.capture()
                state = self._analyser.analyse(img)

                if state.head is None:
                    self._overlay.update(None, None, [], "Searching for snake…")
                    time.sleep(0.1)
                    continue

                if state.food is None:
                    self._overlay.update(state.head, None, [], "No food detected…")
                    time.sleep(0.1)
                    continue

                path = self._pathfinder.find_path(state)

                if path:
                    status    = f"Path: {len(path)} steps"
                    next_dir  = path[0]
                else:
                    next_dir  = self._pathfinder.survival_move(
                        state, self._current_dir,
                    )
                    path      = [next_dir] if next_dir else []
                    status    = "No direct path – surviving…" if next_dir else "Trapped!"

                self._overlay.update(state.head, state.food, path, status)

                if next_dir and next_dir != OPPOSITE.get(self._current_dir):
                    pyautogui.press(PYAUTOGUI_KEY[next_dir])
                    self._current_dir = next_dir

                time.sleep(interval)

            except Exception as exc:
                print(f"[cheat loop] {exc}")
                time.sleep(0.1)


# ═══════════════════════════════════════════════════════════════════════════════
# Setup GUI
# ═══════════════════════════════════════════════════════════════════════════════

class SetupGUI:
    """Three-step wizard that configures and launches the cheat."""

    def __init__(self):
        self.region = None
        self.config = DEFAULT_CONFIG.copy()

    def run(self):
        root = tk.Tk()
        root.title("Snake Cheat – Setup")
        root.geometry("520x520")
        root.resizable(False, False)
        root.configure(bg="#1a1a2e")

        # ── Header ─────────────────────────────────────────────────────────────
        tk.Label(
            root, text="🐍  SNAKE CHEAT OVERLAY",
            bg="#1a1a2e", fg="#00ff88", font=("Consolas", 20, "bold"),
        ).pack(pady=(22, 6))

        tk.Label(
            root,
            text=(
                "Automatically controls the snake using BFS pathfinding.\n"
                "Avoids walls and self-collision.  Shows planned path as overlay."
            ),
            bg="#1a1a2e", fg="#888888", font=("Arial", 10),
            justify="center",
        ).pack(pady=(0, 10))

        tk.Frame(root, bg="#333333", height=1).pack(fill="x", padx=24, pady=6)

        # ── Tuning sliders ────────────────────────────────────────────────────
        def _row(label, var, lo, hi, inc=1):
            f = tk.Frame(root, bg="#1a1a2e")
            f.pack(pady=3)
            tk.Label(f, text=f"{label}:", bg="#1a1a2e", fg="#cccccc",
                     width=24, anchor="e").pack(side="left")
            tk.Spinbox(f, from_=lo, to=hi, increment=inc,
                       textvariable=var, width=8,
                       bg="#0d3b66", fg="white", buttonbackground="#0d3b66",
                       ).pack(side="left", padx=8)

        cell_var  = tk.IntVar(value=20)
        interval_var = tk.DoubleVar(value=0.12)
        tol_var   = tk.IntVar(value=40)

        _row("Grid cell size (px)",       cell_var,  5,   80)
        _row("Move interval (sec)",        interval_var, 0.05, 2.0, 0.01)
        _row("Colour tolerance (0–255)",   tol_var,   5,  200)

        tk.Frame(root, bg="#333333", height=1).pack(fill="x", padx=24, pady=10)

        # ── Status ────────────────────────────────────────────────────────────
        status_var = tk.StringVar(value="Step 1: click 'Select Game Area'")
        tk.Label(
            root, textvariable=status_var,
            bg="#0d3b66", fg="#ffcc00",
            font=("Arial", 10, "bold"), padx=10, pady=6,
        ).pack(fill="x", padx=24)

        region_var = tk.StringVar(value="No region selected yet")
        tk.Label(root, textvariable=region_var,
                 bg="#1a1a2e", fg="#666666",
                 font=("Arial", 9)).pack(pady=2)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn = dict(bg="#0d3b66", fg="white", font=("Arial", 11, "bold"),
                   relief="flat", padx=16, pady=8, cursor="hand2",
                   activebackground="#1a5276", activeforeground="white")

        def do_select():
            root.withdraw()
            time.sleep(0.25)
            self.region = select_region()
            root.deiconify()
            if self.region:
                l, t, w, h = self.region
                region_var.set(f"Region: {w}×{h} at ({l}, {t})")
                status_var.set("Step 2: click 'Configure Colours'")
            else:
                status_var.set("Cancelled – try again")

        def do_colors():
            if not self.region:
                messagebox.showwarning("No region", "Please select a region first.")
                return
            root.withdraw()
            self.config = pick_colors(self.region, self.config)
            root.deiconify()
            status_var.set("Step 3: click 'Start Cheat ▶'")

        def do_start():
            if not self.region:
                messagebox.showwarning("No region", "Please select a region first.")
                return
            self.config["cell_size"]      = cell_var.get()
            self.config["move_interval"]  = interval_var.get()
            self.config["color_tolerance"] = tol_var.get()
            root.destroy()

        tk.Button(root, text="1.  Select Game Area",    command=do_select,
                  **btn).pack(pady=4, padx=40, fill="x")
        tk.Button(root, text="2.  Configure Colours",   command=do_colors,
                  **btn).pack(pady=4, padx=40, fill="x")
        tk.Button(root, text="3.  Start Cheat  ▶",      command=do_start,
                  **{**btn, "bg": "#145a32"}).pack(pady=4, padx=40, fill="x")
        tk.Button(root, text="Quit",                    command=sys.exit,
                  **{**btn, "bg": "#6e1a1a"}).pack(pady=4, padx=40, fill="x")

        root.mainloop()
        return self.region is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 50)
    print("  Snake Game Cheat – Transparent Overlay Bot")
    print("=" * 50)
    print("Use the setup wizard to configure and start.")
    print("Move your mouse to any corner of the screen to abort (failsafe).")
    print()

    setup = SetupGUI()
    if not setup.run():
        print("Setup cancelled – exiting.")
        sys.exit(0)

    region = setup.region
    config = setup.config

    print(f"Region      : {region}")
    print(f"Cell size   : {config['cell_size']} px")
    print(f"Move interval: {config['move_interval']} s")
    print("Press Ctrl-C to stop.\n")

    cheat = SnakeCheat(region, config)
    cheat.start()

    try:
        while cheat.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping…")
        cheat.stop()
        print("Stopped.")


if __name__ == "__main__":
    main()
