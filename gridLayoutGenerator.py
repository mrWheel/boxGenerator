#!/usr/bin/env python3

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class CompartmentSpec:
  index: int
  grid_w: int
  grid_h: int
  count: int


@dataclass
class Placement:
  label: str
  is_leftover: bool
  x_cell: int
  y_cell: int
  w_cells: int
  h_cells: int
  x_mm: float
  y_mm: float
  w_mm: float
  h_mm: float


@dataclass
class SolidBox:
  x: float
  y: float
  z: float
  w: float
  h: float
  d: float


@dataclass
class LabelGlyph:
  compartment_label: str
  text: str
  boxes: List[SolidBox]


@dataclass
class RunDefaults:
  grid_size: float = 40.0
  outer_length: float = 280.0
  outer_width: float = 200.0
  outer_height: float = 60.0
  outer_wall: float = 1.4
  inner_wall: float = 1.0
  bottom_thickness: float = 1.4
  inner_wall_height: float = 58.6
  compartments: Optional[List[CompartmentSpec]] = None


def select_project() -> str:
  project_files = sorted(Path(".").glob(".gridLayout.*.json"))
  projects = [file.name[len(".gridLayout."):-len(".json")] for file in project_files]

  if not projects:
    while True:
      name = input("Enter project name: ").strip()
      if name:
        return name
      print("Project name cannot be empty.")

  new_option = len(projects) + 1
  print("Select a project:")
  for index, name in enumerate(projects, start=1):
    print(f"  [{index}] {name}")
  print(f"  [{new_option}] newProject")

  while True:
    raw = input(f"Choice [1-{new_option}]: ").strip()
    try:
      choice = int(raw)
    except ValueError:
      print(f"Please enter a number between 1 and {new_option}.")
      continue

    if 1 <= choice <= len(projects):
      return projects[choice - 1]
    if choice == new_option:
      while True:
        name = input("Enter new project name: ").strip()
        if name:
          return name
        print("Project name cannot be empty.")

    print(f"Please enter a number between 1 and {new_option}.")


def load_defaults(path: Path) -> RunDefaults:
  if not path.exists():
    return RunDefaults()

  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, ValueError, TypeError):
    return RunDefaults()

  specs: List[CompartmentSpec] = []
  for entry in data.get("compartments", []):
    try:
      specs.append(
        CompartmentSpec(
          index=int(entry.get("index", len(specs) + 1)),
          grid_w=int(entry["grid_w"]),
          grid_h=int(entry["grid_h"]),
          count=int(entry["count"])
        )
      )
    except (TypeError, ValueError, KeyError):
      continue

  return RunDefaults(
    grid_size=float(data.get("grid_size", 40.0)),
    outer_length=float(data.get("outer_length", 280.0)),
    outer_width=float(data.get("outer_width", 200.0)),
    outer_height=float(data.get("outer_height", 60.0)),
    outer_wall=float(data.get("outer_wall", 1.4)),
    inner_wall=float(data.get("inner_wall", 1.0)),
    bottom_thickness=float(data.get("bottom_thickness", data.get("outer_wall", 1.4))),
    inner_wall_height=float(data.get("inner_wall_height", 58.6)),
    compartments=specs
  )


def save_defaults(path: Path, defaults: RunDefaults) -> None:
  data = {
    "grid_size": defaults.grid_size,
    "outer_length": defaults.outer_length,
    "outer_width": defaults.outer_width,
    "outer_height": defaults.outer_height,
    "outer_wall": defaults.outer_wall,
    "inner_wall": defaults.inner_wall,
    "bottom_thickness": defaults.bottom_thickness,
    "inner_wall_height": defaults.inner_wall_height,
    "compartments": [
      {
        "index": spec.index,
        "grid_w": spec.grid_w,
        "grid_h": spec.grid_h,
        "count": spec.count
      }
      for spec in (defaults.compartments or [])
    ]
  }
  path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ask_float(prompt: str, default_value: float) -> float:
  raw = input(f"{prompt} [{default_value}]: ").strip()
  if not raw:
    return default_value
  try:
    value = float(raw.replace(",", "."))
    if value <= 0:
      raise ValueError
    return value
  except ValueError:
    print(f"Invalid input, using default {default_value}.")
    return default_value


