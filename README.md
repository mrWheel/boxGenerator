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

## What Do These Scripts Do?

**boxGenerator.py** is designed for makers who want to create functional storage boxes without manually 
calculating every dimension. The script:

1. **Collects configuration** through interactive prompts (box dimensions, wall thicknesses, compartment specifications)
2. **Optimizes compartment layout** using an advanced bin-packing algorithm that:
   - Attempts multiple layout strategies (default 120 attempts)
   - Automatically tests different orientations (horizontal/vertical)
   - May rotate compartments when that improves the fit
   - May shrink a requested compartment up to 10% per axis to make a layout possible
   - May grow a compartment to absorb otherwise useless leftover strips
   - Minimizes fragmentation for optimal usability
3. **Generates 3D models**:
   - `{projectname}_box.scad` - OpenSCAD file ready for rendering and export
   - `{projectname}_box.stl` - Ready-to-print STL file
4. **Adds labels** - Auto-generated pixel labels per compartment:
   - Small compartment number
   - Small requested/derived size label (rounded integer format, e.g. `32x24`)
   - `+` when a compartment grew, `-` when it shrank, `+-` when both happened on different axes
5. **Saves settings** - Stores all parameters in `.boxGenerator.{projectname}.json` for reuse

**gridLayoutGenerator.py** is a grid-first variant for quick layouts with fixed grid cells. It:

1. **Asks for grid parameters**:
   - `gridSize` in mm
   - complete outer box size as `LxWxH`
   - `outerWall`, `innerWall`, `bottom thickness`, `inner wall height`
2. **Asks for compartment requirements** repeatedly:
   - grid size in cells (for example `1x1`, `2x3`, `4x2`)
   - count per type
3. **Fills the grid first** without wall calculations, then applies wall geometry afterward
4. **Reports fit problems** when requested compartments do not fully fit
5. **Fills remaining cells** with `1x1` leftovers if everything else fits
6. **Generates output**:
   - `{projectname}.scad`
   - `{projectname}.stl`
   - `.gridLayout.{projectname}.json`

## Requirements

