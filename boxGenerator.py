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
class LabelGlyph:
  compartment_number: int
  text: str
  boxes: List[SolidBox]


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
  requested_cell_w: float
  requested_cell_h: float
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
  outer_length: float = 304.0
  outer_width: float = 204.0
  outer_height: float = 80.0
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


@dataclass
class GapAdjustment:
  axis: str
  first_cavity_index: int
  second_cavity_index: int
  gap_size: float
  first_growth: float
  second_growth: float


@dataclass
class CompartmentPlacement:
  number: int
  x: float
  y: float
  w: float
  h: float
  requested_w: float
  requested_h: float
  is_free: bool


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
    outer_length=float(raw.get("outer_length", raw.get("inner_length", 304.0))),
    outer_width=float(raw.get("outer_width", raw.get("inner_width", 204.0))),
    outer_height=float(raw.get("outer_height", raw.get("inner_height", 80.0))),
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
    "outer_length": defaults.outer_length,
    "outer_width": defaults.outer_width,
    "outer_height": defaults.outer_height,
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
      "Enter outer box size (length x width x height, "
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


def format_missing_compartment_indices(items: List[ClusterItem]) -> str:
  indices = sorted({compartment_index_from_label(item.label) for item in items if compartment_index_from_label(item.label) is not None})
  if not indices:
    return "none"
  return ",".join(str(index) for index in indices)


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
) -> List[Tuple[str, float, float, float, float, float, float]]:
  _ = inner_wall_thickness
  shrink_factors = [1.0, 0.95, 0.90]
  options: List[Tuple[str, float, float, float, float, float, float]] = []
  seen: set[Tuple[str, int, int, int, int, int, int]] = set()

  base_variants = [
    (item.cell_w, item.cell_h),
    (item.cell_h, item.cell_w)
  ]

  for base_w, base_h in base_variants:
    for shrink_x in shrink_factors:
      for shrink_y in shrink_factors:
        cell_w = round(base_w * shrink_x, 6)
        cell_h = round(base_h * shrink_y, 6)
        if cell_w <= 0 or cell_h <= 0:
          continue

        if item.cells <= 1:
          entry = ("single", cell_w, cell_h, cell_w, cell_h, base_w, base_h)
          key = (
            entry[0],
            int(round(entry[1] * 1000)),
            int(round(entry[2] * 1000)),
            int(round(entry[3] * 1000)),
            int(round(entry[4] * 1000)),
            int(round(entry[5] * 1000)),
            int(round(entry[6] * 1000))
          )
          if key not in seen:
            options.append(entry)
            seen.add(key)
          continue

        horizontal = ("horizontal", item.cells * cell_w, cell_h, cell_w, cell_h, base_w, base_h)
        vertical = ("vertical", cell_w, item.cells * cell_h, cell_w, cell_h, base_w, base_h)

        for entry in (horizontal, vertical):
          key = (
            entry[0],
            int(round(entry[1] * 1000)),
            int(round(entry[2] * 1000)),
            int(round(entry[3] * 1000)),
            int(round(entry[4] * 1000)),
            int(round(entry[5] * 1000)),
            int(round(entry[6] * 1000))
          )
          if key not in seen:
            options.append(entry)
            seen.add(key)

  return options


def cluster_sort_key(item: ClusterItem, inner_wall_thickness: float) -> Tuple[float, float, float]:
  footprints = get_cluster_footprints(item, inner_wall_thickness)
  max_area = max(width * height for _, width, height, _, _, _, _ in footprints)
  max_side = max(max(width, height) for _, width, height, _, _, _, _ in footprints)
  min_side = max(min(width, height) for _, width, height, _, _, _, _ in footprints)

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
  domain: Rect,
  grid_step: float,
  eps: float = 1e-9
) -> Tuple[float, float]:
  def snap_to_grid(value: float, origin: float, step: float) -> float:
    if step <= eps:
      return value
    snapped = origin + round((value - origin) / step) * step
    # Avoid tiny floating artifacts in downstream subtraction.
    return round(snapped, 6)

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
    x = min(max(snap_to_grid(x, domain.x, grid_step), min_x), max_x)
    y = min(max(snap_to_grid(y, domain.y, grid_step), min_y), max_y)

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
  x = space.x + offset_x
  y = space.y + offset_y
  min_x = space.x
  max_x = space.x + dx
  min_y = space.y
  max_y = space.y + dy
  x = min(max(snap_to_grid(x, domain.x, grid_step), min_x), max_x)
  y = min(max(snap_to_grid(y, domain.y, grid_step), min_y), max_y)

  return x, y


def try_place_cluster(
  free_rects: List[Rect],
  item: ClusterItem,
  rng: random.Random,
  per_item_attempts: int,
  separator_thickness: float,
  domain: Rect
) -> Optional[Tuple[PlacedCluster, List[Rect]]]:
  all_footprints = get_cluster_footprints(item, separator_thickness)
  exact_footprints: List[Tuple[str, float, float, float, float, float, float]] = []
  shrunk_footprints: List[Tuple[str, float, float, float, float, float, float]] = []

  for footprint in all_footprints:
    _, _, _, cell_w, cell_h, requested_w, requested_h = footprint
    if abs(cell_w - requested_w) <= 1e-9 and abs(cell_h - requested_h) <= 1e-9:
      exact_footprints.append(footprint)
    else:
      shrunk_footprints.append(footprint)

  footprint_passes = [exact_footprints]
  if shrunk_footprints:
    footprint_passes.append(shrunk_footprints)

  for footprint_pool in footprint_passes:
    if not footprint_pool:
      continue

    candidates: List[Tuple[PlacedCluster, List[Rect], int]] = []

    for _ in range(per_item_attempts):
      shuffled_spaces = free_rects[:]
      rng.shuffle(shuffled_spaces)

      for space in shuffled_spaces:
        shuffled_footprints = footprint_pool[:]
        rng.shuffle(shuffled_footprints)

        for orientation, footprint_w, footprint_h, cell_w, cell_h, requested_w, requested_h in shuffled_footprints:
          if footprint_w > space.w or footprint_h > space.h:
            continue

          pos_x, pos_y = choose_anchor_position(
            space,
            footprint_w,
            footprint_h,
            rng,
            item,
            domain,
            separator_thickness
          )

          placed = PlacedCluster(
            x=pos_x,
            y=pos_y,
            w=footprint_w,
            h=footprint_h,
            cell_w=cell_w,
            cell_h=cell_h,
            requested_cell_w=requested_w,
            requested_cell_h=requested_h,
            cells=item.cells,
            orientation=orientation,
            label=item.label,
            placement_mode=item.placement_mode,
            lateral_mode=item.lateral_mode
          )

          blocked = Rect(
              placed.x,
              placed.y,
              placed.w,
              placed.h
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

    if candidates:
      candidates.sort(key=lambda entry: entry[2])
      best_band = candidates[:max(1, min(8, len(candidates)))]
      chosen_placed, chosen_free, _ = rng.choice(best_band)
      return chosen_placed, chosen_free

  return None


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
  _ = inner_wall_thickness
  domain = Rect(0.0, 0.0, inner_length, inner_width)

  if domain.w <= 0 or domain.h <= 0:
    raise RuntimeError("Inner box size is too small for the requested inner wall thickness.")

  items_sorted = sorted(
    items,
    key=lambda item: cluster_sort_key(item, inner_wall_thickness),
    reverse=True
  )
  total_cells = sum(item.cells for item in items_sorted)

  def layout_score(
    placed: List[PlacedCluster],
    free: List[Rect],
    attempt: int,
    eps: float = 1e-9
  ) -> Tuple[int, float, int, float, int]:
    shrink_axis_count = 0
    shrink_ratio_total = 0.0

    for cluster in placed:
      if cluster.cell_w + eps < cluster.requested_cell_w:
        shrink_axis_count += 1
        shrink_ratio_total += (cluster.requested_cell_w - cluster.cell_w) / cluster.requested_cell_w
      if cluster.cell_h + eps < cluster.requested_cell_h:
        shrink_axis_count += 1
        shrink_ratio_total += (cluster.requested_cell_h - cluster.cell_h) / cluster.requested_cell_h

    return (
      shrink_axis_count,
      shrink_ratio_total,
      len(free),
      sum(rect_area(rect) for rect in free),
      attempt
    )

  best_result: Optional[Tuple[List[PlacedCluster], List[Rect], int, int]] = None
  best_no_shrink_result: Optional[Tuple[List[PlacedCluster], List[Rect], int, int]] = None
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
      placed_count += item.cells

    free_rects = normalize_free_rects(free_rects)
    current_missing_items = [item for item in items_sorted if item.label not in {cluster.label for cluster in placed_clusters}]

    if success:
      score = layout_score(placed_clusters, free_rects, attempt_index)

      if score[0] == 0:
        if best_no_shrink_result is None:
          best_no_shrink_result = (placed_clusters, free_rects, placed_count, attempt_index)
        else:
          best_no_shrink_score = layout_score(
            best_no_shrink_result[0],
            best_no_shrink_result[1],
            best_no_shrink_result[3]
          )
          if score < best_no_shrink_score:
            best_no_shrink_result = (placed_clusters, free_rects, placed_count, attempt_index)

      if best_result is None:
        best_result = (placed_clusters, free_rects, placed_count, attempt_index)
      else:
        current_score = layout_score(best_result[0], best_result[1], best_result[3])

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
        f"best placed compartments {current_best}/{total_cells}, "
        f"current missing compartments {format_missing_compartment_indices(current_missing_items)}"
      )

  if best_result is None:
    raise RuntimeError("No valid layout could be generated.")

  if best_no_shrink_result is not None:
    best_result = best_no_shrink_result

  placed_clusters, free_rects, placed_count, _ = best_result
  placed_labels = {cluster.label for cluster in placed_clusters}
  missing_items = [item for item in items_sorted if item.label not in placed_labels]

  return placed_clusters, free_rects, domain, missing_items