def parse_2d_mm(text: str) -> Tuple[float, float]:
  cleaned = text.lower().replace(" ", "").replace(",", ".")
  if "x" in cleaned:
    parts = cleaned.split("x")
    if len(parts) != 2:
      raise ValueError("Expected format LxW")
    length = float(parts[0])
    width = float(parts[1])
  else:
    length = float(cleaned)
    width = float(cleaned)

  if length <= 0 or width <= 0:
    raise ValueError("Dimensions must be > 0")

  return length, width


def parse_3d_mm(text: str) -> Tuple[float, float, float]:
  cleaned = text.lower().replace(" ", "").replace(",", ".")
  parts = cleaned.split("x")
  if len(parts) != 3:
    raise ValueError("Expected format LxWxH")

  length = float(parts[0])
  width = float(parts[1])
  height = float(parts[2])

  if length <= 0 or width <= 0 or height <= 0:
    raise ValueError("Dimensions must be > 0")

  return length, width, height


def build_outer_size_suggestions(
  grid_size: float,
  min_size: float = 100.0,
  max_size: float = 300.0
) -> List[float]:
  if grid_size <= 0:
    return []

  min_step = int(math.ceil(min_size / grid_size))
  max_step = int(max_size // grid_size)
  if min_step > max_step:
    return []

  suggestions: List[float] = []
  for step in range(min_step, max_step + 1):
    suggestions.append(step * grid_size)

  return suggestions


def ask_outer_size(
  default_length: float,
  default_width: float,
  default_height: float,
  grid_size: float
) -> Tuple[float, float, float]:
  default_text = f"{default_length:g}x{default_width:g}x{default_height:g}"
  suggestions = build_outer_size_suggestions(grid_size)
  if suggestions:
    suggestion_text = ", ".join(f"{value:g}" for value in suggestions)
    print(f"Axis values (gridSize multiples, 100..300): {suggestion_text}")
  raw = input(f"Enter complete outer box size in mm (LxWxH) [{default_text}]: ").strip()
  if not raw:
    return default_length, default_width, default_height

  try:
    return parse_3d_mm(raw)
  except ValueError:
    print("Invalid input, using defaults.")
    return default_length, default_width, default_height


def parse_compartment_grid_size(text: str) -> Tuple[int, int]:
  cleaned = text.lower().replace(" ", "")
  parts = cleaned.split("x")
  if len(parts) != 2:
    raise ValueError("Expected format NxM")

  grid_w = int(parts[0])
  grid_h = int(parts[1])
  if grid_w <= 0 or grid_h <= 0:
    raise ValueError("Grid dimensions must be > 0")

  return grid_w, grid_h


def ask_int(prompt: str, default_value: int) -> int:
  raw = input(f"{prompt} [{default_value}]: ").strip()
  if not raw:
    return default_value

  try:
    value = int(raw)
    if value <= 0:
      raise ValueError
    return value
  except ValueError:
    print(f"Invalid input, using default {default_value}.")
    return default_value


def ask_compartments(default_specs: Optional[List[CompartmentSpec]]) -> List[CompartmentSpec]:
  print("")
  print("Enter compartment requirements.")
  print("Use format NxM (examples: 1x1, 1x2, 2x6, 3x4)")
  print("Empty size reuses the default size and still asks for count.")
  print("If no default exists yet, empty size finishes input.")

  specs: List[CompartmentSpec] = []
  index = 1

  while True:
    default_spec = None
    if default_specs is not None and index - 1 < len(default_specs):
      default_spec = default_specs[index - 1]

    default_size_text = ""
    if default_spec is not None:
      default_size_text = f" [{default_spec.grid_w}x{default_spec.grid_h}]"

    print("")
    raw_size = input(f"Compartment {index} size in grid units{default_size_text}: ").strip()
    if raw_size == "":
      if default_spec is None:
        break
      grid_w = default_spec.grid_w
      grid_h = default_spec.grid_h
    else:
      try:
        grid_w, grid_h = parse_compartment_grid_size(raw_size)
      except ValueError as exc:
        print(f"Error: {exc}")
        continue

    count_default = default_spec.count if default_spec is not None else 1
    count = ask_int(f"How many of {grid_w}x{grid_h}", count_default)
    specs.append(CompartmentSpec(index=index, grid_w=grid_w, grid_h=grid_h, count=count))
    index += 1

  return specs


def can_place(occupied: List[List[bool]], start_x: int, start_y: int, w: int, h: int) -> bool:
  rows = len(occupied)
  cols = len(occupied[0]) if rows else 0

  if start_x + w > cols or start_y + h > rows:
    return False

  for y in range(start_y, start_y + h):
    for x in range(start_x, start_x + w):
      if occupied[y][x]:
        return False

  return True


def fill_cells(occupied: List[List[bool]], start_x: int, start_y: int, w: int, h: int) -> None:
  for y in range(start_y, start_y + h):
    for x in range(start_x, start_x + w):
      occupied[y][x] = True


def grid_to_mm_size(cell_count: int, grid_size: float, inner_wall: float) -> float:
  _ = inner_wall
  return cell_count * grid_size

def build_layout(
  grid_cols: int,
  grid_rows: int,
  grid_size: float,
  inner_wall: float,
  specs: List[CompartmentSpec]
) -> Tuple[List[Placement], Dict[int, int], int]:
  occupied = [[False for _ in range(grid_cols)] for _ in range(grid_rows)]

  # Place larger compartments first to improve fit rate.
  placement_queue: List[Tuple[int, int, int]] = []
  for spec in specs:
    for _ in range(spec.count):
      placement_queue.append((spec.index, spec.grid_w, spec.grid_h))

  placement_queue.sort(key=lambda entry: (entry[1] * entry[2], max(entry[1], entry[2])), reverse=True)

  placements: List[Placement] = []
  missing_by_spec: Dict[int, int] = {spec.index: 0 for spec in specs}

  requested_counter = 1
  for spec_index, grid_w, grid_h in placement_queue:
    placed = False
    for y in range(grid_rows):
      for x in range(grid_cols):
        if not can_place(occupied, x, y, grid_w, grid_h):
          continue

        fill_cells(occupied, x, y, grid_w, grid_h)
        placements.append(
          Placement(
            label=f"C{requested_counter:02d}",
            is_leftover=False,
            x_cell=x,
            y_cell=y,
            w_cells=grid_w,
            h_cells=grid_h,
            x_mm=x * grid_size,
            y_mm=y * grid_size,
            w_mm=grid_to_mm_size(grid_w, grid_size, inner_wall),
            h_mm=grid_to_mm_size(grid_h, grid_size, inner_wall)
          )
        )
        requested_counter += 1
        placed = True
        break
      if placed:
        break

    if not placed:
      missing_by_spec[spec_index] += 1

  missing_total = sum(missing_by_spec.values())

  # Fill leftover grid cells only when all requested compartments fit.
  if missing_total == 0:
    leftover_counter = 1
    for y in range(grid_rows):
      for x in range(grid_cols):
        if occupied[y][x]:
          continue

        occupied[y][x] = True
        placements.append(
          Placement(
            label=f"L{leftover_counter:02d}",
            is_leftover=True,
            x_cell=x,
            y_cell=y,
            w_cells=1,
            h_cells=1,
            x_mm=x * grid_size,
            y_mm=y * grid_size,
            w_mm=grid_to_mm_size(1, grid_size, inner_wall),
            h_mm=grid_to_mm_size(1, grid_size, inner_wall)
          )
        )
        leftover_counter += 1

  return placements, missing_by_spec, missing_total


PIXEL_FONT: Dict[str, List[str]] = {
  "0": ["111", "101", "101", "101", "111"],
  "1": ["010", "110", "010", "010", "111"],
  "2": ["111", "001", "111", "100", "111"],
  "3": ["111", "001", "111", "001", "111"],
  "4": ["101", "101", "111", "001", "001"],
  "5": ["111", "100", "111", "001", "111"],
  "6": ["111", "100", "111", "101", "111"],
  "7": ["111", "001", "001", "001", "001"],
  "8": ["111", "101", "111", "101", "111"],
  "9": ["111", "101", "111", "001", "111"],
  "X": ["101", "101", "010", "101", "101"],
  "x": ["101", "101", "010", "101", "101"],
  "C": ["111", "100", "100", "100", "111"],
  "L": ["100", "100", "100", "100", "111"]
}


def get_text_pixel_dimensions(text: str) -> Tuple[int, int]:
  if not text:
    return 0, 0

  width_units = 0
  for char_index, char in enumerate(text):
    pattern = PIXEL_FONT.get(char)
    if pattern is None:
      continue

    width_units += len(pattern[0])
    if char_index < len(text) - 1:
      width_units += 1

  return width_units, 5


def build_compartment_label_boxes(
  placements: List[Placement],
  bottom_thickness: float,
  grid_size: float
) -> Tuple[List[SolidBox], List[LabelGlyph]]:
  boxes: List[SolidBox] = []
  glyphs: List[LabelGlyph] = []

  def append_text_boxes(
    compartment_label: str,
    text: str,
    start_x: float,
    start_y: float,
    pixel_size: float,
    label_height: float
  ) -> None:
    cursor_x = start_x
    gap_size = pixel_size
    text_units_h = 5

    for char_index, char in enumerate(text):
      pattern = PIXEL_FONT.get(char)
      if pattern is None:
        continue

      pattern_w = len(pattern[0])
      char_boxes: List[SolidBox] = []
      for row_index, row in enumerate(pattern):
        for col_index, cell in enumerate(row):
          if cell != "1":
            continue

          char_box = SolidBox(
            x=cursor_x + col_index * pixel_size,
            y=start_y + (text_units_h - row_index - 1) * pixel_size,
            z=bottom_thickness,
            w=pixel_size,
            h=pixel_size,
            d=label_height
          )
          boxes.append(char_box)
          char_boxes.append(char_box)

      if char_boxes:
        glyphs.append(LabelGlyph(compartment_label=compartment_label, text=char, boxes=char_boxes))

      cursor_x += pattern_w * pixel_size
      if char_index < len(text) - 1:
        cursor_x += gap_size

  for placement in placements:
    primary_text = placement.label
    width_mm = placement.w_cells * grid_size
    height_mm = placement.h_cells * grid_size
    width_text = f"{int(round(width_mm))}" if abs(width_mm - round(width_mm)) <= 1e-9 else f"{width_mm:g}"
    height_text = f"{int(round(height_mm))}" if abs(height_mm - round(height_mm)) <= 1e-9 else f"{height_mm:g}"
    secondary_text = f"{width_text}X{height_text}"
    lines = [primary_text, secondary_text]

    line_dimensions = [get_text_pixel_dimensions(line) for line in lines]
    if any(units_w <= 0 or units_h <= 0 for units_w, units_h in line_dimensions):
      continue

    widest_units = max(units_w for units_w, _ in line_dimensions)
    line_height_units = 5
    line_gap_units = 2
    total_height_units = len(lines) * line_height_units + (len(lines) - 1) * line_gap_units

    margin = max(0.5, min(placement.w_mm, placement.h_mm) * 0.06)
    available_w = placement.w_mm - 2.0 * margin
    available_h = placement.h_mm - 2.0 * margin
    if available_w <= 0 or available_h <= 0:
      continue

    preferred_pixel_size = 0.55
    max_fit_pixel_size = min(available_w / widest_units, available_h / total_height_units)
    pixel_size = min(preferred_pixel_size, max_fit_pixel_size)
    if pixel_size < 0.30:
      continue

    label_height = min(0.65, max(0.3, bottom_thickness * 0.28))
    total_height = total_height_units * pixel_size
    current_y = placement.y_mm + (placement.h_mm - total_height) / 2.0

    for line, (line_units_w, _) in zip(lines, line_dimensions):
      line_w = line_units_w * pixel_size
      start_x = placement.x_mm + (placement.w_mm - line_w) / 2.0
      append_text_boxes(placement.label, line, start_x, current_y, pixel_size, label_height)
      current_y += (line_height_units + line_gap_units) * pixel_size

  return boxes, glyphs


def make_scad(
  outer_length: float,
  outer_width: float,
  outer_height: float,
  inner_length: float,
  inner_width: float,
  inner_height: float,
  inner_wall_height: float,
  outer_wall: float,
  inner_wall: float,
  bottom_thickness: float,
  placements: List[Placement],
  label_glyphs: List[LabelGlyph]
) -> str:
  lines: List[str] = []

  lines.append("// Generated by gridLayoutGenerator.py")
  lines.append("// Straight-corner box generated from grid layout")
  lines.append("")
  lines.append(f"outerLength = {outer_length:.3f};")
  lines.append(f"outerWidth = {outer_width:.3f};")
  lines.append(f"outerHeight = {outer_height:.3f};")
  lines.append(f"innerLength = {inner_length:.3f};")
  lines.append(f"innerWidth = {inner_width:.3f};")
  lines.append(f"innerHeight = {inner_height:.3f};")
  lines.append(f"innerWallHeight = {inner_wall_height:.3f};")
  lines.append(f"outerWall = {outer_wall:.3f};")
  lines.append(f"innerWall = {inner_wall:.3f};")
  lines.append(f"bottomThickness = {bottom_thickness:.3f};")
  lines.append("")

  lines.append("module outerSolid()")
  lines.append("{")
  lines.append("  translate([-outerWall, -outerWall, 0])")
  lines.append("    linear_extrude(height = outerHeight)")
  lines.append("      square([outerLength, outerWidth]);")
  lines.append("}")
  lines.append("")

  lines.append("module mainCavity()")
  lines.append("{")
  lines.append("  translate([0, 0, bottomThickness])")
  lines.append("    linear_extrude(height = innerHeight + 1)")
  lines.append("      square([innerLength, innerWidth]);")
  lines.append("}")
  lines.append("")

  lines.append("module makeCompartment(posX, posY, sizeX, sizeY)")
  lines.append("{")
  lines.append("  tol = 0.0005;")
  lines.append("  innerHalf = innerWall / 2;")
  lines.append("  leftBoundary = posX <= tol;")
  lines.append("  rightBoundary = posX + sizeX >= innerLength - tol;")
  lines.append("  bottomBoundary = posY <= tol;")
  lines.append("  topBoundary = posY + sizeY >= innerWidth - tol;")
  lines.append("  xMin = leftBoundary ? -outerWall : posX - innerHalf;")
  lines.append("  xMax = rightBoundary ? innerLength + outerWall : posX + sizeX + innerHalf;")
  lines.append("  yMin = bottomBoundary ? -outerWall : posY - innerHalf;")
  lines.append("  yMax = topBoundary ? innerWidth + outerWall : posY + sizeY + innerHalf;")
  lines.append("  leftStart = leftBoundary ? -outerWall : posX - innerHalf;")
  lines.append("  rightStart = rightBoundary ? innerLength : posX + sizeX - innerHalf;")
  lines.append("  bottomStart = bottomBoundary ? -outerWall : posY - innerHalf;")
  lines.append("  topStart = topBoundary ? innerWidth : posY + sizeY - innerHalf;")
  lines.append("  leftThickness = leftBoundary ? outerWall : innerWall;")
  lines.append("  rightThickness = rightBoundary ? outerWall : innerWall;")
  lines.append("  bottomThicknessLocal = bottomBoundary ? outerWall : innerWall;")
  lines.append("  topThicknessLocal = topBoundary ? outerWall : innerWall;")
  lines.append("")
  lines.append("  translate([leftStart, yMin, bottomThickness / 2])")
  lines.append("    cube([leftThickness, yMax - yMin, innerWallHeight]);")
  lines.append("  translate([rightStart, yMin, bottomThickness / 2])")
  lines.append("    cube([rightThickness, yMax - yMin, innerWallHeight]);")
  lines.append("  translate([xMin, bottomStart, bottomThickness / 2])")
  lines.append("    cube([xMax - xMin, bottomThicknessLocal, innerWallHeight]);")
  lines.append("  translate([xMin, topStart, bottomThickness / 2])")
  lines.append("    cube([xMax - xMin, topThicknessLocal, innerWallHeight]);")
  lines.append("}")
  lines.append("")

  lines.append("module boxWithCompartments()")
  lines.append("{")
  lines.append("  union()")
  lines.append("  {")
  lines.append("    difference()")
  lines.append("    {")
  lines.append("      outerSolid();")
  lines.append("      mainCavity();")
  lines.append("    }")
  lines.append("")
  lines.append("    union()")
  lines.append("    {")
  for placement in placements:
    kind = "leftover" if placement.is_leftover else "requested"
    lines.append(
      f"      // {placement.label}, {kind}, grid={placement.w_cells}x{placement.h_cells}, size={placement.w_mm:.3f}x{placement.h_mm:.3f}"
    )
    lines.append(
      f"      makeCompartment({placement.x_mm:.3f}, {placement.y_mm:.3f}, {placement.w_mm:.3f}, {placement.h_mm:.3f});"
    )
  for glyph in label_glyphs:
    lines.append(f"      //-- {glyph.compartment_label}: {glyph.text}")
    for label_box in glyph.boxes:
      lines.append(
        f"      translate([{label_box.x:.3f}, {label_box.y:.3f}, {label_box.z:.3f}]) cube([{label_box.w:.3f}, {label_box.h:.3f}, {label_box.d:.3f}]);"
      )
  lines.append("    }")
  lines.append("  }")
  lines.append("}")
  lines.append("")
  lines.append("boxWithCompartments();")
  lines.append("")

  return "\n".join(lines)


def subtract_vec3(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
  return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross_vec3(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
  return (
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0]
  )


def normalize_vec3(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
  length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
  if length <= 1e-12:
    return (0.0, 0.0, 0.0)
  return (v[0] / length, v[1] / length, v[2] / length)


def triangle_normal(
  a: Tuple[float, float, float],
  b: Tuple[float, float, float],
  c: Tuple[float, float, float]
) -> Tuple[float, float, float]:
  return normalize_vec3(cross_vec3(subtract_vec3(b, a), subtract_vec3(c, a)))


def append_triangle(
  triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]],
  a: Tuple[float, float, float],
  b: Tuple[float, float, float],
  c: Tuple[float, float, float]
) -> None:
  triangles.append((a, b, c))


def append_box_triangles(
  triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]],
  x0: float,
  y0: float,
  z0: float,
  x1: float,
  y1: float,
  z1: float
) -> None:
  if x1 <= x0 or y1 <= y0 or z1 <= z0:
    return

  p000 = (x0, y0, z0)
  p001 = (x0, y0, z1)
  p010 = (x0, y1, z0)
  p011 = (x0, y1, z1)
  p100 = (x1, y0, z0)
  p101 = (x1, y0, z1)
  p110 = (x1, y1, z0)
  p111 = (x1, y1, z1)

  append_triangle(triangles, p000, p010, p110)
  append_triangle(triangles, p000, p110, p100)
  append_triangle(triangles, p001, p101, p111)
  append_triangle(triangles, p001, p111, p011)
  append_triangle(triangles, p000, p100, p101)
  append_triangle(triangles, p000, p101, p001)
  append_triangle(triangles, p010, p011, p111)
  append_triangle(triangles, p010, p111, p110)
  append_triangle(triangles, p000, p001, p011)
  append_triangle(triangles, p000, p011, p010)
  append_triangle(triangles, p100, p110, p111)
  append_triangle(triangles, p100, p111, p101)


