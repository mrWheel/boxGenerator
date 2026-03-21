# Box Generator

A Python tool that generates fully customizable 3D-printable storage boxes with intelligent compartment layout optimization.

# Disclaimer
This software is developed incrementally. That means I have no clue how it works (though it mostly does).

If you have questions about this software, it will probably take you just as long to figure things out 
as it would take me. So I’d prefer that you investigate it yourself.

Having said that Don’t Even Think About Using It

Seriously. Don’t.

Using this software may injure or kill you during construction, burn your house down while in use, and 
then—just to be thorough—explode afterward.

This is not a joke. This project may use lethal voltages. If you are not a qualified software engineer, 
close this repository, step away from the terminal, and make yourself a cup of tea.

If you decide to ignore all of the above and use it anyway, you do so entirely at your own risk. You are 
fully responsible for taking proper safety precautions. I take zero responsibility for anything that
happens—electrically, mechanically, chemically, spiritually, or otherwise.

Also, full disclosure: I am not a qualified software engineer. I provide no guarantees, no warranties, 
and absolutely no assurance that this software is correct, safe, or suitable for any purpose whatsoever.

## Overview

This repository contains two related Python programs that generate compartmented storage boxes:

1. `boxGenerator.py`
2. `gridLayoutGenerator.py`

They share the same overall goal:

1. ask for box and compartment requirements,
2. search for a usable layout,
3. generate `.scad`, `.stl`, and project JSON files,
4. keep project defaults so a later run can reuse them.

They differ mainly in how the layout is defined and how much freedom the packing algorithm has.

## Program Comparison

| Topic | `boxGenerator.py` | `gridLayoutGenerator.py` |
| --- | --- | --- |
| Input model | Physical sizes in mm | Fixed grid, compartment sizes in grid cells |
| Main use case | Flexible packing with more automatic optimization | Fast deterministic layouts on a discrete grid |
| Search strategy | Multi-attempt random packing of cluster groups | Multi-attempt grid packing with rotation and bounded backtracking |
| Remaining free space | Optional leftover compartment size in mm | Automatic `1x1` grid leftovers when everything fits |
| Compartment grouping | Supports cell counts and cluster sizes | Directly requests repeated `NxM` grid compartments |
| Placement preferences | Random/front/back plus lateral preference | No directional preference prompts; solver decides placement |
| Geometry freedom | May shrink/grow requested cavities in some cases | No size distortion; only rotate `NxM` to `MxN` |
| Output files | `{project}.scad`, `{project}.stl`, `.boxGenerator.{project}.json` | `{project}.scad`, `{project}.stl`, `.gridLayout.{project}.json` |

## Shared Behavior

Both programs:

1. are interactive CLI tools,
2. store project defaults in hidden JSON files,
3. write OpenSCAD and STL output,
4. generate internal labels in each compartment,
5. support reproducibility through a random seed,
6. show packing progress over multiple attempts,
7. allow rerunning the same project by pressing Enter on default prompts.

## Requirements

1. Python 3.8+
2. No external Python packages
3. Optional: OpenSCAD for viewing or re-exporting `.scad`
4. Optional: slicer software for printing

## Quick Start

Run either tool directly:

```bash
./boxGenerator.py
./gridLayoutGenerator.py
```

Or via Python:

```bash
python3 boxGenerator.py
python3 gridLayoutGenerator.py
```

Included example profile for `boxGenerator.py`:

`.boxGenerator._boxGeneratorTest.json`

Choose project `_boxGeneratorTest` in the menu.

## boxGenerator.py

### Purpose

`boxGenerator.py` is the more flexible generator. It starts from physical compartment cell sizes in mm and tries many layout attempts to fit grouped compartments inside the available box floor.

### Inputs

The program asks for:

1. project selection,
2. outer box size in mm,
3. outer wall thickness,
4. inner wall thickness,
5. bottom thickness,
6. inner wall height,
7. random seed,
8. number of layout attempts,
9. number of attempts per cluster group,
10. optional leftover compartment size,
11. compartment specifications.

Each compartment specification contains:

1. cell width and height in mm,
2. number of cells,
3. cluster size,
4. placement mode,
5. lateral mode.

### Packing Model

The program:

1. converts requested compartments into cluster groups,
2. sorts larger groups before smaller ones,
3. tries many complete layout attempts,
4. tries many candidate positions/orientations per cluster group,
5. chooses lower-fragmentation candidates,
6. keeps the best result over all attempts.

Important behaviors:

1. compartments may rotate when useful,
2. compartments may shrink up to a limited amount to improve fit,
3. tiny unusable strips may be absorbed by neighboring compartments,
4. leftover free space may optionally be divided into extra compartments.

