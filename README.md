# snakeGameheat – Snake Game Cheat Overlay

A transparent, always-on-top overlay that **automatically controls any
grid-based snake game** using BFS (breadth-first search) pathfinding.

It steers the snake towards the food while avoiding walls and self-collision.
The planned path is drawn live on the overlay so you can see what the bot is
thinking.

---

## Features

| Feature | Details |
|---|---|
| **Transparent overlay** | Borderless, always-on-top semi-transparent window drawn directly over the game |
| **BFS pathfinding** | Finds the shortest safe path from the snake's head to the food every frame |
| **Flood-fill survival** | When no path to food exists, picks the direction that maximises open space |
| **Visual feedback** | Planned path cells, head marker, and food marker rendered on the overlay |
| **Setup wizard** | Three-step GUI: select game region → pick colours → start |
| **Configurable** | Grid cell size, move speed, and colour-matching tolerance are all adjustable |
| **Works on any snake game** | Browser games, desktop apps – anything visible on screen |

---

## Requirements

- Python 3.8 or newer
- `tkinter` (ships with Python; on Linux you may need `sudo apt install python3-tk`)
- **Linux only:** `scrot` – required by Pillow's `ImageGrab` for taking screenshots:
  ```bash
  sudo apt install scrot
  ```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

1. Open your snake game (e.g. in a browser tab).
2. Run the cheat:

   ```bash
   python snake_cheat.py
   ```

3. Follow the three-step wizard:

   | Step | Action |
   |---|---|
   | **1. Select Game Area** | Click and drag a rectangle around the game canvas |
   | **2. Configure Colours** | Click on the snake head, body, food, and background in the screenshot |
   | **3. Start Cheat ▶** | Launches the overlay and begins playing automatically |

4. The overlay appears over the game showing the planned path in green.  
   Move your mouse to **any corner of the screen** (pyautogui failsafe) or
   press **Ctrl-C** in the terminal to stop.

---

## Configuration (in the wizard)

| Setting | Default | Description |
|---|---|---|
| Grid cell size (px) | 20 | Width/height of a single grid cell in pixels |
| Move interval (sec) | 0.12 | Seconds between key presses – lower = faster snake |
| Colour tolerance | 40 | How closely a pixel must match the configured colour (0–255) |

---

## How it works

```
┌──────────────────────────────────────────────────────────────┐
│  Every tick (move_interval seconds):                         │
│                                                              │
│  1. Capture a screenshot of the selected game region.        │
│  2. Scan each grid cell's centre pixel and classify it as:   │
│       • snake head  → start node                             │
│       • snake body  → blocked                                │
│       • food        → goal node                              │
│       • wall        → blocked                                │
│       • background  → passable                               │
│  3. BFS from head to food on the passable grid.              │
│  4. If a path exists → press the first arrow key in the path │
│     If no path exists → flood-fill each neighbour and pick   │
│       the direction with the most open space (survival mode) │
│  5. Update the overlay canvas with the new path.             │
└──────────────────────────────────────────────────────────────┘
```

---

## Tips

- **Cell size**: count how many pixels wide a single grid square is in the
  game and enter that value in the wizard.  The default 20 px works for many
  common browser snake games.
- **Colours**: use the colour-picker wizard for best accuracy.  If the bot
  misses cells, increase the colour tolerance.
- **Speed**: set the move interval slightly longer than the game's own tick
  rate so keys arrive reliably.
- **Focus**: the cheat clicks the game area once on start to ensure keyboard
  focus – do not click elsewhere while the bot is running.