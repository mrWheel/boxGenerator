#!/usr/bin/env python3

import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


# ------------------------------------------------------------
# Data classes
# ------------------------------------------------------------

@dataclass
class Rect:
  x: float
  y: float
  w: float
  h: float


@dataclass
class SolidBox:
  x: float
  y: float
  z: float
  w: float
  h: float
  d: float


@dataclass
class ClusterItem:
  cell_w: float
  cell_h: float
  cells: int
  label: str
  placement_mode: str
  lateral_mode: str


@dataclass
class PlacedCluster:
  x: float
  y: float
  w: float
  h: float
  cell_w: float
  cell_h: float
  cells: int
  orientation: str
  label: str
  placement_mode: str
  lateral_mode: str


@dataclass
class CompartmentSpec:
  index: int
  cell_w: float
  cell_h: float
  count: int
  cluster_size: int
  placement_mode: str
  lateral_mode: str


@dataclass
class RunDefaults:
  inner_length: float = 300.0
  inner_width: float = 200.0
  inner_height: float = 80.0
  inner_wall_height: Optional[float] = None
  outer_wall_thickness: float = 2.0
  inner_wall_thickness: float = 2.0
  bottom_thickness: float = 2.0
  outer_corner_radius: float = 10.0
  rng_seed: int = 12345
  layout_attempts: int = 120
  per_item_attempts: int = 50
  free_cell_w: Optional[float] = None
  free_cell_h: Optional[float] = None
  compartments: Optional[List[CompartmentSpec]] = None


@dataclass
class PackingProgress:
  attempt: int
  total_attempts: int
  best_placed_groups: int
  total_groups: int


# ------------------------------------------------------------
# Parsing helpers
# ------------------------------------------------------------

def select_project() -> str:
  """Show a numbered menu of existing projects; return the chosen project name."""
  project_files = sorted(Path(".").glob(".boxGenerator.*.json"))
  projects: List[str] = []
  for pf in project_files:
    name = pf.name[len(".boxGenerator."):-len(".json")]
    projects.append(name)

  if not projects:
    while True:
      name = input("Enter project name: ").strip()
      if name:
        return name
      print("Project name cannot be empty.")

  new_opt = len(projects) + 1
  print("Select a project:")
  for i, name in enumerate(projects, 1):
    print(f"  [{i}] {name}")
  print(f"  [{new_opt}] newProject")

  while True:
    choice = input(f"Choice [1-{new_opt}]: ").strip()
    if not choice:
      continue
    try:
      idx = int(choice)
      if 1 <= idx <= len(projects):
        return projects[idx - 1]
      if idx == new_opt:
        while True:
          name = input("Enter new project name: ").strip()
          if name:
            return name
          print("Project name cannot be empty.")
    except ValueError:
      pass
    print(f"Please enter a number between 1 and {new_opt}.")


def parse_size_2d(text: str) -> Tuple[float, float]:
  cleaned = text.lower().replace(" ", "").replace(",", ".")
  parts = cleaned.split("x")

  if len(parts) != 2:
    raise ValueError("Expected format: length x width")

  width = float(parts[0])
  height = float(parts[1])

  if width <= 0 or height <= 0:
    raise ValueError("Dimensions must be greater than 0")

  return width, height


def parse_size_3d(text: str) -> Tuple[float, float, float]:
  cleaned = text.lower().replace(" ", "").replace(",", ".")
  parts = cleaned.split("x")

  if len(parts) != 3:
    raise ValueError("Expected format: length x width x height")

  length = float(parts[0])
  width = float(parts[1])
  height = float(parts[2])

  if length <= 0 or width <= 0 or height <= 0:
    raise ValueError("Dimensions must be greater than 0")

  return length, width, height


def format_size_2d(width: float, height: float) -> str:
  return f"{width:g}x{height:g}"


def format_size_3d(length: float, width: float, height: float) -> str:
  return f"{length:g}x{width:g}x{height:g}"


def load_defaults(defaults_path: Path) -> RunDefaults:
  if not defaults_path.exists():
    return RunDefaults()

  try:
    with defaults_path.open("r", encoding="utf-8") as handle:
      raw = json.load(handle)
  except (OSError, ValueError, TypeError):
    return RunDefaults()

  compartments_raw = raw.get("compartments") or []
  compartments: List[CompartmentSpec] = []

  for entry in compartments_raw:
    try:
      compartments.append(
        CompartmentSpec(
          index=int(entry.get("index", len(compartments) + 1)),
          cell_w=float(entry["cell_w"]),
          cell_h=float(entry["cell_h"]),
          count=int(entry["count"]),
          cluster_size=int(entry["cluster_size"]),
          placement_mode=str(entry.get("placement_mode", "random")),
          lateral_mode=str(entry.get("lateral_mode", "random"))
        )
      )
    except (KeyError, TypeError, ValueError):
      continue

  return RunDefaults(
    inner_length=float(raw.get("inner_length", 300.0)),
    inner_width=float(raw.get("inner_width", 200.0)),
    inner_height=float(raw.get("inner_height", 80.0)),
    inner_wall_height=(
      float(raw["inner_wall_height"]) if raw.get("inner_wall_height") is not None else None
    ),
    outer_wall_thickness=float(raw.get("outer_wall_thickness", 2.0)),
    inner_wall_thickness=float(raw.get("inner_wall_thickness", 2.0)),
    bottom_thickness=float(raw.get("bottom_thickness", 2.0)),
    outer_corner_radius=float(raw.get("outer_corner_radius", 10.0)),
    rng_seed=int(raw.get("rng_seed", 12345)),
    layout_attempts=int(raw.get("layout_attempts", 120)),
    per_item_attempts=int(raw.get("per_item_attempts", 50)),
    free_cell_w=(float(raw["free_cell_w"]) if raw.get("free_cell_w") is not None else None),
    free_cell_h=(float(raw["free_cell_h"]) if raw.get("free_cell_h") is not None else None),
    compartments=compartments
  )


def save_defaults(defaults: RunDefaults, defaults_path: Path) -> None:
  data = {
    "inner_length": defaults.inner_length,
    "inner_width": defaults.inner_width,
    "inner_height": defaults.inner_height,
    "inner_wall_height": defaults.inner_wall_height,
    "outer_wall_thickness": defaults.outer_wall_thickness,
    "inner_wall_thickness": defaults.inner_wall_thickness,
    "bottom_thickness": defaults.bottom_thickness,
    "outer_corner_radius": defaults.outer_corner_radius,
    "rng_seed": defaults.rng_seed,
    "layout_attempts": defaults.layout_attempts,
    "per_item_attempts": defaults.per_item_attempts,
    "free_cell_w": defaults.free_cell_w,
    "free_cell_h": defaults.free_cell_h,
    "compartments": [
      {
        "index": spec.index,
        "cell_w": spec.cell_w,
        "cell_h": spec.cell_h,
        "count": spec.count,
        "cluster_size": spec.cluster_size,
        "placement_mode": spec.placement_mode,
        "lateral_mode": spec.lateral_mode
      }
      for spec in (defaults.compartments or [])
    ]
  }

  try:
    with defaults_path.open("w", encoding="utf-8") as handle:
      json.dump(data, handle, indent=2)
  except OSError:
    print("Warning: could not write defaults file.")


# ------------------------------------------------------------
# Input helpers
# ------------------------------------------------------------

def ask_box_dimensions(default_value: Tuple[float, float, float]) -> Tuple[float, float, float]:
  while True:
    raw = input(
      "Enter inner box size (length x width x height, "
      f"example: 300x200x80) [{format_size_3d(*default_value)}]: "
    ).strip()

    if raw == "":
      return default_value

    try:
      return parse_size_3d(raw)
    except ValueError as exc:
      print(f"Error: {exc}")


def ask_float(prompt: str, default_value: float, allow_zero: bool = True) -> float:
  raw = input(f"{prompt} [{default_value}]: ").strip()

  if raw == "":
    return default_value

  try:
    value = float(raw.replace(",", "."))
  except ValueError:
    print(f"Warning: Invalid input, default {default_value} will be used.")
    return default_value

  if allow_zero:
    if value < 0:
      print(f"Warning: Value must be >= 0, default {default_value} will be used.")
      return default_value
  else:
    if value <= 0:
      print(f"Warning: Value must be > 0, default {default_value} will be used.")
      return default_value

  return value


def ask_int(prompt: str, default_value: int, min_value: int = 1) -> int:
  raw = input(f"{prompt} [{default_value}]: ").strip()

  if raw == "":
    return default_value

  try:
    value = int(raw)
  except ValueError:
    print(f"Warning: Invalid input, default {default_value} will be used.")
    return default_value

  if value < min_value:
    print(f"Warning: Value must be >= {min_value}, default {default_value} will be used.")
    return default_value

  return value