### Progress Output

During search it prints lines like:

```text
Packing progress: attempt 40/120, best placed compartments 17/18, current missing compartments C04, C11
```

That line reports:

1. current global attempt,
2. best placement count found so far,
3. what is still missing in the current attempt.

### Outputs

`boxGenerator.py` writes:

1. `{project}.scad`
2. `{project}.stl`
3. `.boxGenerator.{project}.json`

The JSON stores the project defaults and enough information to rerun the same configuration.

## gridLayoutGenerator.py

### Purpose

`gridLayoutGenerator.py` is the grid-first generator. The user works in whole grid cells such as `2x3`, `4x2`, `1x1`, while the script converts those cell counts to mm only after the grid layout is solved.

### Inputs

The program asks for:

1. project selection,
2. layout mode,
3. random seed,
4. number of layout attempts,
5. number of attempts per cluster group,
6. grid parameters,
7. box size parameters,
8. wall parameters,
9. compartment specifications.

Layout mode can be:

1. fixed grid,
2. fixed box length with suggested grid sizes and valid widths,
3. fixed box width with suggested grid sizes and valid lengths.

Compartment input is a repeated `NxM` plus count loop.

### Packing Model

The program:

1. expands requested compartment counts into a queue of grid rectangles,
2. sorts and shuffles that queue across multiple attempts,
3. allows each requested size to be placed in both orientations (`NxM` and `MxN`),
4. scores candidate placements by how much they fragment the remaining free grid,
5. performs bounded backtracking inside each attempt instead of only greedy first-fit,
6. keeps the best full-attempt result.

Important behaviors:

1. grid cells never shrink or grow,
2. rotation is allowed,
3. if all requested compartments fit, remaining cells are filled as `1x1` leftovers,
4. labels show the compartment identifier plus the originally requested grid size such as `2 x 3`.

### Progress Output

During search it prints lines like:

```text
Packing progress: attempt 24/100, best placed compartments 14/15, current missing compartments spec 04 x1
```

That line reports:

1. current global attempt,
2. best placed count found so far,
3. which requested spec counts are still missing in the current attempt.

### Outputs

`gridLayoutGenerator.py` writes:

1. `{project}.scad`
2. `{project}.stl`
3. `.gridLayout.{project}.json`

The JSON stores:

1. project mode,
2. grid size,
3. random seed,
4. layout-attempt settings,
5. box dimensions,
6. wall dimensions,
7. requested compartment specs,
8. missing counts,
9. final placements.

## File Contracts

### boxGenerator JSON

Typical fields:

```json
{
  "outer_length": 300.0,
  "outer_width": 200.0,
  "outer_height": 80.0,
  "outer_wall_thickness": 2.0,
  "inner_wall_thickness": 2.0,
  "bottom_thickness": 2.0,
  "outer_corner_radius": 10.0,
  "rng_seed": 12345,
  "layout_attempts": 120,
  "per_item_attempts": 50,
  "free_cell_w": 20.0,
  "free_cell_h": 20.0,
  "compartments": []
}
```

### gridLayoutGenerator JSON

Typical fields:

```json
{
  "project": "example",
  "mode": 3,
  "grid_size": 17.9,
  "rng_seed": 12345,
  "layout_attempts": 100,
  "per_item_attempts": 50,
  "outer_length": 250.7,
  "outer_width": 197.0,
  "outer_height": 50.0,
  "outer_wall": 1.0,
  "inner_wall": 1.0,
  "bottom_thickness": 1.2,
  "inner_wall_height": 40.0,
  "grid_cols": 14,
  "grid_rows": 11,
  "compartments": [],
  "missing_by_spec": {},
  "placements": []
}
```

### Placement Records in gridLayoutGenerator

Each placement stores both the requested grid size and the actual placed orientation.

Example:

```json
{
  "label": "C10",
  "is_leftover": false,
  "requested_w_cells": 2,
  "requested_h_cells": 3,
  "x_cell": 4,
  "y_cell": 9,
  "w_cells": 3,
  "h_cells": 2
}
```

That means the user requested `2x3`, but the solver placed it rotated as `3x2`.

## AI Reimplementation Brief

If an AI has to rewrite both tools from scratch, use this section as the minimum functional contract.

### Shared Requirements

1. Language: Python 3 with standard library only.
2. Interface: interactive CLI.
3. Project persistence: hidden JSON file per project.
4. Output: one `.scad` file and one `.stl` file per project.
5. Geometry: rectangular outer shell, inner cavity, divider walls, simple label geometry.
6. Determinism: same seed and same inputs must reproduce the same search behavior.