- **Python 3.8+** (no external packages required!)
- Optional: [OpenSCAD](https://openscad.org/) to view/edit `.scad` files
- Optional: Slicer software (Cura, PrusaSlicer, bambuStudio, etc.) for 3D printing

## Usage

### Basic Steps

```bash
./boxGenerator.py
```

Or explicitly with Python:

```bash
python3 boxGenerator.py
```

Grid-based generator:

```bash
./gridLayoutGenerator.py
```

Or:

```bash
python3 gridLayoutGenerator.py
```

### Quick Start (boxGenerator example profile)

Use the included example profile file:

`.boxGenerator._boxGeneratorTest.json`

Then run:

```bash
./boxGenerator.py
```

And choose project:

`_boxGeneratorTest`

### Interactive Menu

The script guides you through:

1. **Project selection** - Choose existing project or create new one
2. **Box dimensions** - Outer length × width × height (mm)
   - Example: `300x200x80`
   - The usable inner area is derived automatically from the wall and bottom thicknesses
3. **Material parameters**:
   - Outer wall thickness
   - Inner divider thickness
   - Bottom thickness
   - Corner radius (rounding)
4. **Compartments** - Define compartment groups:
   - Size (length × width per cell)
   - Number of cells
   - Cluster size (how cells group together)
   - Placement preference (random/front/back)
   - Lateral preference (left/center/right, if applicable)
5. **Pack parameters** - Optionally adjust:
   - Random seed (reproducibility)
   - Layout attempts
   - Attempts per cluster
6. **Free space** - Divide remaining space into smaller compartments?
   - Leftover strips are automatically distributed across neighboring fill compartments to avoid unusable gaps
   - Progress output shows which compartment numbers are still missing during each packing attempt

### Advanced Options

#### Erase Project Defaults
```bash
./boxGenerator.py --erase
```
Removes saved settings before restart.

#### Quick Start with Defaults
After initial configuration, the script automatically remembers your project. Press Enter to reuse default values.

## Output Files

### {projectname}.scad
 Complete OpenSCAD model with:
- Rounded outer shell
- Compartments generated individually with `makeCompartment(nr, posX, posY, sizeX, sizeY)`
- Compartment comments with requested size and adjustment marker information
- Small dual labels inside each compartment (number + size)

**Customization options in OpenSCAD:**
- Modify `$fn` for quality/smoothness
- Add features (label holes, snap tabs, etc.)
- Render to STL via OpenSCAD GUI

### {projectname}.stl

Direct 3D-printable binary STL file.
**Note:** Corner rounding is exact in OpenSCAD but simplified in STL (rectangular). For ultimate quality: render the `.scad` file in OpenSCAD, then re-export to STL.

### .boxGenerator.{projectname}.json
Saved configuration (hidden file on Unix/Mac):
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
  "compartments": [...]
}
```

## Key Concepts

### Cluster Size
Determines how compartments are grouped. Example:
- 8 cells of 25×30, cluster size 3 → groups of 3, 3, and 2 cells

### Placement Preferences
- **Random** - Algorithm chooses optimal placement
- **Front/Back** - Align cells to front or back wall
- **Left/Right/Center** - Lateral preference (works with front/back)

### Fragmentation
The algorithm selects best-performing layouts based on:
1. Fewest free regions (lower = less fragmentation)
2. Smallest total free area (tighter packing)
3. Earliest successful attempt (determinism)

### Random Seed
Default: 12345. Same seed = same layout. Change for different attempts.

## Troubleshooting

### "Total compartment area is larger than inner box floor area"
**Cause:** Your compartments don't fit.  
**Solution:**
- Increase box size (length/width)
- Reduce compartment dimensions
- Decrease number of compartments
- Script provides suggestions

### "Not all cluster groups could be placed"
**Cause:** Layout cannot fit all compartments in available space.  
**Solution:**
- Increase `layout_attempts` (127, 256, ...)
- Increase `per_item_attempts` (100, 300, ...)
- Change random seed to try different pattern
- Reduce compartment dimensions
- Watch the progress line for the current missing compartment numbers

### Output looks wrong in OpenSCAD
- Check if OpenSCAD is updated
- Add `$fn = 128` for better rendering
- Re-export to STL (OpenSCAD renders internally)

## Examples

### Small Parts Organizer
```
Dimensions: 150x100x50
Outer wall: 1.5
Inner dividers: 1.0
Bottom: 2.0
```

Add compartments:
```
Type 1: 25x20, 12 cells, cluster 3
Type 2: 15x15, 8 cells, cluster 4
```

### Large Tool Box
```
Dimensions: 400x300x150
Outer wall: 3.0
Inner dividers: 2.0
Bottom: 3.0
Corners: 15.0 (for durability)
```

Front-left arrangement:
```
Type 1: 50x60, 4 cells, cluster 2, front/left
Type 2: 40x40, 6 cells, cluster 3, front/center
Type 3: 100x100, 2 cells, cluster 1, back/random
```

## Architecture Highlights

### Data Structures
- `Rect` - 2D rectangles (position & dimensions)
- `ClusterItem` - Unplaced compartment group
- `PlacedCluster` - Position + orientation + metadata
- `CompartmentSpec` - User compartment description

### Packing Algorithm
1. Sort clusters by footprint (large → small)
2. For each layout attempt:
   - Create free-space list = entire domain
   - For each cluster: try N random positions/orientations
   - Select placement with lowest fragmentation
   - Update free-space list
3. Choose best layout (most placed, then least fragmentation)

### OpenSCAD Generation
- **Outer shell** - Rounded rectangle, linearly extruded
- **Main cavity** - Large rectangle subtracting the interior from the outer shell
- **Compartments** - Generated one by one from the final compartment placements via `makeCompartment(...)`
- **Labels** - Generated pixel fonts with two small lines per compartment (number + rounded size)

### Label Format
- Compartment number: sequential `1..N`
- Size line: rounded integer format `XxY` (example: `32.5x24.0` is shown as `32x24`)
- Adjustment marker: `+`, `-`, or `+-` when the actual compartment differs from the requested size
- Labels use a small fixed pixel size and only shrink further when a compartment is too small

## Advanced Configuration

### Reproducible Example Project
The repository includes a ready-to-run example profile:

`.boxGenerator._boxGeneratorTest.json`

Select the project `_boxGeneratorTest` in the interactive menu to reproduce a layout where a tiny strip between two requested compartments is absorbed.

The CLI now reports this explicitly in an **Absorbed tiny gaps between requested cavities** section, including axis, involved cavity indices, gap size, and growth per cavity.

### Free Space Compartments
Want to divide unused space into smaller compartments? Specify a "free cell size":
```
Free space size: 20x20
```
This fills all remaining open space with 20×20 cells.

If a leftover strip cannot form a useful extra compartment, the script automatically spreads that strip over adjacent free-space compartments.

The same rule applies to strips trapped between two facing requested compartments: neighboring compartments absorb that strip automatically while keeping divider logic intact.

Narrow free-space strips are now absorbed aggressively into adjacent compartments (including edge-adjacent cases), so thin sliver compartments are minimized.

### Adjust Wall Height
Default: same height as box. Change for shallower walls:
```
Inner wall height: 40 (while box is 80 mm tall)
```

## Exporting for 3D Printing

1. **OpenSCAD route (best quality if corners matter):**
   - Open `{projectname}_box.scad` in OpenSCAD
   - Press F5 to render
   - File → Export as STL

2. **Direct STL route:**
   - Use `{projectname}.stl` directly
   - Note: corners are simplified

3. **Slicer preparation:**
   - Import STL into your slicer
   - Check for holes/problems (shouldn't be any)
   - Configure printer settings (infill, temperature, etc.)
   - Generate G-code and print!

## License & Attribution

This project uses only standard Python libraries. No external dependencies.

---

**Tip:** Keep your favorite settings! They're automatically saved. You can load and modify projects later.
