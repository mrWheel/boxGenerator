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

## What Does This Script Do?

**boxGenerator.py** is designed for makers who want to create functional storage boxes without manually 
calculating every dimension. The script:

1. **Collects configuration** through interactive prompts (box dimensions, wall thicknesses, compartment specifications)
2. **Optimizes compartment layout** using an advanced bin-packing algorithm that:
   - Attempts multiple layout strategies (default 120 attempts)
   - Automatically tests different orientations (horizontal/vertical)
   - Minimizes fragmentation for optimal usability
3. **Generates 3D models**:
   - `{projectname}_box.scad` - OpenSCAD file ready for rendering and export
   - `{projectname}_box.stl` - Ready-to-print STL file
4. **Adds labels** - Auto-generated compartment dimensions for easy identification
5. **Saves settings** - Stores all parameters in `.boxGenerator.{projectname}.json` for reuse

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

### Interactive Menu

The script guides you through:

1. **Project selection** - Choose existing project or create new one
2. **Box dimensions** - Inner length × width × height (mm)
   - Example: `300x200x80`
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

### Advanced Options

#### Erase Project Defaults
```bash
./boxGenerator.py --erase
```
Removes saved settings before restart.

#### Quick Start with Defaults
After initial configuration, the script automatically remembers your project. Press Enter to reuse default values.

## Output Files

### {projectname}_box.scad
 Complete OpenSCAD model with:
- Rounded outer shell
- Compartments defined as cavities (subtracted)
- Internal divider walls
- Labeled compartment groups (% comments)

**Customization options in OpenSCAD:**
- Modify `$fn` for quality/smoothness
- Add features (label holes, snap tabs, etc.)
- Render to STL via OpenSCAD GUI

### {projectname}_box.stl

Direct 3D-printable binary STL file.
**Note:** Corner rounding is exact in OpenSCAD but simplified in STL (rectangular). For ultimate quality: render the `.scad` file in OpenSCAD, then re-export to STL.

### .boxGenerator.{projectname}.json
Saved configuration (hidden file on Unix/Mac):
```json
{
  "inner_length": 300.0,
  "inner_width": 200.0,
  "outer_wall_thickness": 2.0,
Complete OpenSCAD model with:
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
- **Main cavity** - Large rectangle subtracting interior
- **Internal walls** - Rectangles placed between compartments
- **Labels** - Generated pixel fonts with dimensions

## Advanced Configuration

### Free Space Compartments
Want to divide unused space into smaller compartments? Specify a "free cell size":
```
Free space size: 20x20
```
This fills all remaining open space with 20×20 cells.

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
   - Use `{projectname}_box.stl` directly
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