def ask_choice(prompt: str, options: List[str], default_value: str) -> str:
  normalized = {option.lower(): option.lower() for option in options}
  default_key = default_value.lower()

  while True:
    raw = input(f"{prompt} ({'/'.join(options)}) [{default_value}]: ").strip().lower()

    if raw == "":
      return default_key

    if raw in normalized:
      return normalized[raw]

    print(f"Warning: invalid choice. Use one of: {', '.join(options)}")


def ask_yes_no(prompt: str, default_value: bool = False) -> bool:
  default_text = "Y" if default_value else "N"

  while True:
    raw = input(f"{prompt} (Y/N) [{default_text}]: ").strip().lower()

    if raw == "":
      return default_value

    if raw in ("y", "yes"):
      return True

    if raw in ("n", "no"):
      return False

    print("Warning: invalid choice. Use Y or N.")


def ask_optional_size_2d(prompt: str) -> Optional[Tuple[float, float]]:
  raw = input(f"{prompt} (length x width, empty = skip): ").strip()

  if raw == "":
    return None

  try:
    return parse_size_2d(raw)
  except ValueError as exc:
    print(f"Warning: {exc}. Option ignored.")
    return None


def ask_optional_size_2d_with_default(
  prompt: str,
  default_value: Optional[Tuple[float, float]]
) -> Optional[Tuple[float, float]]:
  default_text = format_size_2d(*default_value) if default_value is not None else ""
  raw = input(
    f"{prompt} (length x width, '-' = skip){f' [{default_text}]' if default_text else ''}: "
  ).strip()

  if raw == "":
    return default_value

  if raw == "-":
    return None

  try:
    return parse_size_2d(raw)
  except ValueError as exc:
    print(f"Warning: {exc}. Previous/default value is kept.")
    return default_value


def ask_cluster_items(default_specs: Optional[List[CompartmentSpec]]) -> Tuple[List[ClusterItem], List[CompartmentSpec]]:
  items: List[ClusterItem] = []
  specs: List[CompartmentSpec] = []
  group_index = 1

  print("")
  print("Enter compartment definitions.")
  print("Example size: 25x30")
  print("Cluster size means how many equal compartments must touch each other.")
  print("Example: size 25x30, count 8, cluster 3 => groups of 3, 3, and 2")
  print("Empty size reuses the default size and still shows the remaining questions.")
  print("If no default exists yet, empty size finishes input.")
  print("Use 'keep' to reuse a default compartment without editing.")
  print("Use '0x0' to remove/skip a compartment and skip follow-up questions.")
  print("")

  while True:
    default_spec = None
    if default_specs is not None and group_index - 1 < len(default_specs):
      default_spec = default_specs[group_index - 1]

    default_size_text = ""
    if default_spec is not None:
      default_size_text = format_size_2d(default_spec.cell_w, default_spec.cell_h)

    raw_size = input(
      f"Compartment {group_index} size (length x width){f' [{default_size_text}]' if default_size_text else ''} "
      "(empty = default-size, 'keep' = default-all, '0x0' = skip): "
    ).strip()

    lowered = raw_size.lower()

    if lowered == "":
      if default_spec is None:
        break

      cell_w, cell_h = default_spec.cell_w, default_spec.cell_h

    if lowered == "keep":
      if default_spec is None:
        print("Warning: no default exists for this compartment, enter a size instead.")
        continue

      specs.append(default_spec)

      remaining = default_spec.count
      cluster_index = 1

      while remaining > 0:
        cells_in_group = min(default_spec.cluster_size, remaining)
        items.append(
          ClusterItem(
            cell_w=default_spec.cell_w,
            cell_h=default_spec.cell_h,
            cells=cells_in_group,
            label=f"group_{group_index}_{cluster_index}",
            placement_mode=default_spec.placement_mode,
            lateral_mode=default_spec.lateral_mode
          )
        )
        remaining -= cells_in_group
        cluster_index += 1

      group_index += 1
      print("")
      continue

    if lowered.replace(" ", "") == "0x0":
      print(f"Compartment {group_index} skipped.")
      group_index += 1
      print("")
      continue

    if lowered != "":
      try:
        cell_w, cell_h = parse_size_2d(raw_size)
      except ValueError as exc:
        print(f"Error: {exc}")
        continue

    count_default = default_spec.count if default_spec is not None else 1
    cluster_default = default_spec.cluster_size if default_spec is not None else 1
    placement_default = default_spec.placement_mode if default_spec is not None else "random"
    lateral_default = default_spec.lateral_mode if default_spec is not None else "middle"

    count = ask_int(f"Compartment {group_index} count", count_default, 1)
    cluster_size = ask_int(f"Compartment {group_index} cluster size", cluster_default, 1)
    placement_mode = ask_choice(
      f"Compartment {group_index} preferred placement",
      ["random", "front", "back"],
      placement_default
    )

    lateral_mode = "random"
    if placement_mode in ("front", "back"):
      lateral_mode = ask_choice(
        f"Compartment {group_index} side preference",
        ["left", "right", "middle"],
        lateral_default
      )

    specs.append(
      CompartmentSpec(
        index=group_index,
        cell_w=cell_w,
        cell_h=cell_h,
        count=count,
        cluster_size=cluster_size,
        placement_mode=placement_mode,
        lateral_mode=lateral_mode
      )
    )

    if cluster_size > count:
      cluster_size = count

    remaining = count
    cluster_index = 1

    while remaining > 0:
      cells_in_group = min(cluster_size, remaining)

      items.append(
        ClusterItem(
          cell_w=cell_w,
          cell_h=cell_h,
          cells=cells_in_group,
          label=f"group_{group_index}_{cluster_index}",
          placement_mode=placement_mode,
          lateral_mode=lateral_mode
        )
      )

      remaining -= cells_in_group
      cluster_index += 1

    group_index += 1
    print("")

  return items, specs


def print_area_reduction_suggestions(specs: List[CompartmentSpec], excess_area: float) -> None:
  if not specs:
    return

  print("")
  print("Suggestions to make it fit:")

  greedy_specs = sorted(specs, key=lambda spec: spec.cell_w * spec.cell_h, reverse=True)
  remaining = excess_area
  greedy_lines: List[str] = []

  for spec in greedy_specs:
    if remaining <= 0:
      break

    area_each = spec.cell_w * spec.cell_h
    remove_count = min(spec.count, math.ceil(remaining / area_each))
    if remove_count <= 0:
      continue

    max_times = spec.count - remove_count
    if max_times <= 0:
      greedy_lines.append(
        f"  Compartment {spec.index} ({spec.cell_w:g}x{spec.cell_h:g}) remove completely (or set size to 0x0)"
      )
    else:
      greedy_lines.append(
        f"  Compartment {spec.index} ({spec.cell_w:g}x{spec.cell_h:g}) max {max_times} times"
      )
    remaining -= remove_count * area_each

  if greedy_lines:
    print("  Direct fix (remove in this order):")
    for line in greedy_lines:
      print(line)

  print("  Alternatives per compartment:")
  for spec in specs:
    area_each = spec.cell_w * spec.cell_h
    required_remove = math.ceil(excess_area / area_each)
    max_times = max(0, spec.count - required_remove)

    if max_times < spec.count:
      if max_times <= 0:
        print(
          f"  Compartment {spec.index} ({spec.cell_w:g}x{spec.cell_h:g}) remove completely (or set size to 0x0)"
        )
      else:
        print(
          f"  Compartment {spec.index} ({spec.cell_w:g}x{spec.cell_h:g}) max {max_times} times"
        )


def compartment_index_from_label(label: str) -> Optional[int]:
  parts = label.split("_")
  if len(parts) < 3 or parts[0] != "group":
    return None

  try:
    return int(parts[1])
  except ValueError:
    return None


