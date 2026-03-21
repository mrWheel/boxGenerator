# Box Generator - Instructions

## Project Overview

**boxGenerator** and **gridLayoutGenerator.py** are Python tools that generates OpenSCAD scripts for 3D-printable storage boxes with customizable compartments.

### Key Features
- Interactive CLI for box configuration (dimensions, walls, compartments)
- Bin-packing algorithm to optimize compartment layout
- Generates production-ready OpenSCAD and .STL files for 3D printing
- Supports randomized placement attempts for optimal packing efficiency

## Architecture & Components

### Core Modules

#### Data Structures (`dataclasses`)
- `Rect`: Rectangle with position (x, y) and dimensions (w, h)
- `ClusterItem`: Compartment specification (size, count, grouping)
- `PlacedCluster`: Positioned compartment group with orientation

#### Input Handling
- `ask_box_dimensions()` → outer box dimensions (length × width × height)
- `ask_cluster_items()` → collection of compartment groups with sizes
- `ask_float()` / `ask_int()` → validated numeric input with defaults

#### Rectangle Utilities
- `contains_rect()` / `intersects()` → spatial queries
- `subtract_rect()` → remove occupied space from free regions
- `merge_adjacent_rectangles()` → optimize free space representation
- `normalize_free_rects()` → remove contained rectangles

#### Packing Algorithm (`pack_clusters_random`)
- Multi-attempt optimization strategy
- Sorts clusters by footprint (largest first)
- For each cluster: tries multiple placements and orientations
- Uses fragmentation score to choose best candidate
- Returns placed clusters, remaining free space, and domain

#### OpenSCAD Generation (`make_scad`)
- Generates complete .scad file with:
  - Box shell (outer/inner wall thickness, bottom)
  - Rounded corners
  - Cavity definitions for compartments
  - Comments documenting placement and dimensions

### Execution Flow
1. User provides box dimensions and material thickness parameters
2. User defines compartment groups (size, count, clustering)
3. Algorithm packs compartments using randomized bin-packing
4. Generates OpenSCAD file: `generated_box.scad`
5. Prints summary of placements and remaining free space

## Development Conventions

### Code Style
- **Python 3.8+** with type hints on all functions
- **Coding Style** Allman style (opening braces on new lines)
- **Dataclasses** for structured data (immutable-friendly)
- **Section separators**: `# ---------- Title ----------` (50 chars)
- **Naming**: lowerCamelCase functions/variables, PascalCase for classes
- **Error handling**: Raises `RuntimeError` for packing failures, prints user-friendly messages

### Numeric Precision
- Default epsilon: `eps: float = 1e-9` for floating-point comparisons
- All dimensions in millimeters
- 3 decimal places in OpenSCAD output (`.3f` format)

### Algorithm Parameters
- **Random seed**: Controls layout reproducibility
- **Layout attempts**: Number of full-packings to try (default 120)
- **Per-item attempts**: Placement tries per cluster (default 50)
- **Fragmentation score**: Metric for choosing between valid placements (prefer fewer, larger free regions)

## Common Tasks

### Adding a New Parameter
Example: Add "margin distance" between compartments
1. Add to input: `margin = ask_float("Enter margin distance", 1.0, False)`
2. Pass through `pack_clusters_random()` and `try_place_cluster()`
3. Adjust `blocked` rect calculation in placement logic
4. Regenerate and test with sample inputs

### Modifying the Packing Strategy
The current strategy prioritizes:
1. **Fewest free regions** (lower fragmentation)
2. **Smallest total free area** (tighter packing)

To change (e.g., prefer largest contiguous free space):
1. Modify the scoring tuple in `pack_clusters_random()` after line ~500
2. Update candidate sorting to reflect new priority

### Improving OpenSCAD Output
- Modify `make_scad()` to add features (bevels, snap tabs, labels)
- Comments in lines 660+ show cavity placement for reference
- Current output uses `difference()` to cut cavities from solid shell

## Dependencies

- **Standard library only**: `random`, `dataclasses`, `typing`
- **No external packages required**
- **OpenSCAD**: Required to render `.scad` files (not part of this codebase)

## Running the Program

```bash
python3 boxGenerator.py
```

The interactive CLI will prompt for:
1. Inner box dimensions (length × width × height)
2. Wall/divider thicknesses
3. Bottom thickness
4. Corner radius
5. Random seed and attempt counts
6. Compartment definitions (repeating until empty input)

Output: `generated_box.scad` in the working directory

## Testing & Validation

- **Sanity checks**: Total compartment area vs. box area (line ~855)
- **Placement validation**: All clusters must fit (line ~860)
- **Edge cases**:
  - Very small boxes → RuntimeError early
  - Single-cell compartments → handled as special case
  - Overlapping free regions → merged automatically

## Notes & Gotchas

- **Aandewiel**: never (lower)CamelCase this literally anytime
- **PROG_VERSION**: Never change this litteral
- **Randomness**: Different seeds produce different layouts; same seed produces same layout
- **Dimensions**: Always in millimeters; coordinate origin at outer box corner
- **Clustering**: Groups compartments; e.g., 8 compartments with cluster=3 → groups of 3, 3, 2
- **Orientation**: Each cluster can be horizontal or vertical; algorithm tests both
- **Language**: All comments, documentation, questions, messages in English