# ------------------------------------------------------------
# Cavity generation
# ------------------------------------------------------------

def cluster_to_cavities(cluster: PlacedCluster, inner_wall_thickness: float) -> List[Rect]:
  cavities: List[Rect] = []
  _ = inner_wall_thickness

  if cluster.cells == 1:
    cavities.append(Rect(cluster.x, cluster.y, cluster.cell_w, cluster.cell_h))
    return cavities

  if cluster.orientation == "horizontal":
    for index in range(cluster.cells):
      cavity_x = cluster.x + index * cluster.cell_w
      cavity_y = cluster.y

      cavities.append(
        Rect(cavity_x, cavity_y, cluster.cell_w, cluster.cell_h)
      )

    return cavities

  if cluster.orientation == "vertical":
    for index in range(cluster.cells):
      cavity_x = cluster.x
      cavity_y = cluster.y + index * cluster.cell_h

      cavities.append(
        Rect(cavity_x, cavity_y, cluster.cell_w, cluster.cell_h)
      )

    return cavities

  cavities.append(Rect(cluster.x, cluster.y, cluster.cell_w, cluster.cell_h))
  return cavities


def overlap_length(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
  return min(end_a, end_b) - max(start_a, start_b)


def spans_overlap_or_touch(start_a: float, end_a: float, start_b: float, end_b: float, eps: float = 1e-9) -> bool:
  return overlap_length(start_a, end_a, start_b, end_b) > eps or (
    abs(end_a - start_b) <= eps or
    abs(end_b - start_a) <= eps
  )


def distribute_growth_between_neighbors(
  total_growth: float,
  first_limit: float,
  second_limit: float,
  eps: float = 1e-9
) -> Optional[Tuple[float, float]]:
  if total_growth <= eps:
    return (0.0, 0.0)

  first_growth = min(first_limit, total_growth / 2.0)
  second_growth = min(second_limit, total_growth / 2.0)
  remaining = total_growth - first_growth - second_growth

  if remaining > eps:
    extra_first = min(first_limit - first_growth, remaining)
    first_growth += extra_first
    remaining -= extra_first

  if remaining > eps:
    extra_second = min(second_limit - second_growth, remaining)
    second_growth += extra_second
    remaining -= extra_second

  if remaining > eps:
    return None

  return (first_growth, second_growth)


def distribute_growth_preferring_smaller(
  total_growth: float,
  first_limit: float,
  second_limit: float,
  first_rect: Rect,
  second_rect: Rect,
  eps: float = 1e-9
) -> Optional[Tuple[float, float]]:
  first_area = rect_area(first_rect)
  second_area = rect_area(second_rect)

  if first_area <= second_area:
    first_growth = min(first_limit, total_growth)
    second_growth = min(second_limit, total_growth - first_growth)
  else:
    second_growth = min(second_limit, total_growth)
    first_growth = min(first_limit, total_growth - second_growth)

  remaining = total_growth - first_growth - second_growth
  if remaining > eps:
    return distribute_growth_between_neighbors(total_growth, first_limit, second_limit, eps)

  return (first_growth, second_growth)


def should_consume_gap_for_fill(
  gap_size: float,
  fill_requirement: Optional[float],
  eps: float = 1e-9
) -> bool:
  if gap_size <= eps:
    return False

  if fill_requirement is None:
    return True

  return gap_size + eps < fill_requirement


def has_substantial_overlap(span_a: float, span_b: float, overlap: float, eps: float = 1e-9) -> bool:
  return overlap + eps >= min(span_a, span_b)


def adjust_requested_cavities_for_small_gaps(
  requested_cavities: List[Rect],
  free_rects: List[Rect],
  inner_wall_thickness: float,
  eps: float = 1e-9
) -> Tuple[List[Rect], List[Rect], List[GapAdjustment]]:
  adjusted_cavities = [Rect(cavity.x, cavity.y, cavity.w, cavity.h) for cavity in requested_cavities]
  remaining_free: List[Rect] = []
  adjustments: List[GapAdjustment] = []

  def overlaps_other_cavity(candidate: Rect, skip_indices: set[int]) -> bool:
    for other_index, other in enumerate(adjusted_cavities):
      if other_index in skip_indices:
        continue
      overlap_x = overlap_length(candidate.x, candidate.x + candidate.w, other.x, other.x + other.w)
      overlap_y = overlap_length(candidate.y, candidate.y + candidate.h, other.y, other.y + other.h)
      if overlap_x > eps and overlap_y > eps:
        return True
    return False

  for free_rect in sorted(free_rects, key=rect_area):
    left_index: Optional[int] = None
    right_index: Optional[int] = None
    bottom_index: Optional[int] = None
    top_index: Optional[int] = None

    for index, cavity in enumerate(adjusted_cavities):
      cavity_right = cavity.x + cavity.w
      cavity_top = cavity.y + cavity.h
      overlap_y = overlap_length(cavity.y, cavity_top, free_rect.y, free_rect.y + free_rect.h)
      overlap_x = overlap_length(cavity.x, cavity_right, free_rect.x, free_rect.x + free_rect.w)

      if 0.0 <= free_rect.x - cavity_right <= inner_wall_thickness + eps and has_substantial_overlap(cavity.h, free_rect.h, overlap_y, eps):
        left_index = index if left_index is None else -1

      if 0.0 <= cavity.x - (free_rect.x + free_rect.w) <= inner_wall_thickness + eps and has_substantial_overlap(cavity.h, free_rect.h, overlap_y, eps):
        right_index = index if right_index is None else -1

      if 0.0 <= free_rect.y - cavity_top <= inner_wall_thickness + eps and has_substantial_overlap(cavity.w, free_rect.w, overlap_x, eps):
        bottom_index = index if bottom_index is None else -1

      if 0.0 <= cavity.y - (free_rect.y + free_rect.h) <= inner_wall_thickness + eps and has_substantial_overlap(cavity.w, free_rect.w, overlap_x, eps):
        top_index = index if top_index is None else -1

    consumed = False

    if (
      left_index is not None and left_index >= 0 and
      right_index is not None and right_index >= 0 and
      left_index != right_index
    ):
      left_cavity = adjusted_cavities[left_index]
      right_cavity = adjusted_cavities[right_index]
      total_gap = right_cavity.x - (left_cavity.x + left_cavity.w)
      growth_total = max(0.0, total_gap)
      left_limit = growth_total
      right_limit = growth_total
      growth_split = distribute_growth_preferring_smaller(
        growth_total,
        left_limit,
        right_limit,
        left_cavity,
        right_cavity,
        eps
      )

      if growth_split is not None:
        left_growth, right_growth = growth_split
        grown_left = Rect(left_cavity.x, left_cavity.y, left_cavity.w + left_growth, left_cavity.h)
        grown_right = Rect(right_cavity.x - right_growth, right_cavity.y, right_cavity.w + right_growth, right_cavity.h)

        if not overlaps_other_cavity(grown_left, {left_index, right_index}) and not overlaps_other_cavity(grown_right, {left_index, right_index}):
          left_cavity.w = grown_left.w
          right_cavity.x = grown_right.x
          right_cavity.w = grown_right.w
          adjustments.append(
            GapAdjustment(
              axis="x",
              first_cavity_index=left_index + 1,
              second_cavity_index=right_index + 1,
              gap_size=total_gap,
              first_growth=left_growth,
              second_growth=right_growth
            )
          )
          consumed = True

    elif (
      bottom_index is not None and bottom_index >= 0 and
      top_index is not None and top_index >= 0 and
      bottom_index != top_index
    ):
      bottom_cavity = adjusted_cavities[bottom_index]
      top_cavity = adjusted_cavities[top_index]
      total_gap = top_cavity.y - (bottom_cavity.y + bottom_cavity.h)
      growth_total = max(0.0, total_gap)
      bottom_limit = growth_total
      top_limit = growth_total
      growth_split = distribute_growth_preferring_smaller(
        growth_total,
        bottom_limit,
        top_limit,
        bottom_cavity,
        top_cavity,
        eps
      )

      if growth_split is not None:
        bottom_growth, top_growth = growth_split
        grown_bottom = Rect(bottom_cavity.x, bottom_cavity.y, bottom_cavity.w, bottom_cavity.h + bottom_growth)
        grown_top = Rect(top_cavity.x, top_cavity.y - top_growth, top_cavity.w, top_cavity.h + top_growth)

        if not overlaps_other_cavity(grown_bottom, {bottom_index, top_index}) and not overlaps_other_cavity(grown_top, {bottom_index, top_index}):
          bottom_cavity.h = grown_bottom.h
          top_cavity.y = grown_top.y
          top_cavity.h = grown_top.h
          adjustments.append(
            GapAdjustment(
              axis="y",
              first_cavity_index=bottom_index + 1,
              second_cavity_index=top_index + 1,
              gap_size=total_gap,
              first_growth=bottom_growth,
              second_growth=top_growth
            )
          )
          consumed = True

    if not consumed:
      remaining_free.append(free_rect)

  clipped_remaining: List[Rect] = remaining_free[:]
  for cavity in adjusted_cavities:
    updated_free: List[Rect] = []
    for free_rect in clipped_remaining:
      updated_free.extend(subtract_rect(free_rect, cavity))
    clipped_remaining = normalize_free_rects(updated_free)

  return adjusted_cavities, clipped_remaining, adjustments


def split_free_rects_by_cavity_edges(
  free_rects: List[Rect],
  cavities: List[Rect],
  eps: float = 1e-9
) -> List[Rect]:
  split_rects: List[Rect] = []

  for free_rect in free_rects:
    x_cuts = {free_rect.x, free_rect.x + free_rect.w}
    y_cuts = {free_rect.y, free_rect.y + free_rect.h}

    for cavity in cavities:
      cavity_x0 = cavity.x
      cavity_x1 = cavity.x + cavity.w
      cavity_y0 = cavity.y
      cavity_y1 = cavity.y + cavity.h

      if spans_overlap_or_touch(free_rect.y, free_rect.y + free_rect.h, cavity_y0, cavity_y1, eps):
        if free_rect.x + eps < cavity_x0 < free_rect.x + free_rect.w - eps:
          x_cuts.add(cavity_x0)
        if free_rect.x + eps < cavity_x1 < free_rect.x + free_rect.w - eps:
          x_cuts.add(cavity_x1)

      if spans_overlap_or_touch(free_rect.x, free_rect.x + free_rect.w, cavity_x0, cavity_x1, eps):
        if free_rect.y + eps < cavity_y0 < free_rect.y + free_rect.h - eps:
          y_cuts.add(cavity_y0)
        if free_rect.y + eps < cavity_y1 < free_rect.y + free_rect.h - eps:
          y_cuts.add(cavity_y1)

    xs = sorted(x_cuts)
    ys = sorted(y_cuts)

    for x0, x1 in zip(xs, xs[1:]):
      for y0, y1 in zip(ys, ys[1:]):
        if x1 - x0 <= eps or y1 - y0 <= eps:
          continue
        split_rects.append(Rect(x0, y0, x1 - x0, y1 - y0))

  return normalize_free_rects(split_rects)


def split_narrow_free_rects_by_neighbor_edges(
  free_rects: List[Rect],
  neighbor_rects: List[Rect],
  inner_wall_thickness: float,
  eps: float = 1e-9
) -> List[Rect]:
  split_rects: List[Rect] = []

  for free_rect in free_rects:
    x_cuts = {free_rect.x, free_rect.x + free_rect.w}
    y_cuts = {free_rect.y, free_rect.y + free_rect.h}
    is_vertical_strip = free_rect.w <= free_rect.h
    distance_limit = max(
      inner_wall_thickness * 2.5,
      min(free_rect.w, free_rect.h) + 2.0 * inner_wall_thickness
    ) + eps

    for neighbor in neighbor_rects:
      neighbor_x0 = neighbor.x
      neighbor_x1 = neighbor.x + neighbor.w
      neighbor_y0 = neighbor.y
      neighbor_y1 = neighbor.y + neighbor.h

      if is_vertical_strip:
        is_close_horizontally = (
          spans_overlap_or_touch(free_rect.x, free_rect.x + free_rect.w, neighbor_x0, neighbor_x1, eps) or
          0.0 <= free_rect.x - neighbor_x1 <= distance_limit or
          0.0 <= neighbor_x0 - (free_rect.x + free_rect.w) <= distance_limit
        )
        if is_close_horizontally and spans_overlap_or_touch(free_rect.y, free_rect.y + free_rect.h, neighbor_y0, neighbor_y1, eps):
          if free_rect.y + eps < neighbor_y0 < free_rect.y + free_rect.h - eps:
            y_cuts.add(neighbor_y0)
          if free_rect.y + eps < neighbor_y1 < free_rect.y + free_rect.h - eps:
            y_cuts.add(neighbor_y1)
      else:
        is_close_vertically = (
          spans_overlap_or_touch(free_rect.y, free_rect.y + free_rect.h, neighbor_y0, neighbor_y1, eps) or
          0.0 <= free_rect.y - neighbor_y1 <= distance_limit or
          0.0 <= neighbor_y0 - (free_rect.y + free_rect.h) <= distance_limit
        )
        if is_close_vertically and spans_overlap_or_touch(free_rect.x, free_rect.x + free_rect.w, neighbor_x0, neighbor_x1, eps):
          if free_rect.x + eps < neighbor_x0 < free_rect.x + free_rect.w - eps:
            x_cuts.add(neighbor_x0)
          if free_rect.x + eps < neighbor_x1 < free_rect.x + free_rect.w - eps:
            x_cuts.add(neighbor_x1)

    xs = sorted(x_cuts)
    ys = sorted(y_cuts)
    for x0, x1 in zip(xs, xs[1:]):
      for y0, y1 in zip(ys, ys[1:]):
        if x1 - x0 <= eps or y1 - y0 <= eps:
          continue
        split_rects.append(Rect(x0, y0, x1 - x0, y1 - y0))

  return split_rects

def build_all_cavities(
  placed_clusters: List[PlacedCluster],
  free_rects: List[Rect],
  inner_wall_thickness: float,
  free_cell_size: Optional[Tuple[float, float]],
  domain: Rect
) -> Tuple[List[Rect], List[Rect], List[GapAdjustment]]:
  requested_cavities: List[Rect] = []

  for cluster in placed_clusters:
    requested_cavities.extend(cluster_to_cavities(cluster, inner_wall_thickness))

  free_rects = split_free_rects_by_cavity_edges(free_rects, requested_cavities)
  free_rects = split_narrow_free_rects_by_neighbor_edges(
    free_rects,
    requested_cavities,
    inner_wall_thickness
  )

  requested_cavities, free_rects, adjustments = adjust_requested_cavities_for_small_gaps(
    requested_cavities,
    free_rects,
    inner_wall_thickness
  )

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

  requested_cavities, free_cavities = absorb_narrow_free_cavities(
    requested_cavities,
    free_cavities,
    domain,
    inner_wall_thickness
  )
  free_cavities = normalize_free_rects(free_cavities)

  return requested_cavities, free_cavities, adjustments


def build_compartment_number_labels(cavity_count: int) -> List[str]:
  return [str(index) for index in range(1, cavity_count + 1)]


def build_compartment_placements(
  placed_clusters: List[PlacedCluster],
  requested_cavities: List[Rect],
  free_cavities: List[Rect]
) -> Tuple[List[CompartmentPlacement], List[CompartmentPlacement]]:
  adjusted_requested = [Rect(cavity.x, cavity.y, cavity.w, cavity.h) for cavity in requested_cavities]
  adjusted_free = [Rect(cavity.x, cavity.y, cavity.w, cavity.h) for cavity in free_cavities]
  eps = 1e-9

  for cavity in adjusted_requested:
    grew = True
    while grew:
      grew = False
      for free_index, free_rect in enumerate(adjusted_free):
        same_height = abs(free_rect.y - cavity.y) <= eps and abs(free_rect.h - cavity.h) <= eps
        if not same_height:
          continue

        grows_left = abs((free_rect.x + free_rect.w) - cavity.x) <= eps
        grows_right = abs((cavity.x + cavity.w) - free_rect.x) <= eps
        if not grows_left and not grows_right:
          continue

        candidate = Rect(
          free_rect.x if grows_left else cavity.x,
          cavity.y,
          cavity.w + free_rect.w,
          cavity.h
        )

        blocked = False
        for other in adjusted_requested:
          if other is cavity:
            continue
          overlap_x = overlap_length(candidate.x, candidate.x + candidate.w, other.x, other.x + other.w)
          overlap_y = overlap_length(candidate.y, candidate.y + candidate.h, other.y, other.y + other.h)
          if overlap_x > eps and overlap_y > eps:
            blocked = True
            break

        if blocked:
          continue

        cavity.x = candidate.x
        cavity.w = candidate.w
        del adjusted_free[free_index]
        grew = True
        break

  max_x = 0.0
  for rect in adjusted_requested + adjusted_free:
    max_x = max(max_x, rect.x + rect.w)

  for cavity in adjusted_requested:
    grew = True
    while grew:
      grew = False
      cavity_right = cavity.x + cavity.w

      for free_index, free_rect in enumerate(adjusted_free):
        if abs(free_rect.x - cavity_right) > eps:
          continue

        free_covers_height = free_rect.y <= cavity.y + eps and free_rect.y + free_rect.h >= cavity.y + cavity.h - eps
        if not free_covers_height:
          continue

        candidate = Rect(cavity.x, cavity.y, cavity.w + free_rect.w, cavity.h)

        blocked = False
        for other in adjusted_requested:
          if other is cavity:
            continue
          overlap_x = overlap_length(candidate.x, candidate.x + candidate.w, other.x, other.x + other.w)
          overlap_y = overlap_length(candidate.y, candidate.y + candidate.h, other.y, other.y + other.h)
          if overlap_x > eps and overlap_y > eps:
            blocked = True
            break

        if blocked:
          continue

        cavity.w = candidate.w

        consumed_slice = Rect(free_rect.x, cavity.y, free_rect.w, cavity.h)
        replacement = subtract_rect(free_rect, consumed_slice, eps)
        del adjusted_free[free_index]
        for part in replacement:
          if part.w > eps and part.h > eps:
            adjusted_free.append(part)

        adjusted_free = normalize_free_rects(adjusted_free, eps)

        if cavity.x + cavity.w >= max_x - eps:
          break

        grew = True
        break

  for cavity in adjusted_requested:
    current_right = cavity.x + cavity.w
    if current_right >= max_x - eps:
      continue

    candidate = Rect(cavity.x, cavity.y, max_x - cavity.x, cavity.h)
    blocked = False
    for other in adjusted_requested:
      if other is cavity:
        continue
      overlap_x = overlap_length(candidate.x, candidate.x + candidate.w, other.x, other.x + other.w)
      overlap_y = overlap_length(candidate.y, candidate.y + candidate.h, other.y, other.y + other.h)
      if overlap_x > eps and overlap_y > eps:
        blocked = True
        break

    if blocked:
      continue

    cavity.w = candidate.w

    consumed_strip = Rect(current_right, cavity.y, max_x - current_right, cavity.h)
    next_free: List[Rect] = []
    for free_rect in adjusted_free:
      next_free.extend(subtract_rect(free_rect, consumed_strip, eps))
    adjusted_free = normalize_free_rects(next_free, eps)

  requested: List[CompartmentPlacement] = []
  number = 1
  expected_requested_count = sum(cluster.cells for cluster in placed_clusters)

  if len(requested_cavities) != expected_requested_count:
    raise RuntimeError(
      "Adjusted requested cavities do not match the placed compartment count."
    )

  requested_index = 0
  for cluster in placed_clusters:
    for _ in range(cluster.cells):
      cavity = adjusted_requested[requested_index]
      requested.append(
        CompartmentPlacement(
          number=number,
          x=cavity.x,
          y=cavity.y,
          w=cavity.w,
          h=cavity.h,
          requested_w=cluster.requested_cell_w,
          requested_h=cluster.requested_cell_h,
          is_free=False
        )
      )
      requested_index += 1
      number += 1

  free: List[CompartmentPlacement] = []
  for cavity in adjusted_free:
    free.append(
      CompartmentPlacement(
        number=number,
        x=cavity.x,
        y=cavity.y,
        w=cavity.w,
        h=cavity.h,
        requested_w=cavity.w,
        requested_h=cavity.h,
        is_free=True
      )
    )
    number += 1

  return requested, free


def find_overlapping_compartments(
  compartments: List[CompartmentPlacement],
  eps: float = 1e-9
) -> List[Tuple[int, int, float, float]]:
  overlaps: List[Tuple[int, int, float, float]] = []

  for first_index in range(len(compartments)):
    first = compartments[first_index]
    for second_index in range(first_index + 1, len(compartments)):
      second = compartments[second_index]
      overlap_x = overlap_length(first.x, first.x + first.w, second.x, second.x + second.w)
      overlap_y = overlap_length(first.y, first.y + first.h, second.y, second.y + second.h)
      if overlap_x > eps and overlap_y > eps:
        overlaps.append((first.number, second.number, overlap_x, overlap_y))

  return overlaps


def get_compartment_adjustment_marker(compartment: CompartmentPlacement, eps: float = 1e-6) -> str:
  wider = compartment.w > compartment.requested_w + eps
  taller = compartment.h > compartment.requested_h + eps
  narrower = compartment.w < compartment.requested_w - eps
  shorter = compartment.h < compartment.requested_h - eps

  if compartment.is_free:
    return ""
  if (wider or taller) and not (narrower or shorter):
    return "+"
  if (narrower or shorter) and not (wider or taller):
    return "-"
  if (wider or taller) and (narrower or shorter):
    return "+-"
  return ""


def format_adjustment_marker_display(marker: str) -> str:
  if not marker:
    return ""
  return f"({marker})"


def get_axis_adjustment_marker(actual: float, requested: float, eps: float = 1e-6) -> str:
  if actual > requested + eps:
    return "+"
  if actual < requested - eps:
    return "-"
  return ""


def format_requested_size_with_axis_markers(compartment: CompartmentPlacement) -> str:
  rounded_w = int(round(compartment.requested_w))
  rounded_h = int(round(compartment.requested_h))
  width_marker = get_axis_adjustment_marker(compartment.w, compartment.requested_w)
  height_marker = get_axis_adjustment_marker(compartment.h, compartment.requested_h)
  width_suffix = f"({width_marker})" if width_marker else ""
  height_suffix = f"({height_marker})" if height_marker else ""
  return f"{rounded_w}{width_suffix}X{rounded_h}{height_suffix}"


def build_compartment_primary_labels(compartments: List[CompartmentPlacement]) -> List[str]:
  labels: List[str] = []
  for compartment in compartments:
    prefix = "L" if compartment.is_free else "C"
    base_label = f"{prefix}{compartment.number:02d}"
    marker = get_compartment_adjustment_marker(compartment)
    labels.append(f"{base_label}{format_adjustment_marker_display(marker)}")
  return labels


def build_compartment_secondary_labels(compartments: List[CompartmentPlacement]) -> List[str]:
  return [format_requested_size_with_axis_markers(compartment) for compartment in compartments]


def absorb_narrow_free_cavities(
  requested_cavities: List[Rect],
  free_cavities: List[Rect],
  domain: Rect,
  inner_wall_thickness: float,
  eps: float = 1e-9
) -> Tuple[List[Rect], List[Rect]]:
  if not free_cavities:
    return requested_cavities, free_cavities

  free_cavities = split_narrow_free_rects_by_neighbor_edges(
    free_cavities,
    requested_cavities + free_cavities,
    inner_wall_thickness,
    eps
  )

  max_x = domain.x + domain.w
  max_y = domain.y + domain.h
  requested_count = len(requested_cavities)
  cavities: List[Rect] = [Rect(c.x, c.y, c.w, c.h) for c in requested_cavities + free_cavities]
  free_indices = set(range(requested_count, len(cavities)))
  removed_indices: set[int] = set()

  def overlaps_active_cavity(candidate: Rect, skip_indices: set[int]) -> bool:
    for idx, other in enumerate(cavities):
      if idx in removed_indices or idx in skip_indices:
        continue
      if idx >= requested_count:
        continue
      overlap_x = overlap_length(candidate.x, candidate.x + candidate.w, other.x, other.x + other.w)
      overlap_y = overlap_length(candidate.y, candidate.y + candidate.h, other.y, other.y + other.h)
      if overlap_x > eps and overlap_y > eps:
        return True
    return False

  def find_neighbors_for_strip(strip_index: int, axis: str) -> Tuple[Optional[int], Optional[int]]:
    strip = cavities[strip_index]
    strip_right = strip.x + strip.w
    strip_top = strip.y + strip.h
    first_neighbor: Optional[int] = None
    second_neighbor: Optional[int] = None
    best_first_gap = float("inf")
    best_second_gap = float("inf")
    best_first_overlap = -1.0
    best_second_overlap = -1.0
    distance_limit = max(
      inner_wall_thickness * 2.5,
      min(strip.w, strip.h) * 1.75 + inner_wall_thickness
    ) + eps

    for idx, candidate in enumerate(cavities):
      if idx == strip_index or idx in removed_indices:
        continue

      candidate_right = candidate.x + candidate.w
      candidate_top = candidate.y + candidate.h

      overlap_y = overlap_length(candidate.y, candidate_top, strip.y, strip_top)
      overlap_x = overlap_length(candidate.x, candidate_right, strip.x, strip_right)

      if axis == "x":
        left_gap = strip.x - candidate_right
        right_gap = candidate.x - strip_right

        if 0.0 <= left_gap <= distance_limit and overlap_y > eps:
          if left_gap + eps < best_first_gap or (abs(left_gap - best_first_gap) <= eps and overlap_y > best_first_overlap):
            best_first_gap = left_gap
            best_first_overlap = overlap_y
            first_neighbor = idx
        if 0.0 <= right_gap <= distance_limit and overlap_y > eps:
          if right_gap + eps < best_second_gap or (abs(right_gap - best_second_gap) <= eps and overlap_y > best_second_overlap):
            best_second_gap = right_gap
            best_second_overlap = overlap_y
            second_neighbor = idx
      else:
        bottom_gap = strip.y - candidate_top
        top_gap = candidate.y - strip_top

        if 0.0 <= bottom_gap <= distance_limit and overlap_x > eps:
          if bottom_gap + eps < best_first_gap or (abs(bottom_gap - best_first_gap) <= eps and overlap_x > best_first_overlap):
            best_first_gap = bottom_gap
            best_first_overlap = overlap_x
            first_neighbor = idx
        if 0.0 <= top_gap <= distance_limit and overlap_x > eps:
          if top_gap + eps < best_second_gap or (abs(top_gap - best_second_gap) <= eps and overlap_x > best_second_overlap):
            best_second_gap = top_gap
            best_second_overlap = overlap_x
            second_neighbor = idx

    return first_neighbor, second_neighbor

  def is_narrow_strip(rect: Rect) -> bool:
    short_side = min(rect.w, rect.h)
    long_side = max(rect.w, rect.h)
    return short_side <= max(2.0 * inner_wall_thickness, 0.75 * long_side)

  ordered_free_indices = sorted(free_indices, key=lambda idx: min(cavities[idx].w, cavities[idx].h))

  for strip_index in ordered_free_indices:
    if strip_index in removed_indices:
      continue

    strip = cavities[strip_index]
    if not is_narrow_strip(strip):
      continue

    x_axis_strip = strip.w <= strip.h
    axis = "x" if x_axis_strip else "y"
    first_neighbor, second_neighbor = find_neighbors_for_strip(strip_index, axis)
    consumed = False

    def try_consume_with_axis(
      active_axis: str,
      left_or_bottom_neighbor: Optional[int],
      right_or_top_neighbor: Optional[int]
    ) -> bool:
      if left_or_bottom_neighbor is not None and right_or_top_neighbor is not None and left_or_bottom_neighbor != right_or_top_neighbor:
        first = cavities[left_or_bottom_neighbor]
        second = cavities[right_or_top_neighbor]

        if active_axis == "x":
          total_gap = second.x - (first.x + first.w)
          growth_total = max(0.0, total_gap)
          growth_split = distribute_growth_preferring_smaller(
            growth_total,
            growth_total,
            growth_total,
            first,
            second,
            eps
          )
          if growth_split is not None:
            first_growth, second_growth = growth_split
            grown_first = Rect(first.x, first.y, first.w + first_growth, first.h)
            grown_second = Rect(second.x - second_growth, second.y, second.w + second_growth, second.h)
            if not overlaps_active_cavity(grown_first, {strip_index, left_or_bottom_neighbor, right_or_top_neighbor}) and not overlaps_active_cavity(grown_second, {strip_index, left_or_bottom_neighbor, right_or_top_neighbor}):
              first.w = grown_first.w
              second.x = grown_second.x
              second.w = grown_second.w
              return True
        else:
          total_gap = second.y - (first.y + first.h)
          growth_total = max(0.0, total_gap)
          growth_split = distribute_growth_preferring_smaller(
            growth_total,
            growth_total,
            growth_total,
            first,
            second,
            eps
          )
          if growth_split is not None:
            first_growth, second_growth = growth_split
            grown_first = Rect(first.x, first.y, first.w, first.h + first_growth)
            grown_second = Rect(second.x, second.y - second_growth, second.w, second.h + second_growth)
            if not overlaps_active_cavity(grown_first, {strip_index, left_or_bottom_neighbor, right_or_top_neighbor}) and not overlaps_active_cavity(grown_second, {strip_index, left_or_bottom_neighbor, right_or_top_neighbor}):
              first.h = grown_first.h
              second.y = grown_second.y
              second.h = grown_second.h
              return True

      strip_right = strip.x + strip.w
      strip_top = strip.y + strip.h
      touches_left = strip.x <= domain.x + eps
      touches_right = strip_right >= max_x - eps
      touches_bottom = strip.y <= domain.y + eps
      touches_top = strip_top >= max_y - eps

      if active_axis == "x":
        if touches_left and right_or_top_neighbor is not None:
          right_neighbor = cavities[right_or_top_neighbor]
          growth = right_neighbor.x - domain.x
          if growth > eps:
            grown_right = Rect(domain.x, right_neighbor.y, right_neighbor.w + growth, right_neighbor.h)
            if not overlaps_active_cavity(grown_right, {strip_index, right_or_top_neighbor}):
              right_neighbor.x = grown_right.x
              right_neighbor.w = grown_right.w
              return True
        elif touches_right and left_or_bottom_neighbor is not None:
          left_neighbor = cavities[left_or_bottom_neighbor]
          growth = max_x - (left_neighbor.x + left_neighbor.w)
          if growth > eps:
            grown_left = Rect(left_neighbor.x, left_neighbor.y, left_neighbor.w + growth, left_neighbor.h)
            if not overlaps_active_cavity(grown_left, {strip_index, left_or_bottom_neighbor}):
              left_neighbor.w = grown_left.w
              return True
        elif left_or_bottom_neighbor is not None:
          left_neighbor = cavities[left_or_bottom_neighbor]
          growth = strip_right - left_neighbor.x - left_neighbor.w
          if growth > eps:
            grown_left = Rect(left_neighbor.x, left_neighbor.y, left_neighbor.w + growth, left_neighbor.h)
            if not overlaps_active_cavity(grown_left, {strip_index, left_or_bottom_neighbor}):
              left_neighbor.w = grown_left.w
              return True
        elif right_or_top_neighbor is not None:
          right_neighbor = cavities[right_or_top_neighbor]
          growth = right_neighbor.x - strip.x
          if growth > eps:
            grown_right = Rect(strip.x, right_neighbor.y, right_neighbor.w + growth, right_neighbor.h)
            if not overlaps_active_cavity(grown_right, {strip_index, right_or_top_neighbor}):
              right_neighbor.x = grown_right.x
              right_neighbor.w = grown_right.w
              return True
      else:
        if touches_bottom and right_or_top_neighbor is not None:
          top_neighbor = cavities[right_or_top_neighbor]
          growth = top_neighbor.y - domain.y
          if growth > eps:
            grown_top = Rect(top_neighbor.x, domain.y, top_neighbor.w, top_neighbor.h + growth)
            if not overlaps_active_cavity(grown_top, {strip_index, right_or_top_neighbor}):
              top_neighbor.y = grown_top.y
              top_neighbor.h = grown_top.h
              return True
        elif touches_top and left_or_bottom_neighbor is not None:
          bottom_neighbor = cavities[left_or_bottom_neighbor]
          growth = max_y - (bottom_neighbor.y + bottom_neighbor.h)
          if growth > eps:
            grown_bottom = Rect(bottom_neighbor.x, bottom_neighbor.y, bottom_neighbor.w, bottom_neighbor.h + growth)
            if not overlaps_active_cavity(grown_bottom, {strip_index, left_or_bottom_neighbor}):
              bottom_neighbor.h = grown_bottom.h
              return True
        elif left_or_bottom_neighbor is not None:
          bottom_neighbor = cavities[left_or_bottom_neighbor]
          growth = strip_top - bottom_neighbor.y - bottom_neighbor.h
          if growth > eps:
            grown_bottom = Rect(bottom_neighbor.x, bottom_neighbor.y, bottom_neighbor.w, bottom_neighbor.h + growth)
            if not overlaps_active_cavity(grown_bottom, {strip_index, left_or_bottom_neighbor}):
              bottom_neighbor.h = grown_bottom.h
              return True
        elif right_or_top_neighbor is not None:
          top_neighbor = cavities[right_or_top_neighbor]
          growth = top_neighbor.y - strip.y
          if growth > eps:
            grown_top = Rect(top_neighbor.x, strip.y, top_neighbor.w, top_neighbor.h + growth)
            if not overlaps_active_cavity(grown_top, {strip_index, right_or_top_neighbor}):
              top_neighbor.y = grown_top.y
              top_neighbor.h = grown_top.h
              return True

      return False

    consumed = try_consume_with_axis(axis, first_neighbor, second_neighbor)

    if consumed:
      removed_indices.add(strip_index)

  updated_requested: List[Rect] = []
  updated_free: List[Rect] = []

  for idx, cavity in enumerate(cavities):
    if idx in removed_indices:
      continue
    if cavity.w <= eps or cavity.h <= eps:
      continue
    if idx < requested_count:
      updated_requested.append(cavity)
    else:
      updated_free.append(cavity)

  for cavity in updated_requested:
    grown = True
    while grown:
      grown = False
      for free_index, free_rect in enumerate(updated_free):
        same_height = abs(free_rect.y - cavity.y) <= eps and abs(free_rect.h - cavity.h) <= eps
        if not same_height:
          continue

        grows_left = abs((free_rect.x + free_rect.w) - cavity.x) <= eps
        grows_right = abs((cavity.x + cavity.w) - free_rect.x) <= eps
        if not grows_left and not grows_right:
          continue

        candidate = Rect(
          free_rect.x if grows_left else cavity.x,
          cavity.y,
          cavity.w + free_rect.w,
          cavity.h
        )

        blocked = False
        for other in updated_requested:
          if other is cavity:
            continue
          overlap_x = overlap_length(candidate.x, candidate.x + candidate.w, other.x, other.x + other.w)
          overlap_y = overlap_length(candidate.y, candidate.y + candidate.h, other.y, other.y + other.h)
          if overlap_x > eps and overlap_y > eps:
            blocked = True
            break

        if blocked:
          continue

        cavity.x = candidate.x
        cavity.w = candidate.w
        del updated_free[free_index]
        grown = True
        break

  clipped_free = updated_free[:]
  for cavity in updated_requested:
    next_free: List[Rect] = []
    for free_rect in clipped_free:
      next_free.extend(subtract_rect(free_rect, cavity))
    clipped_free = normalize_free_rects(next_free)

  return updated_requested, normalize_free_rects(clipped_free)


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

  if cell_w <= eps or cell_h <= eps:
    return free_rects

  for free_rect in free_rects:
    columns = 0
    rows = 0
    forced_single_column = False
    forced_single_row = False

    used_width = 0.0
    while True:
      next_width = columns * (cell_w + inner_wall_thickness) + cell_w
      if next_width > free_rect.w + eps:
        break
      columns += 1
      used_width = next_width

    used_height = 0.0
    while True:
      next_height = rows * (cell_h + inner_wall_thickness) + cell_h
      if next_height > free_rect.h + eps:
        break
      rows += 1
      used_height = next_height

    if columns == 0:
      columns = 1
      forced_single_column = True
      used_width = free_rect.w

    if rows == 0:
      rows = 1
      forced_single_row = True
      used_height = free_rect.h

    base_cell_w = free_rect.w if forced_single_column else cell_w
    base_cell_h = free_rect.h if forced_single_row else cell_h

    remainder_x = max(0.0, free_rect.w - used_width)
    remainder_y = max(0.0, free_rect.h - used_height)
    extra_w = remainder_x / columns
    extra_h = remainder_y / rows
    remainder_x = 0.0
    remainder_y = 0.0

    actual_cell_w = base_cell_w + extra_w
    actual_cell_h = base_cell_h + extra_h
    step_x = actual_cell_w
    step_y = actual_cell_h

    for row_index in range(rows):
      y = free_rect.y + row_index * step_y
      for column_index in range(columns):
        x = free_rect.x + column_index * step_x
        cells.append(Rect(x, y, actual_cell_w, actual_cell_h))

    used_span_x = columns * actual_cell_w
    used_span_y = rows * actual_cell_h
    remainder_x_start = free_rect.x + used_span_x
    remainder_y_start = free_rect.y + used_span_y
    right_remainder_w = (free_rect.x + free_rect.w) - remainder_x_start
    bottom_remainder_h = (free_rect.y + free_rect.h) - remainder_y_start

    if right_remainder_w > eps:
      for row_index in range(rows):
        y = free_rect.y + row_index * step_y
        cells.append(Rect(remainder_x_start, y, right_remainder_w, actual_cell_h))

    if bottom_remainder_h > eps:
      for column_index in range(columns):
        x = free_rect.x + column_index * step_x
        cells.append(Rect(x, remainder_y_start, actual_cell_w, bottom_remainder_h))

    if right_remainder_w > eps and bottom_remainder_h > eps:
      cells.append(Rect(remainder_x_start, remainder_y_start, right_remainder_w, bottom_remainder_h))

  if not cells:
    return free_rects

  filtered_cells = [rect for rect in cells if rect.w > eps and rect.h > eps]
  return normalize_free_rects(filtered_cells)


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
  "X": [
    "101",
    "101",
    "010",
    "101",
    "101"
  ],
  "C": [
    "111",
    "100",
    "100",
    "100",
    "111"
  ],
  "L": [
    "100",
    "100",
    "100",
    "100",
    "111"
  ],
  "+": [
    "000",
    "010",
    "111",
    "010",
    "000"
  ],
  "-": [
    "000",
    "000",
    "111",
    "000",
    "000"
  ],
  "(": [
    "001",
    "010",
    "010",
    "010",
    "001"
  ],
  ")": [
    "100",
    "010",
    "010",
    "010",
    "100"
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
  rounded_w = int(round(width))
  rounded_h = int(round(height))
  return f"{rounded_w}x{rounded_h}"


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
  bottom_thickness: float,
  compartment_label_texts: Optional[List[str]] = None,
  secondary_label_texts: Optional[List[str]] = None
) -> Tuple[List[SolidBox], List[LabelGlyph]]:
  boxes: List[SolidBox] = []
  glyphs: List[LabelGlyph] = []

  def append_text_boxes(
    compartment_number: int,
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
        glyphs.append(LabelGlyph(compartment_number=compartment_number, text=char, boxes=char_boxes))

      cursor_x += pattern_w * pixel_size
      if char_index < len(text) - 1:
        cursor_x += gap_size

  for index, cavity in enumerate(cavities):
    compartment_number = index + 1
    if compartment_label_texts is not None and index < len(compartment_label_texts):
      primary_text = compartment_label_texts[index]
    else:
      primary_text = format_compartment_size_label(cavity.w, cavity.h)

    secondary_text: Optional[str] = None
    if secondary_label_texts is not None and index < len(secondary_label_texts):
      secondary_text = secondary_label_texts[index]

    lines = [line for line in [primary_text, secondary_text] if line]
    if not lines:
      continue

    line_dimensions: List[Tuple[int, int]] = [get_text_pixel_dimensions(line) for line in lines]
    if any(units_w <= 0 or units_h <= 0 for units_w, units_h in line_dimensions):
      continue

    widest_units = max(units_w for units_w, _ in line_dimensions)
    line_height_units = 5
    line_gap_units = 2 if len(lines) > 1 else 0
    total_height_units = len(lines) * line_height_units + (len(lines) - 1) * line_gap_units

    margin = max(0.5, min(cavity.w, cavity.h) * 0.06)
    available_w = cavity.w - 2.0 * margin
    available_h = cavity.h - 2.0 * margin

    if available_w <= 0 or available_h <= 0:
      continue

    preferred_pixel_size = 0.55
    max_fit_pixel_size = min(available_w / widest_units, available_h / total_height_units)
    pixel_size = min(preferred_pixel_size, max_fit_pixel_size)
    if pixel_size < 0.30:
      continue

    label_height = min(0.65, max(0.3, bottom_thickness * 0.28))
    total_height = total_height_units * pixel_size
    current_y = cavity.y + (cavity.h - total_height) / 2.0

    for line, (line_units_w, _) in zip(lines, line_dimensions):
      line_w = line_units_w * pixel_size
      start_x = cavity.x + (cavity.w - line_w) / 2.0
      append_text_boxes(compartment_number, line, start_x, current_y, pixel_size, label_height)
      current_y += (line_height_units + line_gap_units) * pixel_size

  return boxes, glyphs


# ------------------------------------------------------------
# OpenSCAD generation
# ------------------------------------------------------------


def make_scad(
  outer_length: float,
  outer_width: float,
  outer_height: float,
  inner_length: float,
  inner_width: float,
  inner_height: float,
  inner_wall_height: float,
  outer_wall_thickness: float,
  inner_wall_thickness: float,
  bottom_thickness: float,
  outer_corner_radius: float,
  placed_clusters: List[PlacedCluster],
  requested_compartments: List[CompartmentPlacement],
  free_compartments: List[CompartmentPlacement],
  label_boxes: List[SolidBox],
  label_glyphs: List[LabelGlyph]
) -> str:
  _ = outer_corner_radius

  lines: List[str] = []
  all_compartments = requested_compartments + free_compartments

  lines.append("// Generated by Python")
  lines.append("// The requested box dimensions are the outer dimensions in mm")
  lines.append("// Compartments are generated individually with makeCompartment()")
  lines.append("")

  lines.append(f"outerLength = {outer_length:.3f};")
  lines.append(f"outerWidth = {outer_width:.3f};")
  lines.append(f"outerHeight = {outer_height:.3f};")
  lines.append(f"innerLength = {inner_length:.3f};")
  lines.append(f"innerWidth = {inner_width:.3f};")
  lines.append(f"innerHeight = {inner_height:.3f};")
  lines.append(f"innerWallHeight = {inner_wall_height:.3f};")
  lines.append(f"outerWallThickness = {outer_wall_thickness:.3f};")
  lines.append(f"innerWallThickness = {inner_wall_thickness:.3f};")
  lines.append(f"bottomThickness = {bottom_thickness:.3f};")
  lines.append("outerCornerRadius = 0.000;")
  lines.append("")
  lines.append("$fn = 64;")
  lines.append("")

  _ = placed_clusters

  lines.append("module outerSolid()")
  lines.append("{")
  lines.append("  translate([-outerWallThickness, -outerWallThickness, 0])")
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

  lines.append("module makeCompartment(nr, posX, posY, sizeX, sizeY)")
  lines.append("{")
  lines.append("  tol = 0.0005;")
  lines.append("  innerHalf = innerWallThickness / 2;")
  lines.append("  leftBoundary = posX <= tol;")
  lines.append("  rightBoundary = posX + sizeX >= innerLength - tol;")
  lines.append("  bottomBoundary = posY <= tol;")
  lines.append("  topBoundary = posY + sizeY >= innerWidth - tol;")
  lines.append("  xMin = leftBoundary ? -outerWallThickness : posX - innerHalf;")
  lines.append("  xMax = rightBoundary ? innerLength + outerWallThickness : posX + sizeX + innerHalf;")
  lines.append("  yMin = bottomBoundary ? -outerWallThickness : posY - innerHalf;")
  lines.append("  yMax = topBoundary ? innerWidth + outerWallThickness : posY + sizeY + innerHalf;")
  lines.append("  leftStart = leftBoundary ? -outerWallThickness : posX - innerHalf;")
  lines.append("  rightStart = rightBoundary ? innerLength : posX + sizeX - innerHalf;")
  lines.append("  bottomStart = bottomBoundary ? -outerWallThickness : posY - innerHalf;")
  lines.append("  topStart = topBoundary ? innerWidth : posY + sizeY - innerHalf;")
  lines.append("  leftThickness = leftBoundary ? outerWallThickness : innerWallThickness;")
  lines.append("  rightThickness = rightBoundary ? outerWallThickness : innerWallThickness;")
  lines.append("  bottomThicknessLocal = bottomBoundary ? outerWallThickness : innerWallThickness;")
  lines.append("  topThicknessLocal = topBoundary ? outerWallThickness : innerWallThickness;")
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

  lines.append("module labelBlock(x, y, z, w, h, d)")
  lines.append("{")
  lines.append("  translate([x, y, z])")
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
  for compartment in all_compartments:
    requested_size = format_requested_size_with_axis_markers(compartment)
    actual_size = format_compartment_size_label(compartment.w, compartment.h)
    kind = "free" if compartment.is_free else "requested"
    marker = get_compartment_adjustment_marker(compartment) or "none"
    lines.append(
      f"      // {kind}, requested={requested_size}, actual={actual_size}, marker={marker}"
    )
    lines.append(
      f"      makeCompartment({compartment.number}, {compartment.x:.3f}, {compartment.y:.3f}, {compartment.w:.3f}, {compartment.h:.3f});"
    )
  for glyph in label_glyphs:
    glyph_is_free = glyph.compartment_number > len(requested_compartments)
    glyph_prefix = "L" if glyph_is_free else "C"
    lines.append(f"      //-- {glyph_prefix}{glyph.compartment_number:02d}: {glyph.text}")
    for label_box in glyph.boxes:
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
  outer_length: float,
  outer_width: float,
  outer_height: float,
  inner_length: float,
  inner_width: float,
  inner_height: float,
  inner_wall_height: float,
  outer_wall_thickness: float,
  inner_wall_thickness: float,
  bottom_thickness: float,
  compartments: List[CompartmentPlacement],
  label_boxes: List[SolidBox]
) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
  triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []

  append_box_triangles(triangles, -outer_wall_thickness, -outer_wall_thickness, 0.0, inner_length + outer_wall_thickness, inner_width + outer_wall_thickness, bottom_thickness)
  append_box_triangles(triangles, -outer_wall_thickness, -outer_wall_thickness, bottom_thickness, inner_length + outer_wall_thickness, 0.0, outer_height)
  append_box_triangles(
    triangles,
    -outer_wall_thickness,
    inner_width,
    bottom_thickness,
    inner_length + outer_wall_thickness,
    inner_width + outer_wall_thickness,
    outer_height
  )
  append_box_triangles(
    triangles,
    -outer_wall_thickness,
    0.0,
    bottom_thickness,
    0.0,
    inner_width,
    outer_height
  )
  append_box_triangles(
    triangles,
    inner_length,
    0.0,
    bottom_thickness,
    inner_length + outer_wall_thickness,
    inner_width,
    outer_height
  )

  wall_z0 = bottom_thickness / 2.0
  wall_z1 = wall_z0 + inner_wall_height
  tol = 1e-6

  for compartment in compartments:
    inner_half = inner_wall_thickness / 2.0
    left_boundary = compartment.x <= tol
    right_boundary = compartment.x + compartment.w >= inner_length - tol
    bottom_boundary = compartment.y <= tol
    top_boundary = compartment.y + compartment.h >= inner_width - tol

    x_min = -outer_wall_thickness if left_boundary else compartment.x - inner_half
    x_max = inner_length + outer_wall_thickness if right_boundary else compartment.x + compartment.w + inner_half
    y_min = -outer_wall_thickness if bottom_boundary else compartment.y - inner_half
    y_max = inner_width + outer_wall_thickness if top_boundary else compartment.y + compartment.h + inner_half

    left_start = -outer_wall_thickness if left_boundary else compartment.x - inner_half
    right_start = inner_length if right_boundary else compartment.x + compartment.w - inner_half
    bottom_start = -outer_wall_thickness if bottom_boundary else compartment.y - inner_half
    top_start = inner_width if top_boundary else compartment.y + compartment.h - inner_half

    left_thickness = outer_wall_thickness if left_boundary else inner_wall_thickness
    right_thickness = outer_wall_thickness if right_boundary else inner_wall_thickness
    bottom_thickness_local = outer_wall_thickness if bottom_boundary else inner_wall_thickness
    top_thickness_local = outer_wall_thickness if top_boundary else inner_wall_thickness

    append_box_triangles(
      triangles,
      left_start,
      y_min,
      wall_z0,
      left_start + left_thickness,
      y_max,
      wall_z1
    )
    append_box_triangles(
      triangles,
      right_start,
      y_min,
      wall_z0,
      right_start + right_thickness,
      y_max,
      wall_z1
    )
    append_box_triangles(
      triangles,
      x_min,
      bottom_start,
      wall_z0,
      x_max,
      bottom_start + bottom_thickness_local,
      wall_z1
    )
    append_box_triangles(
      triangles,
      x_min,
      top_start,
      wall_z0,
      x_max,
      top_start + top_thickness_local,
      wall_z1
    )

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
  outer_length: float,
  outer_width: float,
  outer_height: float,
  inner_length: float,
  inner_width: float,
  inner_height: float,
  inner_wall_height: float,
  outer_wall_thickness: float,
  inner_wall_thickness: float,
  bottom_thickness: float,
  outer_corner_radius: float,
  compartments: List[CompartmentPlacement],
  label_boxes: List[SolidBox]
) -> str:
  # STL export is intentionally self-contained: no OpenSCAD dependency,
  # no external Python packages, and no separate virtual environment setup.
  triangles = build_stl_triangles(
    outer_length=outer_length,
    outer_width=outer_width,
    outer_height=outer_height,
    inner_length=inner_length,
    inner_width=inner_width,
    inner_height=inner_height,
    inner_wall_height=inner_wall_height,
    outer_wall_thickness=outer_wall_thickness,
    inner_wall_thickness=inner_wall_thickness,
    bottom_thickness=bottom_thickness,
    compartments=compartments,
    label_boxes=label_boxes
  )
  write_ascii_stl(stl_path, triangles)
  _ = outer_corner_radius
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