def print_missing_group_suggestions(specs: List[CompartmentSpec], missing_items: List[ClusterItem]) -> None:
  missing_groups = len(missing_items)
  print("")
  print(f"Error: Not all cluster groups could be placed. Missing groups: {missing_groups}")

  if not missing_items:
    return

  missing_cells_by_compartment: dict[int, int] = {}
  for item in missing_items:
    index = compartment_index_from_label(item.label)
    if index is None:
      continue
    missing_cells_by_compartment[index] = missing_cells_by_compartment.get(index, 0) + item.cells

  if not missing_cells_by_compartment:
    print("Hint: Increase the box size, reduce the number of compartments, or increase the attempt counts.")
    return

  print("Suggested compartment adjustments:")
  suggestions: List[Tuple[float, int, CompartmentSpec, int]] = []
  for spec in specs:
    missing_cells = missing_cells_by_compartment.get(spec.index, 0)
    if missing_cells <= 0:
      continue

    impact = missing_cells * spec.cell_w * spec.cell_h
    suggestions.append((impact, missing_cells, spec, max(0, spec.count - missing_cells)))

  suggestions.sort(key=lambda entry: (entry[0], entry[1], entry[2].cell_w * entry[2].cell_h), reverse=True)

  for _, _, spec, suggested_count in suggestions:

    if suggested_count <= 0:
      print(
        f"  Compartment {spec.index} ({spec.cell_w:g}x{spec.cell_h:g}): remove completely "
        "(or set size to 0x0)"
      )
    else:
      print(
        f"  Compartment {spec.index} ({spec.cell_w:g}x{spec.cell_h:g}): "
        f"count {suggested_count} in plaats van {spec.count}"
      )

  print("Hint: You can also increase layout attempts or attempts per group for difficult layouts.")


# ------------------------------------------------------------
# Rectangle helpers
# ------------------------------------------------------------

def rect_area(rect: Rect) -> float:
  return rect.w * rect.h


def contains_rect(outer: Rect, inner: Rect, eps: float = 1e-9) -> bool:
  return (
    inner.x >= outer.x - eps and
    inner.y >= outer.y - eps and
    inner.x + inner.w <= outer.x + outer.w + eps and
    inner.y + inner.h <= outer.y + outer.h + eps
  )


def intersects(a: Rect, b: Rect, eps: float = 1e-9) -> bool:
  return not (
    a.x + a.w <= b.x + eps or
    b.x + b.w <= a.x + eps or
    a.y + a.h <= b.y + eps or
    b.y + b.h <= a.y + eps
  )


def subtract_rect(space: Rect, cut: Rect, eps: float = 1e-9) -> List[Rect]:
  if not intersects(space, cut, eps):
    return [space]

  ix0 = max(space.x, cut.x)
  iy0 = max(space.y, cut.y)
  ix1 = min(space.x + space.w, cut.x + cut.w)
  iy1 = min(space.y + space.h, cut.y + cut.h)

  if ix1 <= ix0 + eps or iy1 <= iy0 + eps:
    return [space]

  result: List[Rect] = []

  left_rect = Rect(space.x, space.y, ix0 - space.x, space.h)
  right_rect = Rect(ix1, space.y, (space.x + space.w) - ix1, space.h)
  bottom_rect = Rect(ix0, space.y, ix1 - ix0, iy0 - space.y)
  top_rect = Rect(ix0, iy1, ix1 - ix0, (space.y + space.h) - iy1)

  for rect in (left_rect, right_rect, bottom_rect, top_rect):
    if rect.w > eps and rect.h > eps:
      result.append(rect)

  return result


def merge_adjacent_rectangles(rects: List[Rect], eps: float = 1e-9) -> List[Rect]:
  merged = rects[:]
  changed = True

  while changed:
    changed = False
    new_rects: List[Rect] = []
    used = [False] * len(merged)

    for i in range(len(merged)):
      if used[i]:
        continue

      a = merged[i]
      did_merge = False

      for j in range(i + 1, len(merged)):
        if used[j]:
          continue

        b = merged[j]

        if abs(a.y - b.y) < eps and abs(a.h - b.h) < eps:
          if abs((a.x + a.w) - b.x) < eps:
            new_rects.append(Rect(a.x, a.y, a.w + b.w, a.h))
            used[i] = True
            used[j] = True
            changed = True
            did_merge = True
            break

          if abs((b.x + b.w) - a.x) < eps:
            new_rects.append(Rect(b.x, b.y, a.w + b.w, a.h))
            used[i] = True
            used[j] = True
            changed = True
            did_merge = True
            break

        if abs(a.x - b.x) < eps and abs(a.w - b.w) < eps:
          if abs((a.y + a.h) - b.y) < eps:
            new_rects.append(Rect(a.x, a.y, a.w, a.h + b.h))
            used[i] = True
            used[j] = True
            changed = True
            did_merge = True
            break

          if abs((b.y + b.h) - a.y) < eps:
            new_rects.append(Rect(b.x, b.y, a.w, a.h + b.h))
            used[i] = True
            used[j] = True
            changed = True
            did_merge = True
            break

      if not did_merge and not used[i]:
        new_rects.append(a)
        used[i] = True

    merged = new_rects

  return merged


def normalize_free_rects(rects: List[Rect], eps: float = 1e-9) -> List[Rect]:
  filtered = [rect for rect in rects if rect.w > eps and rect.h > eps]

  changed = True
  while changed:
    changed = False
    new_rects: List[Rect] = []

    for i, rect in enumerate(filtered):
      contained = False

      for j, other in enumerate(filtered):
        if i == j:
          continue

        if contains_rect(other, rect, eps):
          contained = True
          changed = True
          break

      if not contained:
        new_rects.append(rect)

    filtered = new_rects

  return merge_adjacent_rectangles(filtered, eps)


def clip_rect_to_domain(rect: Rect, domain: Rect) -> Optional[Rect]:
  x0 = max(rect.x, domain.x)
  y0 = max(rect.y, domain.y)
  x1 = min(rect.x + rect.w, domain.x + domain.w)
  y1 = min(rect.y + rect.h, domain.y + domain.h)

  if x1 <= x0 or y1 <= y0:
    return None

  return Rect(x0, y0, x1 - x0, y1 - y0)


# ------------------------------------------------------------
# Cluster footprint helpers
# ------------------------------------------------------------

def get_cluster_footprints(
  item: ClusterItem,
  inner_wall_thickness: float
) -> List[Tuple[str, float, float]]:
  if item.cells <= 1:
    return [("single", item.cell_w, item.cell_h)]

  horizontal_w = item.cells * item.cell_w + (item.cells - 1) * inner_wall_thickness
  horizontal_h = item.cell_h

  vertical_w = item.cell_w
  vertical_h = item.cells * item.cell_h + (item.cells - 1) * inner_wall_thickness

  if abs(horizontal_w - vertical_w) < 1e-9 and abs(horizontal_h - vertical_h) < 1e-9:
    return [("horizontal", horizontal_w, horizontal_h)]

  return [
    ("horizontal", horizontal_w, horizontal_h),
    ("vertical", vertical_w, vertical_h)
  ]


def cluster_sort_key(item: ClusterItem, inner_wall_thickness: float) -> Tuple[float, float, float]:
  footprints = get_cluster_footprints(item, inner_wall_thickness)
  max_area = max(width * height for _, width, height in footprints)
  max_side = max(max(width, height) for _, width, height in footprints)
  min_side = max(min(width, height) for _, width, height in footprints)

  return (max_area, max_side, min_side)


# ------------------------------------------------------------
# Random placement
# ------------------------------------------------------------

def choose_anchor_position(
  space: Rect,
  item_w: float,
  item_h: float,
  rng: random.Random,
  item: ClusterItem,
  domain: Rect
) -> Tuple[float, float]:
  dx = space.w - item_w
  dy = space.h - item_h

  if item.placement_mode in ("front", "back"):
    if item.placement_mode == "front":
      target_y = domain.y
    else:
      target_y = domain.y + domain.h - item_h

    min_y = space.y
    max_y = space.y + dy
    y = min(max(target_y, min_y), max_y)

    if item.lateral_mode == "left":
      target_x = domain.x
    elif item.lateral_mode == "right":
      target_x = domain.x + domain.w - item_w
    else:
      target_x = domain.x + (domain.w - item_w) / 2.0

    min_x = space.x
    max_x = space.x + dx
    x = min(max(target_x, min_x), max_x)

    return x, y

  anchors = [
    (0.0, 0.0),
    (dx, 0.0),
    (0.0, dy),
    (dx, dy),
    (dx / 2.0, dy / 2.0),
    (rng.uniform(0.0, dx), rng.uniform(0.0, dy))
  ]

  offset_x, offset_y = rng.choice(anchors)

  return space.x + offset_x, space.y + offset_y