def build_stl_triangles(
  outer_length: float,
  outer_width: float,
  outer_height: float,
  inner_length: float,
  inner_width: float,
  inner_wall_height: float,
  outer_wall: float,
  inner_wall: float,
  bottom_thickness: float,
  placements: List[Placement],
  label_boxes: List[SolidBox]
) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
  triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []

  append_box_triangles(triangles, -outer_wall, -outer_wall, 0.0, inner_length + outer_wall, inner_width + outer_wall, bottom_thickness)
  append_box_triangles(triangles, -outer_wall, -outer_wall, bottom_thickness, inner_length + outer_wall, 0.0, outer_height)
  append_box_triangles(triangles, -outer_wall, inner_width, bottom_thickness, inner_length + outer_wall, inner_width + outer_wall, outer_height)
  append_box_triangles(triangles, -outer_wall, 0.0, bottom_thickness, 0.0, inner_width, outer_height)
  append_box_triangles(triangles, inner_length, 0.0, bottom_thickness, inner_length + outer_wall, inner_width, outer_height)

  wall_z0 = bottom_thickness / 2.0
  wall_z1 = wall_z0 + inner_wall_height
  tol = 1e-6

  for placement in placements:
    x = placement.x_mm
    y = placement.y_mm
    w = placement.w_mm
    h = placement.h_mm

    inner_half = inner_wall / 2.0
    left_boundary = x <= tol
    right_boundary = x + w >= inner_length - tol
    bottom_boundary = y <= tol
    top_boundary = y + h >= inner_width - tol

    x_min = -outer_wall if left_boundary else x - inner_half
    x_max = inner_length + outer_wall if right_boundary else x + w + inner_half
    y_min = -outer_wall if bottom_boundary else y - inner_half
    y_max = inner_width + outer_wall if top_boundary else y + h + inner_half

    left_start = -outer_wall if left_boundary else x - inner_half
    right_start = inner_length if right_boundary else x + w - inner_half
    bottom_start = -outer_wall if bottom_boundary else y - inner_half
    top_start = inner_width if top_boundary else y + h - inner_half

    left_thickness = outer_wall if left_boundary else inner_wall
    right_thickness = outer_wall if right_boundary else inner_wall
    bottom_thickness_local = outer_wall if bottom_boundary else inner_wall
    top_thickness_local = outer_wall if top_boundary else inner_wall

    append_box_triangles(triangles, left_start, y_min, wall_z0, left_start + left_thickness, y_max, wall_z1)
    append_box_triangles(triangles, right_start, y_min, wall_z0, right_start + right_thickness, y_max, wall_z1)
    append_box_triangles(triangles, x_min, bottom_start, wall_z0, x_max, bottom_start + bottom_thickness_local, wall_z1)
    append_box_triangles(triangles, x_min, top_start, wall_z0, x_max, top_start + top_thickness_local, wall_z1)

  for label_box in label_boxes:
    append_box_triangles(
      triangles,
      label_box.x,
      label_box.y,
      label_box.z,
      label_box.x + label_box.w,
      label_box.y + label_box.h,
      label_box.z + label_box.d
    )

  return triangles