def print_gap_adjustments(adjustments: List[GapAdjustment]) -> None:
  print("")
  print("Absorbed tiny gaps between requested cavities:")

  if not adjustments:
    print("  None")
    return

  for index, adjustment in enumerate(adjustments, start=1):
    print(
      f"  adjustment_{index:02d} "
      f"axis={adjustment.axis} "
      f"between=requested_{adjustment.first_cavity_index:02d}/requested_{adjustment.second_cavity_index:02d} "
      f"gap={adjustment.gap_size:.3f} "
      f"growth=+{adjustment.first_growth:.3f}/+{adjustment.second_growth:.3f}"
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

  outer_length, outer_width, outer_height = ask_box_dimensions(
    (defaults.outer_length, defaults.outer_width, defaults.outer_height)
  )
  inner_wall_height_default = defaults.inner_wall_height if defaults.inner_wall_height is not None else outer_height
  inner_wall_height = ask_float("Enter inner wall height in mm", inner_wall_height_default, allow_zero=False)
  outer_wall_thickness = ask_float("Enter outer wall thickness in mm", defaults.outer_wall_thickness, allow_zero=False)
  inner_wall_thickness = ask_float("Enter inner divider thickness in mm", defaults.inner_wall_thickness, allow_zero=False)
  bottom_thickness = ask_float("Enter bottom thickness in mm", defaults.bottom_thickness, allow_zero=False)
  outer_corner_radius = 0.0

  inner_length = outer_length - 2.0 * outer_wall_thickness
  inner_width = outer_width - 2.0 * outer_wall_thickness
  inner_height = outer_height - bottom_thickness

  if inner_length <= 0 or inner_width <= 0 or inner_height <= 0:
    print("")
    print("Error: Outer box dimensions are too small for the selected outer wall and bottom thickness.")
    return

  if inner_wall_height > inner_height:
    print("Warning: inner wall height is larger than the usable inner height. It will be capped.")
    inner_wall_height = inner_height

  free_cell_default: Optional[Tuple[float, float]] = None
  if defaults.free_cell_w is not None and defaults.free_cell_h is not None:
    free_cell_default = (defaults.free_cell_w, defaults.free_cell_h)
  free_cell_size = ask_optional_size_2d_with_default("Enter leftover compartment size", free_cell_default)

  rng_seed = ask_int("Enter random seed", defaults.rng_seed, 1)
  layout_attempts = ask_int("Enter number of layout attempts", defaults.layout_attempts, 1)
  per_item_attempts = ask_int("Enter number of attempts per cluster group", defaults.per_item_attempts, 1)

  items, compartment_specs = ask_cluster_items(defaults.compartments)

  defaults.outer_length = outer_length
  defaults.outer_width = outer_width
  defaults.outer_height = outer_height
  defaults.inner_wall_height = inner_wall_height
  defaults.outer_wall_thickness = outer_wall_thickness
  defaults.inner_wall_thickness = inner_wall_thickness
  defaults.bottom_thickness = bottom_thickness
  defaults.outer_corner_radius = 0.0
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
    domain = Rect(0.0, 0.0, inner_length, inner_width)
    free_rects = clip_free_rects_to_domain(free_rects, domain)

  requested_cavities, free_cavities, gap_adjustments = build_all_cavities(
    placed_clusters=placed_clusters,
    free_rects=free_rects,
    inner_wall_thickness=inner_wall_thickness,
    free_cell_size=free_cell_size,
    domain=domain
  )
  requested_compartments, free_compartments = build_compartment_placements(
    placed_clusters,
    requested_cavities,
    free_cavities
  )
  all_compartments = requested_compartments + free_compartments
  overlaps = find_overlapping_compartments(all_compartments)
  if overlaps:
    print("")
    print("Error: overlapping compartments were generated; export aborted.")
    for first_number, second_number, overlap_x, overlap_y in overlaps[:12]:
      print(
        f"  overlap between compartments {first_number} and {second_number}: "
        f"{overlap_x:.3f} x {overlap_y:.3f} mm"
      )
    if len(overlaps) > 12:
      print(f"  ... and {len(overlaps) - 12} more overlaps")
    return
  compartment_label_texts = build_compartment_primary_labels(all_compartments)
  secondary_label_texts = build_compartment_secondary_labels(all_compartments)

  label_boxes, label_glyphs = build_compartment_label_boxes(
    [Rect(compartment.x, compartment.y, compartment.w, compartment.h) for compartment in all_compartments],
    bottom_thickness,
    compartment_label_texts=compartment_label_texts,
    secondary_label_texts=secondary_label_texts
  )

  scad_text = make_scad(
    outer_length=outer_length,
    outer_width=outer_width,
    outer_height=outer_height,
    inner_length=inner_length,
    inner_width=inner_width,
    inner_height=inner_height,
    inner_wall_height=inner_wall_height,
    outer_wall_thickness=outer_wall_thickness,
    inner_wall_thickness=inner_wall_thickness,
    bottom_thickness=bottom_thickness,
    outer_corner_radius=outer_corner_radius,
    placed_clusters=placed_clusters,
    requested_compartments=requested_compartments,
    free_compartments=free_compartments,
    label_boxes=label_boxes,
    label_glyphs=label_glyphs
  )

  output_path = Path(f"{project_name}_box.scad")

  with output_path.open("w", encoding="utf-8") as handle:
    handle.write(scad_text)

  stl_path = Path(f"{project_name}_box.stl")
  stl_export_method = export_stl(
    stl_path=stl_path,
    outer_length=outer_length,
    outer_width=outer_width,
    outer_height=outer_height,
    inner_length=inner_length,
    inner_width=inner_width,
    inner_height=inner_height,
    inner_wall_height=inner_wall_height,
    outer_wall_thickness=outer_wall_thickness,
    inner_wall_thickness=inner_wall_thickness,
    bottom_thickness=bottom_thickness,
    outer_corner_radius=outer_corner_radius,
    compartments=all_compartments,
    label_boxes=label_boxes
  )

  print_cluster_summary(placed_clusters)
  print_cavity_summary(requested_cavities, free_cavities)
  print_gap_adjustments(gap_adjustments)

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
  