def try_place_cluster(
  free_rects: List[Rect],
  item: ClusterItem,
  rng: random.Random,
  per_item_attempts: int,
  separator_thickness: float,
  domain: Rect
) -> Optional[Tuple[PlacedCluster, List[Rect]]]:
  candidates: List[Tuple[PlacedCluster, List[Rect], int]] = []

  for _ in range(per_item_attempts):
    shuffled_spaces = free_rects[:]
    rng.shuffle(shuffled_spaces)

    for space in shuffled_spaces:
      footprints = get_cluster_footprints(item, separator_thickness)
      shuffled_footprints = footprints[:]
      rng.shuffle(shuffled_footprints)

      for orientation, footprint_w, footprint_h in shuffled_footprints:
        if footprint_w > space.w or footprint_h > space.h:
          continue

        pos_x, pos_y = choose_anchor_position(
          space,
          footprint_w,
          footprint_h,
          rng,
          item,
          domain
        )

        placed = PlacedCluster(
          x=pos_x,
          y=pos_y,
          w=footprint_w,
          h=footprint_h,
          cell_w=item.cell_w,
          cell_h=item.cell_h,
          cells=item.cells,
          orientation=orientation,
          label=item.label,
          placement_mode=item.placement_mode,
          lateral_mode=item.lateral_mode
        )

        blocked = Rect(
          placed.x - separator_thickness,
          placed.y - separator_thickness,
          placed.w + 2.0 * separator_thickness,
          placed.h + 2.0 * separator_thickness
        )

        blocked_clipped = clip_rect_to_domain(blocked, domain)
        if blocked_clipped is None:
          continue

        updated_free: List[Rect] = []
        for existing in free_rects:
          updated_free.extend(subtract_rect(existing, blocked_clipped))

        updated_free = normalize_free_rects(updated_free)
        fragmentation_score = len(updated_free)

        candidates.append((placed, updated_free, fragmentation_score))

  if not candidates:
    return None

  candidates.sort(key=lambda entry: entry[2])
  best_band = candidates[:max(1, min(8, len(candidates)))]
  chosen_placed, chosen_free, _ = rng.choice(best_band)

  return chosen_placed, chosen_free