def write_ascii_stl(
  stl_path: Path,
  triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]],
  solid_name: str = "grid_layout_box"
) -> None:
  with stl_path.open("w", encoding="ascii") as handle:
    handle.write(f"solid {solid_name}\n")
    for triangle in triangles:
      normal = triangle_normal(triangle[0], triangle[1], triangle[2])
      handle.write(f"  facet normal {normal[0]:.6g} {normal[1]:.6g} {normal[2]:.6g}\n")
      handle.write("    outer loop\n")
      for vertex in triangle:
        handle.write(f"      vertex {vertex[0]:.6g} {vertex[1]:.6g} {vertex[2]:.6g}\n")
      handle.write("    endloop\n")
      handle.write("  endfacet\n")
    handle.write(f"endsolid {solid_name}\n")


def export_scad_and_stl(
  project_name: str,
  outer_length: float,
  outer_width: float,
  outer_height: float,
  outer_wall: float,
  inner_wall: float,
  bottom_thickness: float,
  inner_wall_height: float,
  grid_size: float,
  placements: List[Placement]
) -> Tuple[Path, Path]:
  _ = grid_size
  inner_length = outer_length - 2.0 * outer_wall
  inner_width = outer_width - 2.0 * outer_wall
  inner_height = outer_height - bottom_thickness
  effective_inner_wall_height = min(inner_wall_height, inner_height)

  label_boxes, label_glyphs = build_compartment_label_boxes(placements, bottom_thickness, grid_size)

  scad_text = make_scad(
    outer_length=outer_length,
    outer_width=outer_width,
    outer_height=outer_height,
    inner_length=inner_length,
    inner_width=inner_width,
    inner_height=inner_height,
    inner_wall_height=effective_inner_wall_height,
    outer_wall=outer_wall,
    inner_wall=inner_wall,
    bottom_thickness=bottom_thickness,
    placements=placements,
    label_glyphs=label_glyphs
  )

  scad_path = Path(f"{project_name}.scad")
  scad_path.write_text(scad_text, encoding="utf-8")

  triangles = build_stl_triangles(
    outer_length=outer_length,
    outer_width=outer_width,
    outer_height=outer_height,
    inner_length=inner_length,
    inner_width=inner_width,
    inner_wall_height=effective_inner_wall_height,
    outer_wall=outer_wall,
    inner_wall=inner_wall,
    bottom_thickness=bottom_thickness,
    placements=placements,
    label_boxes=label_boxes
  )
  stl_path = Path(f"{project_name}.stl")
  write_ascii_stl(stl_path, triangles)

  return scad_path, stl_path