### Reimplement boxGenerator.py

The rewritten script must:

1. manage projects using `.boxGenerator.{project}.json`,
2. ask for physical box dimensions and wall parameters,
3. ask for compartment groups using mm-based cell sizes and cluster sizes,
4. support random seed, layout attempts, attempts per cluster group,
5. support optional leftover compartment size,
6. perform multi-attempt randomized packing of cluster groups,
7. support orientation changes,
8. allow controlled size adjustments when needed,
9. prefer layouts with fewer missing groups and less fragmentation,
10. print periodic packing progress,
11. export `{project}.scad` and `{project}.stl`,
12. generate labels that include compartment number and size/adjustment information.

### Reimplement gridLayoutGenerator.py

The rewritten script must:

1. manage projects using `.gridLayout.{project}.json`,
2. support three input modes: fixed grid, fixed box length, fixed box width,
3. support suggestion lists for valid dimensions when box length or width is fixed,
4. remember defaults for mode, seed, attempts, walls, box size, and compartment list,
5. ask for grid-based compartment specs as repeated `NxM` plus count,
6. accept count `0` to skip a remembered spec,
7. allow placement in both orientations,
8. run multiple packing attempts,
9. use candidate scoring plus bounded backtracking within an attempt,
10. print periodic packing progress,
11. fill leftover cells with `1x1` only when all requested compartments fit,
12. export `{project}.scad`, `{project}.stl`, and `.gridLayout.{project}.json`,
13. label compartments with the compartment identifier and the originally requested grid size written as `N x M`,
14. show the rounded grid size in the largest compartment label.

### Non-Goals

A rewrite does not need to preserve:

1. exact internal function names,
2. exact prompt wording,
3. exact triangle order in STL,
4. exact OpenSCAD formatting.

A rewrite does need to preserve:

1. the interactive workflow,
2. the saved project data model,
3. deterministic search from seed,
4. the practical layout behavior,
5. the emitted file types and overall geometry meaning.

## Copyable AI Prompt

Use the text below when asking an AI to recreate these tools.

```text
Rewrite two Python CLI programs named boxGenerator.py and gridLayoutGenerator.py.

General constraints:
- Python 3 standard library only
- Interactive CLI
- Save per-project defaults in hidden JSON files
- Generate {project}.scad and {project}.stl
- Deterministic behavior for the same random seed and inputs

Program 1: boxGenerator.py
- Input model is physical sizes in mm
- Ask for project, box dimensions, wall dimensions, random seed, layout attempts, attempts per cluster group, optional leftover compartment size, and compartment group definitions
- Compartment group definitions must include cell width, cell height, count, cluster size, placement mode, and lateral mode
- Use a multi-attempt randomized packing algorithm
- Allow orientation changes
- Allow limited size adjustment when needed
- Prefer layouts with fewer missing groups and less fragmentation
- Print periodic packing progress during attempts
- Save defaults to .boxGenerator.{project}.json

Program 2: gridLayoutGenerator.py
- Input model is grid-based
- Support three layout modes: fixed grid, fixed box length, fixed box width
- Ask for project, mode, random seed, layout attempts, attempts per cluster group, box/grid values, wall values, and repeated compartment specs in NxM plus count form
- Accept count 0 to skip a remembered compartment spec
- Allow both orientations NxM and MxN
- Use multi-attempt search with candidate scoring and bounded backtracking
- Print periodic packing progress during attempts
- Fill remaining cells with 1x1 leftovers only if all requested compartments fit
- Save defaults and placements to .gridLayout.{project}.json
- Labels must show the compartment identifier and the originally requested grid size formatted like N x M
- The largest compartment must also show the rounded grid size

Outputs for both:
- OpenSCAD geometry for outer shell, cavity, walls, and labels
- STL export generated directly by Python
- Project JSON file with enough information to rerun the same project
```

## Troubleshooting

### Requested compartments do not fit

Try one or more of these:

1. increase box size,
2. reduce counts,
3. increase `layout_attempts`,
4. increase `per_item_attempts`,
5. change `rng_seed`.

### Output looks different from expected

Check:

1. project JSON defaults,
2. current random seed,
3. attempt counts,
4. whether a compartment was rotated,
5. whether `boxGenerator.py` grew or shrank a compartment.

### OpenSCAD vs STL differences

The `.scad` file is the more editable source. If visual quality matters, open the `.scad` in OpenSCAD and export STL from there.

## License & Attribution

This project uses only standard Python libraries. No external dependencies.