def pack_clusters_random(
  inner_length: float,
  inner_width: float,
  inner_wall_thickness: float,
  items: List[ClusterItem],
  rng_seed: int,
  layout_attempts: int,
  per_item_attempts: int,
  show_progress: bool = True
) -> Tuple[List[PlacedCluster], List[Rect], Rect, List[ClusterItem]]:
  edge_margin = inner_wall_thickness / 2.0
  domain = Rect(
    edge_margin,
    edge_margin,
    inner_length - inner_wall_thickness,
    inner_width - inner_wall_thickness
  )

  if domain.w <= 0 or domain.h <= 0:
    raise RuntimeError("Inner box size is too small for the requested inner wall thickness.")

  items_sorted = sorted(
    items,
    key=lambda item: cluster_sort_key(item, inner_wall_thickness),
    reverse=True
  )

  best_result: Optional[Tuple[List[PlacedCluster], List[Rect], int, int]] = None
  progress_step = max(1, layout_attempts // 12)

  for attempt_index in range(layout_attempts):
    rng = random.Random(rng_seed + attempt_index)

    free_rects: List[Rect] = [domain]
    placed_clusters: List[PlacedCluster] = []
    placed_count = 0
    success = True

    for item in items_sorted:
      placement = try_place_cluster(
        free_rects=free_rects,
        item=item,
        rng=rng,
        per_item_attempts=per_item_attempts,
        separator_thickness=inner_wall_thickness,
        domain=domain
      )

      if placement is None:
        success = False
        break

      placed_cluster, free_rects = placement
      placed_clusters.append(placed_cluster)
      placed_count += 1

    free_rects = normalize_free_rects(free_rects)

    if success:
      score = (
        len(free_rects),
        sum(rect_area(rect) for rect in free_rects),
        attempt_index
      )

      if best_result is None:
        best_result = (placed_clusters, free_rects, placed_count, attempt_index)
      else:
        current_score = (
          len(best_result[1]),
          sum(rect_area(rect) for rect in best_result[1]),
          best_result[3]
        )

        if score < current_score:
          best_result = (placed_clusters, free_rects, placed_count, attempt_index)
    else:
      if best_result is None or placed_count > best_result[2]:
        best_result = (placed_clusters, free_rects, placed_count, attempt_index)

    if show_progress and (
      attempt_index == 0 or
      (attempt_index + 1) % progress_step == 0 or
      attempt_index + 1 == layout_attempts
    ):
      current_best = best_result[2] if best_result is not None else 0
      print(
        f"Packing progress: attempt {attempt_index + 1}/{layout_attempts}, "
        f"best placed groups {current_best}/{len(items_sorted)}"
      )

  if best_result is None:
    raise RuntimeError("No valid layout could be generated.")

  placed_clusters, free_rects, placed_count, _ = best_result
  placed_labels = {cluster.label for cluster in placed_clusters}
  missing_items = [item for item in items_sorted if item.label not in placed_labels]

  return placed_clusters, free_rects, domain, missing_items


# ------------------------------------------------------------
# Cavity generation
# ------------------------------------------------------------

def cluster_to_cavities(cluster: PlacedCluster, inner_wall_thickness: float) -> List[Rect]:
  cavities: List[Rect] = []

  if cluster.cells == 1:
    cavities.append(Rect(cluster.x, cluster.y, cluster.cell_w, cluster.cell_h))
    return cavities

  if cluster.orientation == "horizontal":
    for index in range(cluster.cells):
      cavity_x = cluster.x + index * (cluster.cell_w + inner_wall_thickness)
      cavity_y = cluster.y

      cavities.append(
        Rect(cavity_x, cavity_y, cluster.cell_w, cluster.cell_h)
      )

    return cavities

  if cluster.orientation == "vertical":
    for index in range(cluster.cells):
      cavity_x = cluster.x
      cavity_y = cluster.y + index * (cluster.cell_h + inner_wall_thickness)

      cavities.append(
        Rect(cavity_x, cavity_y, cluster.cell_w, cluster.cell_h)
      )

    return cavities

  cavities.append(Rect(cluster.x, cluster.y, cluster.cell_w, cluster.cell_h))
  return cavities


def build_all_cavities(
  placed_clusters: List[PlacedCluster],
  free_rects: List[Rect],
  inner_wall_thickness: float,
  free_cell_size: Optional[Tuple[float, float]]
) -> Tuple[List[Rect], List[Rect]]:
  requested_cavities: List[Rect] = []

  for cluster in placed_clusters:
    requested_cavities.extend(cluster_to_cavities(cluster, inner_wall_thickness))

  if free_cell_size is not None:
    merged_free_rects = merge_adjacent_rectangles(free_rects)
    cell_w, cell_h = free_cell_size
    free_cavities = split_free_rects_into_cells(
      merged_free_rects,
      cell_w,
      cell_h,
      inner_wall_thickness
    )
  else:
    free_cavities = merge_adjacent_rectangles(free_rects)

  return requested_cavities, free_cavities


def build_wall_rects(domain: Rect, cavities: List[Rect]) -> List[Rect]:
  wall_rects: List[Rect] = [domain]

  for cavity in cavities:
    updated_rects: List[Rect] = []
    for wall_rect in wall_rects:
      updated_rects.extend(subtract_rect(wall_rect, cavity))
    wall_rects = normalize_free_rects(updated_rects)

  return normalize_free_rects(wall_rects)


def to_centerline_cavities(
  cavities: List[Rect],
  wall_thickness: float,
  eps: float = 1e-9
) -> List[Rect]:
  """
  Convert nominal compartment rectangles to centerline-based cavities.
  Per axis, total cavity reduction is wall_thickness / 2, centered around midpoint.
  """
  if wall_thickness <= eps:
    return cavities[:]

  inset = wall_thickness / 4.0
  adjusted: List[Rect] = []

  for cavity in cavities:
    new_w = cavity.w - 2.0 * inset
    new_h = cavity.h - 2.0 * inset
    if new_w <= eps or new_h <= eps:
      continue
    adjusted.append(Rect(cavity.x + inset, cavity.y + inset, new_w, new_h))

  return adjusted


def merge_1d_intervals(intervals: List[Tuple[float, float]], eps: float = 1e-9) -> List[Tuple[float, float]]:
  if not intervals:
    return []

  sorted_intervals = sorted(intervals, key=lambda entry: entry[0])
  merged: List[Tuple[float, float]] = [sorted_intervals[0]]

  for start, end in sorted_intervals[1:]:
    last_start, last_end = merged[-1]
    if start <= last_end + eps:
      merged[-1] = (last_start, max(last_end, end))
    else:
      merged.append((start, end))

  return merged


def has_line_coverage(
  wall_rects: List[Rect],
  is_vertical: bool,
  line_value: float,
  span_start: float,
  span_end: float,
  eps: float = 1e-9
) -> bool:
  intervals: List[Tuple[float, float]] = []

  for wall_rect in wall_rects:
    if is_vertical:
      if wall_rect.x - eps <= line_value <= wall_rect.x + wall_rect.w + eps:
        overlap_start = max(span_start, wall_rect.y)
        overlap_end = min(span_end, wall_rect.y + wall_rect.h)
        if overlap_end - overlap_start > eps:
          intervals.append((overlap_start, overlap_end))
    else:
      if wall_rect.y - eps <= line_value <= wall_rect.y + wall_rect.h + eps:
        overlap_start = max(span_start, wall_rect.x)
        overlap_end = min(span_end, wall_rect.x + wall_rect.w)
        if overlap_end - overlap_start > eps:
          intervals.append((overlap_start, overlap_end))

  if not intervals:
    return False

  merged = merge_1d_intervals(intervals, eps)
  covered_until = span_start

  for start, end in merged:
    if start > covered_until + eps:
      return False
    covered_until = max(covered_until, end)
    if covered_until >= span_end - eps:
      return True

  return covered_until >= span_end - eps


def clip_rect_to_domain_strict(rect: Rect, domain: Rect, eps: float = 1e-9) -> Optional[Rect]:
  clipped = clip_rect_to_domain(rect, domain)
  if clipped is None:
    return None

  if clipped.w <= eps or clipped.h <= eps:
    return None

  return clipped


def ensure_cavity_closure(
  domain: Rect,
  cavities: List[Rect],
  wall_rects: List[Rect],
  wall_thickness: float,
  eps: float = 1e-9
) -> List[Rect]:
  if wall_thickness <= eps:
    return wall_rects

  completed = wall_rects[:]
  max_x = domain.x + domain.w
  max_y = domain.y + domain.h

  for cavity in cavities:
    left_edge = cavity.x
    right_edge = cavity.x + cavity.w
    bottom_edge = cavity.y
    top_edge = cavity.y + cavity.h

    left_on_boundary = left_edge <= domain.x + eps
    right_on_boundary = right_edge >= max_x - eps
    bottom_on_boundary = bottom_edge <= domain.y + eps
    top_on_boundary = top_edge >= max_y - eps

    if not left_on_boundary and not has_line_coverage(completed, True, left_edge, bottom_edge, top_edge, eps):
      missing = clip_rect_to_domain_strict(
        Rect(left_edge - wall_thickness, bottom_edge, wall_thickness, cavity.h),
        domain,
        eps
      )
      if missing is not None:
        completed.append(missing)

    if not right_on_boundary and not has_line_coverage(completed, True, right_edge, bottom_edge, top_edge, eps):
      missing = clip_rect_to_domain_strict(
        Rect(right_edge, bottom_edge, wall_thickness, cavity.h),
        domain,
        eps
      )
      if missing is not None:
        completed.append(missing)

    if not bottom_on_boundary and not has_line_coverage(completed, False, bottom_edge, left_edge, right_edge, eps):
      missing = clip_rect_to_domain_strict(
        Rect(left_edge, bottom_edge - wall_thickness, cavity.w, wall_thickness),
        domain,
        eps
      )
      if missing is not None:
        completed.append(missing)

    if not top_on_boundary and not has_line_coverage(completed, False, top_edge, left_edge, right_edge, eps):
      missing = clip_rect_to_domain_strict(
        Rect(left_edge, top_edge, cavity.w, wall_thickness),
        domain,
        eps
      )
      if missing is not None:
        completed.append(missing)

  return normalize_free_rects(completed)


def extend_walls_for_overlap(
  wall_rects: List[Rect],
  domain: Rect,
  extension: float,
  wall_thickness: float,
  debug: bool = False,
  eps: float = 1e-9
) -> List[Rect]:
  """
  Extend each wall's length by 'extension' distance on both ends.
  The transform is applied per wall rectangle and returned as-is (no merge),
  so start/end offsets remain exact for each individual wall.
  No clipping is applied so walls may start below 0 or end beyond inner bounds.
  """
  _ = domain

  if extension <= eps:
    return wall_rects

  extended: List[Rect] = []
  axis_tol = max(eps, wall_thickness * 0.35)
  thickness_tol = max(eps, wall_thickness * 0.51)

  def classify_orientation(rect: Rect) -> str:
    h_near_thickness = abs(rect.h - wall_thickness) <= thickness_tol
    w_near_thickness = abs(rect.w - wall_thickness) <= thickness_tol

    if h_near_thickness and not w_near_thickness:
      return "horizontal-thickness"
    if w_near_thickness and not h_near_thickness:
      return "vertical-thickness"
    if rect.w > rect.h + axis_tol:
      return "horizontal-length"
    if rect.h > rect.w + axis_tol:
      return "vertical-length"
    return "horizontal-tie" if rect.w > rect.h else "vertical-tie"

  def has_vertical_touch(x_value: float, y0: float, y1: float) -> bool:
    if x_value <= domain.x + eps or x_value >= domain.x + domain.w - eps:
      return True

    for candidate in wall_rects:
      orientation = classify_orientation(candidate)
      if not orientation.startswith("vertical"):
        continue

      cx0 = candidate.x
      cx1 = candidate.x + candidate.w
      cy0 = candidate.y
      cy1 = candidate.y + candidate.h
      overlap_y0 = max(y0, cy0)
      overlap_y1 = min(y1, cy1)

      if overlap_y1 - overlap_y0 > eps and cx0 - eps <= x_value <= cx1 + eps:
        return True

    return False

  def has_horizontal_touch(y_value: float, x0: float, x1: float) -> bool:
    if y_value <= domain.y + eps or y_value >= domain.y + domain.h - eps:
      return True

    for candidate in wall_rects:
      orientation = classify_orientation(candidate)
      if not orientation.startswith("horizontal"):
        continue

      cx0 = candidate.x
      cx1 = candidate.x + candidate.w
      cy0 = candidate.y
      cy1 = candidate.y + candidate.h
      overlap_x0 = max(x0, cx0)
      overlap_x1 = min(x1, cx1)

      if overlap_x1 - overlap_x0 > eps and cy0 - eps <= y_value <= cy1 + eps:
        return True

    return False

  if debug:
    print("Wall extension debug (before -> after):")
  
  for index, wall in enumerate(wall_rects, start=1):
    new_x = wall.x
    new_y = wall.y
    new_w = wall.w
    new_h = wall.h

    orientation = classify_orientation(wall)

    if orientation.startswith("horizontal"):
      candidates = [
        ("split", wall.x - extension, wall.w + 2.0 * extension),
        ("neg-heavy", wall.x - 2.0 * extension, wall.w + 2.0 * extension),
        ("pos-heavy", wall.x, wall.w + 2.0 * extension)
      ]

      best_mode = "split"
      best_x = wall.x - extension
      best_w = wall.w + 2.0 * extension
      best_score = -1
      best_shift = float("inf")

      for mode, cand_x, cand_w in candidates:
        cand_x0 = cand_x
        cand_x1 = cand_x + cand_w
        left_touch = has_vertical_touch(cand_x0, wall.y, wall.y + wall.h)
        right_touch = has_vertical_touch(cand_x1, wall.y, wall.y + wall.h)
        score = (1 if left_touch else 0) + (1 if right_touch else 0)
        shift = abs(cand_x - wall.x)

        if score > best_score or (score == best_score and shift < best_shift - eps):
          best_score = score
          best_shift = shift
          best_mode = mode
          best_x = cand_x
          best_w = cand_w

      new_x = best_x
      new_w = best_w
      orientation = f"{orientation}:{best_mode}"
    else:
      candidates = [
        ("split", wall.y - extension, wall.h + 2.0 * extension),
        ("neg-heavy", wall.y - 2.0 * extension, wall.h + 2.0 * extension),
        ("pos-heavy", wall.y, wall.h + 2.0 * extension)
      ]

      best_mode = "split"
      best_y = wall.y - extension
      best_h = wall.h + 2.0 * extension
      best_score = -1
      best_shift = float("inf")

      for mode, cand_y, cand_h in candidates:
        cand_y0 = cand_y
        cand_y1 = cand_y + cand_h
        bottom_touch = has_horizontal_touch(cand_y0, wall.x, wall.x + wall.w)
        top_touch = has_horizontal_touch(cand_y1, wall.x, wall.x + wall.w)
        score = (1 if bottom_touch else 0) + (1 if top_touch else 0)
        shift = abs(cand_y - wall.y)

        if score > best_score or (score == best_score and shift < best_shift - eps):
          best_score = score
          best_shift = shift
          best_mode = mode
          best_y = cand_y
          best_h = cand_h

      new_y = best_y
      new_h = best_h
      orientation = f"{orientation}:{best_mode}"
    
    if new_w > eps and new_h > eps:
      extended.append(Rect(new_x, new_y, new_w, new_h))
      if debug:
        print(
          f"  [{index}] {orientation}: "
          f"({wall.x:.3f}, {wall.y:.3f}, {wall.w:.3f}, {wall.h:.3f}) -> "
          f"({new_x:.3f}, {new_y:.3f}, {new_w:.3f}, {new_h:.3f})"
        )

  return extended


def find_box_size_reduction(
  domain: Rect,
  free_rects: List[Rect],
  placed_clusters: List[PlacedCluster],
  inner_wall_thickness: float,
  eps: float = 1e-9
) -> Tuple[Optional[float], Optional[float]]:
  max_x = domain.x + domain.w
  max_y = domain.y + domain.h

  used_max_x = domain.x
  used_max_y = domain.y
  for cluster in placed_clusters:
    used_max_x = max(used_max_x, cluster.x + cluster.w)
    used_max_y = max(used_max_y, cluster.y + cluster.h)

  # Keep the same right/top edge margin that the packing domain uses.
  required_max_x = min(max_x, used_max_x + inner_wall_thickness / 2.0)
  required_max_y = min(max_y, used_max_y + inner_wall_thickness / 2.0)

  footprint_reduce_length = max(0.0, max_x - required_max_x)
  footprint_reduce_width = max(0.0, max_y - required_max_y)

  reduce_length: Optional[float] = None
  reduce_width: Optional[float] = None

  for free_rect in free_rects:
    spans_width = free_rect.y <= domain.y + eps and free_rect.y + free_rect.h >= max_y - eps
    spans_length = free_rect.x <= domain.x + eps and free_rect.x + free_rect.w >= max_x - eps
    touches_right = free_rect.x + free_rect.w >= max_x - eps
    touches_top = free_rect.y + free_rect.h >= max_y - eps

    if spans_width and touches_right and free_rect.w > eps:
      reduce_length = free_rect.w if reduce_length is None else max(reduce_length, free_rect.w)

    if spans_length and touches_top and free_rect.h > eps:
      reduce_width = free_rect.h if reduce_width is None else max(reduce_width, free_rect.h)

  if footprint_reduce_length > eps:
    reduce_length = footprint_reduce_length if reduce_length is None else max(reduce_length, footprint_reduce_length)

  if footprint_reduce_width > eps:
    reduce_width = footprint_reduce_width if reduce_width is None else max(reduce_width, footprint_reduce_width)

  return reduce_length, reduce_width


def clip_free_rects_to_domain(free_rects: List[Rect], domain: Rect) -> List[Rect]:
  clipped: List[Rect] = []

  for free_rect in free_rects:
    clipped_rect = clip_rect_to_domain(free_rect, domain)
    if clipped_rect is not None:
      clipped.append(clipped_rect)

  return normalize_free_rects(clipped)


def split_free_rects_into_cells(
  free_rects: List[Rect],
  cell_w: float,
  cell_h: float,
  inner_wall_thickness: float,
  eps: float = 1e-9
) -> List[Rect]:
  cells: List[Rect] = []
  step_x = cell_w + inner_wall_thickness
  step_y = cell_h + inner_wall_thickness

  if step_x <= eps or step_y <= eps:
    return free_rects

  for free_rect in free_rects:
    columns = 0
    rows = 0

    x = free_rect.x
    while x + cell_w <= free_rect.x + free_rect.w + eps:
      columns += 1
      x += step_x

    y = free_rect.y
    while y + cell_h <= free_rect.y + free_rect.h + eps:
      rows += 1
      y += step_y

    if columns == 0 or rows == 0:
      cells.append(free_rect)
      continue

    for row_index in range(rows):
      y = free_rect.y + row_index * step_y
      for column_index in range(columns):
        x = free_rect.x + column_index * step_x
        cells.append(Rect(x, y, cell_w, cell_h))

    remainder_x = free_rect.x + columns * step_x
    remainder_y = free_rect.y + rows * step_y
    right_remainder_w = (free_rect.x + free_rect.w) - remainder_x
    bottom_remainder_h = (free_rect.y + free_rect.h) - remainder_y

    if right_remainder_w > eps:
      for row_index in range(rows):
        y = free_rect.y + row_index * step_y
        cells.append(Rect(remainder_x, y, right_remainder_w, cell_h))

    if bottom_remainder_h > eps:
      for column_index in range(columns):
        x = free_rect.x + column_index * step_x
        cells.append(Rect(x, remainder_y, cell_w, bottom_remainder_h))

    if right_remainder_w > eps and bottom_remainder_h > eps:
      cells.append(Rect(remainder_x, remainder_y, right_remainder_w, bottom_remainder_h))

  if not cells:
    return free_rects

  return [rect for rect in cells if rect.w > eps and rect.h > eps]


PIXEL_FONT: dict[str, List[str]] = {
  "0": [
    "111",
    "101",
    "101",
    "101",
    "111"
  ],
  "1": [
    "010",
    "110",
    "010",
    "010",
    "111"
  ],
  "2": [
    "111",
    "001",
    "111",
    "100",
    "111"
  ],
  "3": [
    "111",
    "001",
    "111",
    "001",
    "111"
  ],
  "4": [
    "101",
    "101",
    "111",
    "001",
    "001"
  ],
  "5": [
    "111",
    "100",
    "111",
    "001",
    "111"
  ],
  "6": [
    "111",
    "100",
    "111",
    "101",
    "111"
  ],
  "7": [
    "111",
    "001",
    "001",
    "001",
    "001"
  ],
  "8": [
    "111",
    "101",
    "111",
    "101",
    "111"
  ],
  "9": [
    "111",
    "101",
    "111",
    "001",
    "111"
  ],
  "x": [
    "101",
    "101",
    "010",
    "101",
    "101"
  ],
  ".": [
    "0",
    "0",
    "0",
    "0",
    "1"
  ]
}


def format_compartment_size_label(width: float, height: float) -> str:
  return f"{width:g}x{height:g}"


def get_text_pixel_dimensions(text: str) -> Tuple[int, int]:
  if not text:
    return 0, 0

  width_units = 0
  for index, char in enumerate(text):
    pattern = PIXEL_FONT.get(char)
    if pattern is None:
      continue

    width_units += len(pattern[0])
    if index < len(text) - 1:
      width_units += 1

  return width_units, 5


def build_compartment_label_boxes(
  cavities: List[Rect],
  bottom_thickness: float
) -> List[SolidBox]:
  boxes: List[SolidBox] = []

  for cavity in cavities:
    label_text = format_compartment_size_label(cavity.w, cavity.h)
    text_units_w, text_units_h = get_text_pixel_dimensions(label_text)

    if text_units_w <= 0 or text_units_h <= 0:
      continue

    margin = max(0.6, min(cavity.w, cavity.h) * 0.08)
    available_w = cavity.w - 2.0 * margin
    available_h = cavity.h - 2.0 * margin

    if available_w <= 0 or available_h <= 0:
      continue

    pixel_size = min(available_w / text_units_w, available_h / text_units_h)
    if pixel_size < 0.8:
      continue

    gap_size = pixel_size
    text_w = text_units_w * pixel_size
    text_h = text_units_h * pixel_size
    start_x = cavity.x + (cavity.w - text_w) / 2.0
    start_y = cavity.y + (cavity.h - text_h) / 2.0
    cursor_x = start_x
    label_height = min(0.8, max(0.4, bottom_thickness * 0.35))

    for char_index, char in enumerate(label_text):
      pattern = PIXEL_FONT.get(char)
      if pattern is None:
        continue

      pattern_w = len(pattern[0])
      for row_index, row in enumerate(pattern):
        for col_index, cell in enumerate(row):
          if cell != "1":
            continue

          boxes.append(
            SolidBox(
              x=cursor_x + col_index * pixel_size,
              y=start_y + (text_units_h - row_index - 1) * pixel_size,
              z=bottom_thickness,
              w=pixel_size,
              h=pixel_size,
              d=label_height
            )
          )

      cursor_x += pattern_w * pixel_size
      if char_index < len(label_text) - 1:
        cursor_x += gap_size

  return boxes


# ------------------------------------------------------------
# OpenSCAD generation
# ------------------------------------------------------------

def make_scad(
  inner_length: float,
  inner_width: float,
  inner_height: float,
  inner_wall_height: float,
  outer_wall_thickness: float,
  inner_wall_thickness: float,
  bottom_thickness: float,
  outer_corner_radius: float,
  placed_clusters: List[PlacedCluster],
  requested_cavities: List[Rect],
  free_cavities: List[Rect],
  wall_rects: List[Rect],
  label_boxes: List[SolidBox]
) -> str:
  outer_length = inner_length + 2.0 * outer_wall_thickness
  outer_width = inner_width + 2.0 * outer_wall_thickness
  outer_height = inner_height + bottom_thickness

  safe_corner_radius = max(
    0.0,
    min(
      outer_corner_radius,
      outer_length / 2.0 - 0.001,
      outer_width / 2.0 - 0.001
    )
  )

  lines: List[str] = []

  lines.append("// Generated by Python")
  lines.append("// The requested box dimensions are the inner dimensions in mm")
  lines.append("// All cavity rectangles are subtracted from a rounded outer shell")
  lines.append("")

  lines.append(f"innerLength = {inner_length:.3f};")
  lines.append(f"innerWidth = {inner_width:.3f};")
  lines.append(f"innerHeight = {inner_height:.3f};")
  lines.append(f"innerWallHeight = {inner_wall_height:.3f};")
  lines.append(f"outerWallThickness = {outer_wall_thickness:.3f};")
  lines.append(f"innerWallThickness = {inner_wall_thickness:.3f};")
  lines.append(f"bottomThickness = {bottom_thickness:.3f};")
  lines.append(f"outerCornerRadius = {safe_corner_radius:.3f};")
  lines.append("")
  lines.append(f"outerLength = {outer_length:.3f};")
  lines.append(f"outerWidth = {outer_width:.3f};")
  lines.append(f"outerHeight = {outer_height:.3f};")
  lines.append("")
  lines.append("$fn = 64;")
  lines.append("")

  lines.append("// Cluster groups")
  for cluster in placed_clusters:
    lines.append(
      f"// {cluster.label}: x={cluster.x:.3f}, y={cluster.y:.3f}, "
      f"footprint={cluster.w:.3f}x{cluster.h:.3f}, "
      f"cells={cluster.cells}, orientation={cluster.orientation}"
    )

  lines.append("")
  lines.append("// Requested cavities")
  for index, cavity in enumerate(requested_cavities, start=1):
    lines.append(
      f"// requested_{index}: x={cavity.x:.3f}, y={cavity.y:.3f}, "
      f"size={cavity.w:.3f}x{cavity.h:.3f}"
    )

  lines.append("")
  lines.append("// Remaining free cavities")
  for index, cavity in enumerate(free_cavities, start=1):
    lines.append(
      f"// free_{index}: x={cavity.x:.3f}, y={cavity.y:.3f}, "
      f"size={cavity.w:.3f}x{cavity.h:.3f}"
    )

  lines.append("")
  lines.append("// Internal wall rectangles")
  for index, wall_rect in enumerate(wall_rects, start=1):
    lines.append(
      f"// wall_{index}: x={wall_rect.x:.3f}, y={wall_rect.y:.3f}, "
      f"size={wall_rect.w:.3f}x{wall_rect.h:.3f}"
    )

  lines.append("")
  lines.append("// Raised size labels")
  for index, label_box in enumerate(label_boxes, start=1):
    lines.append(
      f"// label_{index}: x={label_box.x:.3f}, y={label_box.y:.3f}, z={label_box.z:.3f}, "
      f"size={label_box.w:.3f}x{label_box.h:.3f}x{label_box.d:.3f}"
    )

  lines.append("")
  lines.append("module roundedRect2d(length, width, radius)")
  lines.append("{")
  lines.append("  if (radius <= 0)")
  lines.append("  {")
  lines.append("    square([length, width]);")
  lines.append("  }")
  lines.append("  else")
  lines.append("  {")
  lines.append("    translate([radius, radius])")
  lines.append("      offset(r = radius)")
  lines.append("        square([length - 2 * radius, width - 2 * radius]);")
  lines.append("  }")
  lines.append("}")
  lines.append("")

  lines.append("module outerSolid()")
  lines.append("{")
  lines.append("  linear_extrude(height = outerHeight)")
  lines.append("    roundedRect2d(outerLength, outerWidth, outerCornerRadius);")
  lines.append("}")
  lines.append("")

  lines.append("module mainCavity()")
  lines.append("{")
  lines.append("  innerRadius = outerCornerRadius - outerWallThickness;")
  lines.append("  translate([outerWallThickness, outerWallThickness, bottomThickness])")
  lines.append("    linear_extrude(height = innerHeight + 1)")
  lines.append("      roundedRect2d(innerLength, innerWidth, innerRadius);")
  lines.append("}")
  lines.append("")

  lines.append("module wall(x, y, w, h)")
  lines.append("{")
  lines.append("  translate([outerWallThickness + x, outerWallThickness + y, bottomThickness / 2])")
  lines.append("    cube([w, h, innerWallHeight]);")
  lines.append("}")
  lines.append("")

  lines.append("module labelBlock(x, y, z, w, h, d)")
  lines.append("{")
  lines.append("  translate([outerWallThickness + x, outerWallThickness + y, z])")
  lines.append("    cube([w, h, d]);")
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
  for wall_rect in wall_rects:
    lines.append(
      f"      wall({wall_rect.x:.3f}, {wall_rect.y:.3f}, {wall_rect.w:.3f}, {wall_rect.h:.3f});"
    )
  for label_box in label_boxes:
    lines.append(
      f"      labelBlock({label_box.x:.3f}, {label_box.y:.3f}, {label_box.z:.3f}, "
      f"{label_box.w:.3f}, {label_box.h:.3f}, {label_box.d:.3f});"
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
  inner_length: float,
  inner_width: float,
  inner_height: float,
  inner_wall_height: float,
  outer_wall_thickness: float,
  bottom_thickness: float,
  wall_rects: List[Rect],
  label_boxes: List[SolidBox]
) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
  triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []

  outer_length = inner_length + 2.0 * outer_wall_thickness
  outer_width = inner_width + 2.0 * outer_wall_thickness
  outer_height = inner_height + bottom_thickness

  append_box_triangles(triangles, 0.0, 0.0, 0.0, outer_length, outer_width, bottom_thickness)
  append_box_triangles(triangles, 0.0, 0.0, bottom_thickness, outer_length, outer_wall_thickness, outer_height)
  append_box_triangles(
    triangles,
    0.0,
    outer_width - outer_wall_thickness,
    bottom_thickness,
    outer_length,
    outer_width,
    outer_height
  )
  append_box_triangles(
    triangles,
    0.0,
    outer_wall_thickness,
    bottom_thickness,
    outer_wall_thickness,
    outer_width - outer_wall_thickness,
    outer_height
  )
  append_box_triangles(
    triangles,
    outer_length - outer_wall_thickness,
    outer_wall_thickness,
    bottom_thickness,
    outer_length,
    outer_width - outer_wall_thickness,
    outer_height
  )

  wall_z0 = bottom_thickness / 2.0
  wall_z1 = wall_z0 + inner_wall_height

  for wall_rect in wall_rects:
    append_box_triangles(
      triangles,
      outer_wall_thickness + wall_rect.x,
      outer_wall_thickness + wall_rect.y,
      wall_z0,
      outer_wall_thickness + wall_rect.x + wall_rect.w,
      outer_wall_thickness + wall_rect.y + wall_rect.h,
      wall_z1
    )

  for label_box in label_boxes:
    append_box_triangles(
      triangles,
      outer_wall_thickness + label_box.x,
      outer_wall_thickness + label_box.y,
      label_box.z,
      outer_wall_thickness + label_box.x + label_box.w,
      outer_wall_thickness + label_box.y + label_box.h,
      label_box.z + label_box.d
    )

  return triangles


def write_ascii_stl(
  stl_path: Path,
  triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]
) -> None:
  with stl_path.open("w", encoding="utf-8") as handle:
    solid_name = stl_path.stem
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