def main() -> None:
  print("gridLayoutGenerator")
  print("-------------------")

  project_name = select_project()
  defaults_path = Path(f".gridLayout.{project_name}.json")
  print(f"Project: {project_name}")

  defaults = load_defaults(defaults_path)

  grid_size = ask_float("Enter gridSize in mm", defaults.grid_size)

  while True:
    outer_length, outer_width, outer_height = ask_outer_size(
      defaults.outer_length,
      defaults.outer_width,
      defaults.outer_height,
      grid_size
    )
    cols = outer_length / grid_size
    rows = outer_width / grid_size

    if abs(cols - round(cols)) <= 1e-9 and abs(rows - round(rows)) <= 1e-9:
      grid_cols = int(round(cols))
      grid_rows = int(round(rows))
      break

    print("")
    print("Error: outer dimensions must each be an exact multiple of gridSize.")
    print(f"Given: L/gridSize={cols:.6f}, W/gridSize={rows:.6f}")
    print("Please re-enter the outer size.")

  outer_wall = ask_float("Enter outer wall thickness (outerWall) in mm", defaults.outer_wall)
  inner_wall = ask_float("Enter inner wall thickness (innerWall) in mm", defaults.inner_wall)
  bottom_thickness = ask_float("Enter bottom thickness in mm", defaults.bottom_thickness)
  inner_height = outer_height - bottom_thickness
  if inner_height <= 0:
    print("Error: bottom thickness is too large for the selected outer height.")
    return
  inner_wall_height = ask_float("Enter inner wall height in mm", defaults.inner_wall_height)
  if inner_wall_height > inner_height:
    print("Warning: inner wall height is larger than usable inner height. It will be capped.")
    inner_wall_height = inner_height

  specs = ask_compartments(defaults.compartments)
  if not specs:
    print("No compartments entered. Stopping.")
    return

  defaults.grid_size = grid_size
  defaults.outer_length = outer_length
  defaults.outer_width = outer_width
  defaults.outer_height = outer_height
  defaults.outer_wall = outer_wall
  defaults.inner_wall = inner_wall
  defaults.bottom_thickness = bottom_thickness
  defaults.inner_wall_height = inner_wall_height
  defaults.compartments = specs
  save_defaults(defaults_path, defaults)

  placements, missing_by_spec, missing_total = build_layout(
    grid_cols=grid_cols,
    grid_rows=grid_rows,
    grid_size=grid_size,
    inner_wall=inner_wall,
    specs=specs
  )

  print("")
  print(f"Grid: {grid_cols} x {grid_rows} cells ({grid_cols * grid_rows} total)")
  print(f"Placed compartments: {len([p for p in placements if not p.is_leftover])}")

  if missing_total > 0:
    print("")
    print("Some requested compartments do not fit:")
    for spec in specs:
      missing = missing_by_spec.get(spec.index, 0)
      if missing <= 0:
        continue
      allowed = spec.count - missing
      print(
        f"  spec {spec.index:02d} ({spec.grid_w}x{spec.grid_h}): "
        f"requested {spec.count}, fits {allowed}, missing {missing}"
      )
    print("")
    print("Tip: reduce the listed counts or use a larger box/grid.")
  else:
    leftovers = len([p for p in placements if p.is_leftover])
    print(f"All requested compartments fit. Leftover 1x1 compartments added: {leftovers}")

  output_data = {
    "project": project_name,
    "grid_size": grid_size,
    "outer_length": outer_length,
    "outer_width": outer_width,
    "outer_height": outer_height,
    "outer_wall": outer_wall,
    "inner_wall": inner_wall,
    "bottom_thickness": bottom_thickness,
    "inner_wall_height": inner_wall_height,
    "grid_cols": grid_cols,
    "grid_rows": grid_rows,
    "compartments": [
      {
        "index": spec.index,
        "grid_w": spec.grid_w,
        "grid_h": spec.grid_h,
        "count": spec.count
      }
      for spec in specs
    ],
    "missing_by_spec": missing_by_spec,
    "placements": [
      {
        "label": placement.label,
        "is_leftover": placement.is_leftover,
        "x_cell": placement.x_cell,
        "y_cell": placement.y_cell,
        "w_cells": placement.w_cells,
        "h_cells": placement.h_cells,
        "x_mm": placement.x_mm,
        "y_mm": placement.y_mm,
        "w_mm": placement.w_mm,
        "h_mm": placement.h_mm
      }
      for placement in placements
    ]
  }

  output_path = Path(f".gridLayout.{project_name}.json")
  output_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")

#  print("")
#  print(f"Configuration and layout saved to {output_path}")

  if missing_total > 0:
    print("SCAD/STL not generated because the requested layout does not fully fit.")
    return

  scad_path, stl_path = export_scad_and_stl(
    project_name=project_name,
    outer_length=outer_length,
    outer_width=outer_width,
    outer_height=outer_height,
    outer_wall=outer_wall,
    inner_wall=inner_wall,
    bottom_thickness=bottom_thickness,
    inner_wall_height=inner_wall_height,
    grid_size=grid_size,
    placements=placements
  )

  print(f"OpenSCAD file written: {scad_path}")
  print(f"STL file written: {stl_path}")


if __name__ == "__main__":
  main()