def export_stl(
  stl_path: Path,
  inner_length: float,
  inner_width: float,
  inner_height: float,
  inner_wall_height: float,
  outer_wall_thickness: float,
  bottom_thickness: float,
  outer_corner_radius: float,
  wall_rects: List[Rect],
  label_boxes: List[SolidBox]
) -> str:
  # STL export is intentionally self-contained: no OpenSCAD dependency,
  # no external Python packages, and no separate virtual environment setup.
  triangles = build_stl_triangles(
    inner_length=inner_length,
    inner_width=inner_width,
    inner_height=inner_height,
    inner_wall_height=inner_wall_height,
    outer_wall_thickness=outer_wall_thickness,
    bottom_thickness=bottom_thickness,
    wall_rects=wall_rects,
    label_boxes=label_boxes
  )
  write_ascii_stl(stl_path, triangles)

  if outer_corner_radius > 0:
    return "builtin-rectangular"

  return "builtin"


# ------------------------------------------------------------
# Reporting
# ------------------------------------------------------------

def print_cluster_summary(placed_clusters: List[PlacedCluster]) -> None:
  print("")
  print("Placed cluster groups:")

  for cluster in placed_clusters:
    print(
      f"  {cluster.label:14s} "
      f"position=({cluster.x:.1f}, {cluster.y:.1f}) "
      f"footprint={cluster.w:.1f}x{cluster.h:.1f} "
      f"cells={cluster.cells} "
      f"orientation={cluster.orientation} "
      f"pref={cluster.placement_mode}/{cluster.lateral_mode}"
    )


def print_cavity_summary(requested_cavities: List[Rect], free_cavities: List[Rect]) -> None:
  print("")
  print("Requested cavities:")

  for index, cavity in enumerate(requested_cavities, start=1):
    print(
      f"  requested_{index:02d} "
      f"position=({cavity.x:.1f}, {cavity.y:.1f}) "
      f"size={cavity.w:.1f}x{cavity.h:.1f}"
    )

  print("")
  print("Remaining free cavities:")

  if not free_cavities:
    print("  None")
  else:
    for index, cavity in enumerate(free_cavities, start=1):
      print(
        f"  free_{index:02d} "
        f"position=({cavity.x:.1f}, {cavity.y:.1f}) "
        f"size={cavity.w:.1f}x{cavity.h:.1f}"
      )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
  print("OpenSCAD box generator")
  print("----------------------")

  project_name = select_project()
  defaults_path = Path(f".boxGenerator.{project_name}.json")
  print(f"Project: {project_name}")
  print("")

  if "--erase" in sys.argv or "--empty" in sys.argv:
    if defaults_path.exists():
      try:
        defaults_path.unlink()
        print("Stored defaults erased.")
      except OSError:
        print("Warning: could not erase stored defaults.")
    else:
      print("No stored defaults found to erase.")

  defaults = load_defaults(defaults_path)

  inner_length, inner_width, inner_height = ask_box_dimensions(
    (defaults.inner_length, defaults.inner_width, defaults.inner_height)
  )
  inner_wall_height_default = defaults.inner_wall_height if defaults.inner_wall_height is not None else inner_height
  inner_wall_height = ask_float("Enter inner wall height in mm", inner_wall_height_default, allow_zero=False)
  if inner_wall_height > inner_height:
    print("Warning: inner wall height is larger than inner box height. It will be capped.")
    inner_wall_height = inner_height

  outer_wall_thickness = ask_float("Enter outer wall thickness in mm", defaults.outer_wall_thickness, allow_zero=False)
  inner_wall_thickness = ask_float("Enter inner divider thickness in mm", defaults.inner_wall_thickness, allow_zero=False)
  bottom_thickness = ask_float("Enter bottom thickness in mm", defaults.bottom_thickness, allow_zero=False)
  outer_corner_radius = ask_float("Enter outer corner radius in mm", defaults.outer_corner_radius, allow_zero=True)

  free_cell_default: Optional[Tuple[float, float]] = None
  if defaults.free_cell_w is not None and defaults.free_cell_h is not None:
    free_cell_default = (defaults.free_cell_w, defaults.free_cell_h)
  free_cell_size = ask_optional_size_2d_with_default("Enter leftover compartment size", free_cell_default)

  rng_seed = ask_int("Enter random seed", defaults.rng_seed, 1)
  layout_attempts = ask_int("Enter number of layout attempts", defaults.layout_attempts, 1)
  per_item_attempts = ask_int("Enter number of attempts per cluster group", defaults.per_item_attempts, 1)

  items, compartment_specs = ask_cluster_items(defaults.compartments)

  defaults.inner_length = inner_length
  defaults.inner_width = inner_width
  defaults.inner_height = inner_height
  defaults.inner_wall_height = inner_wall_height
  defaults.outer_wall_thickness = outer_wall_thickness
  defaults.inner_wall_thickness = inner_wall_thickness
  defaults.bottom_thickness = bottom_thickness
  defaults.outer_corner_radius = outer_corner_radius
  defaults.rng_seed = rng_seed
  defaults.layout_attempts = layout_attempts
  defaults.per_item_attempts = per_item_attempts
  defaults.free_cell_w = free_cell_size[0] if free_cell_size is not None else None
  defaults.free_cell_h = free_cell_size[1] if free_cell_size is not None else None
  defaults.compartments = compartment_specs
  save_defaults(defaults, defaults_path)

  if not items:
    print("Warning: No compartment definitions were entered. Program will stop.")
    return

  total_requested_area = sum(item.cell_w * item.cell_h * item.cells for item in items)
  inner_box_area = inner_length * inner_width

  if total_requested_area > inner_box_area:
    excess_area = total_requested_area - inner_box_area
    print("")
    print("Error: The total requested compartment area is larger than the inner box floor area.")
    print(f"Requested compartment area: {total_requested_area:.1f} mm2")
    print(f"Inner box floor area:      {inner_box_area:.1f} mm2")
    print_area_reduction_suggestions(compartment_specs, excess_area)
    return

  try:
    placed_clusters, free_rects, domain, missing_items = pack_clusters_random(
      inner_length=inner_length,
      inner_width=inner_width,
      inner_wall_thickness=inner_wall_thickness,
      items=items,
      rng_seed=rng_seed,
      layout_attempts=layout_attempts,
      per_item_attempts=per_item_attempts,
      show_progress=True
    )
  except RuntimeError as exc:
    print("")
    print(f"Error: {exc}")
    print("Hint: Increase the box size, reduce the number of compartments, or increase the attempt counts.")
    return

  if missing_items:
    print_missing_group_suggestions(compartment_specs, missing_items)
    return

  reduce_length, reduce_width = find_box_size_reduction(
    domain,
    free_rects,
    placed_clusters,
    inner_wall_thickness
  )
  resize_applied = False

  if reduce_length is not None:
    proposed_length = inner_length - reduce_length
    if proposed_length > inner_wall_thickness and ask_yes_no(
      f"Unused strip over full box width detected. Shrink box length from {inner_length:g} to {proposed_length:g}? modifyBoxSize",
      False
    ):
      inner_length = proposed_length
      resize_applied = True

  if reduce_width is not None:
    proposed_width = inner_width - reduce_width
    if proposed_width > inner_wall_thickness and ask_yes_no(
      f"Unused strip over full box length detected. Shrink box width from {inner_width:g} to {proposed_width:g}? modifyBoxSize",
      False
    ):
      inner_width = proposed_width
      resize_applied = True

  if resize_applied:
    edge_margin = inner_wall_thickness / 2.0
    domain = Rect(
      edge_margin,
      edge_margin,
      inner_length - inner_wall_thickness,
      inner_width - inner_wall_thickness
    )
    free_rects = clip_free_rects_to_domain(free_rects, domain)

  requested_cavities, free_cavities = build_all_cavities(
    placed_clusters=placed_clusters,
    free_rects=free_rects,
    inner_wall_thickness=inner_wall_thickness,
    free_cell_size=free_cell_size
  )
  wall_cavities = to_centerline_cavities(
    requested_cavities + free_cavities,
    inner_wall_thickness
  )
  wall_domain = Rect(0.0, 0.0, inner_length, inner_width)
  wall_rects = build_wall_rects(wall_domain, wall_cavities)
  wall_rects = ensure_cavity_closure(
    wall_domain,
    wall_cavities,
    wall_rects,
    inner_wall_thickness
  )

  label_boxes = build_compartment_label_boxes(requested_cavities + free_cavities, bottom_thickness)

  scad_text = make_scad(
    inner_length=inner_length,
    inner_width=inner_width,
    inner_height=inner_height,
    inner_wall_height=inner_wall_height,
    outer_wall_thickness=outer_wall_thickness,
    inner_wall_thickness=inner_wall_thickness,
    bottom_thickness=bottom_thickness,
    outer_corner_radius=outer_corner_radius,
    placed_clusters=placed_clusters,
    requested_cavities=requested_cavities,
    free_cavities=free_cavities,
    wall_rects=wall_rects,
    label_boxes=label_boxes
  )

  output_path = Path(f"{project_name}_box.scad")

  with output_path.open("w", encoding="utf-8") as handle:
    handle.write(scad_text)

  stl_path = Path(f"{project_name}_box.stl")
  stl_export_method = export_stl(
    stl_path=stl_path,
    inner_length=inner_length,
    inner_width=inner_width,
    inner_height=inner_height,
    inner_wall_height=inner_wall_height,
    outer_wall_thickness=outer_wall_thickness,
    bottom_thickness=bottom_thickness,
    outer_corner_radius=outer_corner_radius,
    wall_rects=wall_rects,
    label_boxes=label_boxes
  )

  print_cluster_summary(placed_clusters)
  print_cavity_summary(requested_cavities, free_cavities)

  print("")
  print(f"OpenSCAD file written: {output_path}")
  print(f"STL file written: {stl_path}")
  if stl_export_method == "builtin-rectangular":
    print("STL export was generated internally. Rounded outer corners remain exact only in the SCAD file.")
  else:
    print("STL export was generated internally.")
  print(f"Random seed used: {rng_seed}")


if __name__ == "__main__":
  main()
  