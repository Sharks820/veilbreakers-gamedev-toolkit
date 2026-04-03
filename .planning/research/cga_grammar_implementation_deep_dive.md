# CGA Shape Grammar for Procedural Building Generation -- Ultra Deep Dive

**Researched:** 2026-04-02
**Domain:** CGA shape grammar, procedural facade composition, recursive building generation
**Confidence:** HIGH (original paper, official CityEngine docs, multiple open-source implementations, existing VB codebase audit)

---

## Executive Summary

CGA (Computer Generated Architecture) shape grammar, introduced by Muller/Wonka/Haegler/Ulmer/Van Gool at SIGGRAPH 2006, is the de-facto standard for procedural building generation. CityEngine commercialized it; every major procedural city tool since (Houdini City Tools, Unity CityEngine SDK/Vitruvio, ShapeML) derives from its core ideas. The grammar is remarkably simple in concept -- a shape tree where rules recursively replace parent shapes with subdivided children until only terminal geometry remains -- but powerful enough to generate entire cities.

The existing VeilBreakers `_building_grammar.py` already has the *skeleton* of this approach (BuildingSpec with operations, 5 style configs, facade rules) but lacks the recursive shape tree that makes CGA powerful. Currently it generates geometry imperatively (foundation box, wall boxes, roof box, detail cubes) rather than through grammar derivation. The upgrade path is clear: implement a lightweight shape tree with split/repeat/comp operations, wire it to the existing 175 modular kit pieces and 9 AAA quality generators, and define per-building-type rulesets.

**The key insight: CGA is not complex to implement. The core engine is ~300-400 lines of Python. The real work is writing good rulesets (the grammar rules themselves) and wiring terminals to quality geometry.**

---

## MISSION 1: The CGA Grammar Paper (Muller/Wonka 2006)

### 1.1 Complete Grammar Rule Syntax

A CGA rule has the form:

```
PredecessorSymbol --> operation1 operation2 ... SuccessorSymbol
```

Or with multiple successors (branching):

```
PredecessorSymbol --> operation1 SuccessorA operation2 SuccessorB
```

**Key syntactic elements:**

| Element | Syntax | Meaning |
|---------|--------|---------|
| Rule definition | `Symbol --> body` | Replace Symbol with body |
| Terminal | `Symbol.` (dot suffix) | Leaf node, no further derivation |
| Stochastic | `Symbol --> 30% : A \| 70% : B` | Probabilistic rule selection |
| Conditional | `Symbol --> case cond : A else : B` | Condition-based selection |
| Attribute | `attr height = rand(10, 25)` | Per-shape parameter |

### 1.2 The Shape and Scope System

Every shape in the grammar tree has a **scope** -- an oriented bounding box defined by:

```
scope = {
    position: (tx, ty, tz),    # translation relative to parent pivot
    rotation: (rx, ry, rz),    # orientation (Euler angles)
    size:     (sx, sy, sz),    # dimensions along local axes
}
```

Plus a **pivot** (the local origin) and **geometry** (polygonal mesh, initially the full shape volume).

The scope is the fundamental abstraction -- all operations manipulate the scope, and child shapes inherit their parent's scope (modified by the operation that created them).

### 1.3 The Split Operation

The most important operation. Divides a shape along one axis into sub-shapes.

**Syntax:**
```
split(axis) { size1 : Op1 | size2 : Op2 | ... | sizeN : OpN }
```

**Axis:** `x` (horizontal/width), `y` (vertical/height), `z` (depth)

**Size types:**
- **Absolute** (no prefix): `3.0` = exactly 3 meters
- **Relative** (single quote): `'0.5` = 50% of parent scope along that axis
- **Floating** (tilde): `~3.0` = preferred 3m, will stretch/shrink to fill remainder

**Example -- split a facade into floors:**
```
Facade --> split(y) { 4.0 : GroundFloor | { ~3.5 : UpperFloor }* }
```
This puts a 4m ground floor at the bottom, then repeats ~3.5m upper floors to fill remaining height.

**How the repeat operator `*` works:**
When `{ pattern }*` is used, the pattern repeats as many times as it fits. Floating dimensions (`~`) adjust so the total fills the scope exactly. For a 15m facade:
- Ground floor: 4m (absolute)
- Remaining: 11m
- `~3.5` repeats 3 times: 3 x 3.667m = 11m (each adjusted from 3.5 to 3.667)

**How split handles remainder:**
- Absolute sizes are placed first
- Floating sizes split the remainder proportionally
- If absolute sizes exceed scope, shapes are clipped (or flagged as errors)

### 1.4 The Repeat Operation

A specialized split that evenly divides space:

```
split(x) { { ~tileWidth : Tile }* }
```

This is syntactic sugar for "repeat Tile across the x-axis at approximately tileWidth intervals, adjusting to fill evenly."

### 1.5 Component Split (comp)

Extracts faces from a 3D shape as separate 2D shapes, each with its own scope:

**Syntax:**
```
comp(f) { front : FrontFacade | back : BackFacade | side : SideFacade | top : Roof | bottom : Floor }
```

**Face selectors:**
| Selector | Meaning |
|----------|---------|
| `front` | Face with normal closest to -z (or scope-relative front) |
| `back` | Face with normal closest to +z |
| `left` | Normal closest to -x |
| `right` | Normal closest to +x |
| `top` | Normal closest to +y (upward) |
| `bottom` | Normal closest to -y (downward) |
| `side` | All vertical faces (front + back + left + right) |
| `all` | Every face |

**After comp, each face becomes a 2D shape** with scope aligned to the face plane:
- `scope.sx` = face width
- `scope.sy` = face height
- `scope.sz` = 0 (2D)
- Face normal becomes the new z-axis

This is how you go from a 3D building mass to individual facades that can be further split into floors and bays.

### 1.6 Scope Manipulation Operations

| Operation | Syntax | Effect |
|-----------|--------|--------|
| **Translate** | `t(tx, ty, tz)` | Move scope position |
| **Rotate** | `r(rx, ry, rz)` | Rotate scope orientation |
| **Scale** | `s(sx, sy, sz)` | Resize scope (absolute) |
| **Scale relative** | `s('rx, 'ry, 'rz)` | Resize scope (proportional) |
| **Center** | `center(axis)` | Center scope along axis |
| **Set position** | `setPivot(x, y, z)` | Set pivot origin |

**Scope inheritance:** When a rule creates child shapes, each child starts with the scope resulting from the parent's operations. This is how transforms cascade down the tree.

### 1.7 Occlusion Queries

CGA provides context-sensitive functions to prevent geometry conflicts:

**Functions:**
```
inside(target)    # Is current shape completely inside target?
overlaps(target)  # Does current shape partially overlap target?
touches(target)   # Does current shape touch/contact target?
```

**Target selectors:**
- `intra` -- check within same shape tree (same building)
- `inter` -- check across different shape trees (between buildings)
- `all` -- check everything

**Practical example -- don't place windows behind other geometry:**
```
WindowOpening -->
    case touches(intra) : Wall    # Occluded, make it a solid wall
    else : Window                 # Not occluded, place window
```

**Key constraint:** Occlusion tests only work against closed (watertight) meshes. They exclude parent/ancestor shapes to avoid false positives from the hierarchy itself.

**Performance note:** Occlusion queries are expensive. CityEngine only computes them when explicitly requested in CGA code. For our Python implementation, we can do simpler AABB overlap tests rather than full mesh intersection.

### 1.8 Terminal Geometry Mapping

At leaf nodes, geometry is inserted into the scene:

**Insert operation:**
```
i("path/to/asset.obj")    # Insert mesh at current scope
```

The inserted mesh is scaled and positioned to fit the current scope. This is how the grammar connects to artist-authored assets -- the grammar positions and sizes the scope, then `i()` places the actual mesh.

**Primitive insertion:**
```
primitiveCube()       # Fill scope with a box
primitiveCylinder()   # Fill scope with a cylinder
primitiveQuad()       # Fill scope with a flat quad
```

**The derivation terminates when:**
1. A terminal symbol is reached (Symbol. with dot)
2. An `i()` insert operation is executed
3. A primitive is created
4. No matching rule exists (implicit terminal)

---

## MISSION 2: CityEngine CGA Reference

### 2.1 Complete CGA Operation Catalog

**Geometry Creation:**
| Operation | Purpose |
|-----------|---------|
| `extrude(distance)` | Extend 2D footprint into 3D volume |
| `envelope(...)` | Create building envelope from lot |
| `roofGable(angle)` | Generate gable roof |
| `roofHip(angle)` | Generate hip roof (straight skeleton) |
| `roofPyramid(angle)` | Generate pyramid roof |
| `roofShed(angle)` | Generate single-slope shed roof |
| `taper(height)` | Taper shape to a point |
| `i(assetPath)` | Insert external mesh asset |
| `primitiveCube/Cylinder/Quad/Sphere/Cone/Disk` | Insert geometric primitives |

**Geometry Subdivision:**
| Operation | Purpose |
|-----------|---------|
| `split(axis) { ... }` | Divide shape along axis |
| `comp(type) { ... }` | Extract face/edge/vertex components |
| `setback(dist) { ... }` | Inset edges creating margins |
| `offset(dist)` | Shrink/grow 2D shape |
| `splitArea(axis) { ... }` | Split by area rather than distance |
| `innerRectangle(mode)` | Find largest inscribed rectangle |
| `scatter(type, count)` | Distribute points on surface |
| `shapeL/U/O(...)` | Create L/U/O shaped footprints |

**Transformations:**
| Operation | Purpose |
|-----------|---------|
| `t(x, y, z)` | Translate scope |
| `r(rx, ry, rz)` | Rotate scope |
| `s(sx, sy, sz)` | Scale scope |
| `center(axis)` | Center in parent scope |
| `mirror(axis)` | Mirror along axis |

**Texturing:**
| Operation | Purpose |
|-----------|---------|
| `setupProjection(uvSet, axisPlane, su, sv)` | Configure UV projection |
| `texture(path)` | Apply texture to current shape |
| `projectUV(uvSet)` | Project UVs onto geometry |
| `normalizeUV/rotateUV/scaleUV/translateUV/tileUV` | Manipulate UVs |

### 2.2 How Rules Chain Together

Rules apply top-down through the shape tree:

```
# 1. Start: 2D lot footprint
Lot --> extrude(height) Building

# 2. Decompose 3D mass into faces
Building --> comp(f) { front : Frontfacade | side : Sidefacade | top : Roof }

# 3. Split facade into floors
Frontfacade --> split(y) { 4 : Groundfloor | { ~3.5 : Floor }* }

# 4. Split floor into bays/tiles
Floor --> split(x) { ~0.5 : Wall | { ~4 : Tile }* | ~0.5 : Wall }

# 5. Place window in tile
Tile --> split(x) { ~1 : Wall | ~2 : WindowArea | ~1 : Wall }
         split(y) { ~1 : Wall | ~1.5 : Window | ~0.5 : Wall }

# 6. Terminal: insert window mesh
Window --> t(0, 0, -0.2) i("assets/window_gothic.obj")
```

**Key pattern: expand-then-divide.** Extrude a lot to create 3D volume, decompose into faces, split faces into floors, split floors into bays, split bays into elements, insert geometry at leaves.

### 2.3 Randomness/Probability in Rule Selection

```
# Stochastic rule: 30% chance of A, 20% of B, 50% of C
Shape -->
    30% : SuccessorA
    20% : SuccessorB
    else : SuccessorC

# Random attributes
attr height = rand(10, 25)
attr num_floors = rint(rand(2, 5))
attr facade_texture = fileRandom("facades/*.jpg")
```

Randomness is **seeded per shape** via the `seedian` attribute. This ensures reproducibility -- same seed produces same building every time.

### 2.4 Attribute Propagation

Attributes defined at the top of a rule file are inherited by all shapes in the tree. They can be overridden per-rule:

```
attr height = 15
attr floor_height = 3.5

Lot --> extrude(height) Building
Building --> comp(f) { side : Facade | top : Roof }
Facade --> split(y) { floor_height : GroundFloor | { ~floor_height : UpperFloor }* }
```

Attributes propagate downward through the shape tree. Child shapes see parent attributes unless the child rule redefines them.

### 2.5 LOD Handling

CityEngine uses conditional rules for LOD:

```
attr LOD = 1    # 0 = low, 1 = high

Window -->
    case LOD > 0 :
        t(0, 0, -0.2)
        s('1, '1, windowSetback)
        [ i("window_detail.obj") ]
    else :
        setupProjection(0, scope.xy, 1, 1)
        texture("window_flat.jpg")
```

At LOD 0: simple textured quad (816 polys for a building).
At LOD 1: full 3D window inserts (2,347 polys for same building).

### 2.6 Texture Mapping

```
# Project UVs onto a facade face
Facade -->
    setupProjection(0, scope.xy, 1.5, 1.5, 0, 0, 1)  # 1.5m repeat
    texture("facades/brick_white_02.jpg")
    projectUV(0)
```

The `setupProjection` maps UVs to scope dimensions. `scope.xy` means project along the face plane with specified repeat distances.

### 2.7 Irregular Lot Handling

CGA handles irregular lots through:
- `innerRectangle(mode)` -- finds the largest inscribed rectangle in a polygon
- `setback(dist)` -- insets edges to create margins
- `shapeL/U/O` -- creates L/U/O shaped footprints from rectangular inputs
- `offset(dist)` -- shrinks/grows the 2D polygon uniformly

For VeilBreakers, most building lots will be rectangular (placed by settlement generator), so irregular lot handling is lower priority.

---

## MISSION 3: Open Source CGA Implementations

### 3.1 BCGA (Blender CGA) -- github.com/vvoovv/bcga

**Language:** Python, Blender addon
**Status:** Archived/unmaintained (last significant activity ~2015)
**Stars:** 94
**Approach:** Rules are Python functions that operate on a shape object. Each function receives a shape with scope properties and produces child shapes.

**Key design:**
- Rules are plain Python functions decorated or registered
- Shape tree is implicit (function call stack)
- Operations are method calls on a shape context
- Blender integration: creates Blender mesh objects at terminals

**Limitation:** No explicit shape tree data structure. Rules execute imperatively. This makes it hard to inspect the tree or do multi-pass operations (like occlusion testing).

### 3.2 Prokitektura -- github.com/nortikin/prokitektura-blender

**Language:** Python, Blender addon
**Status:** Fork of BCGA, similarly unmaintained
**Approach:** Same as BCGA but with interactive Blender panel for rule editing

**Workflow:** 2D outline -> extrude -> decompose facades -> cut floors -> fill sections

### 3.3 ShapeML -- github.com/stefalie/shapeml

**Language:** C++ (99%)
**Status:** Last commit June 2023, stable but unmaintained
**Approach:** Full grammar-based system inspired by CGA, L-systems, and G2

**Key design:**
- Rules defined in a custom DSL: `rule Name = { operations TerminalName_ }`
- Parallel rewriting (L-system style)
- Built-in straight skeleton for roofHip
- Stack-based material scoping
- Terminal shapes suffixed with `_`

**Complexity:** Example "Hello House" is ~30 rules. Full city examples have hundreds.

### 3.4 CGA_interpreter -- github.com/pvallet/CGA_interpreter

**Language:** C++ (84%), with flex/bison parser
**Status:** Appears inactive since ~2015
**Approach:** Parses CGA-like grammar files, generates .obj meshes
**Uses:** CGAL for computational geometry

### 3.5 CGAjs -- gromgull.github.io/cgajs

**Language:** JavaScript
**Status:** Proof of concept
**Operations:** split, comp, extrude, taper, rotate, scale, translate, color, stochastic rules
**Limitation:** Missing arithmetic, parameterized rules, conditional logic

### 3.6 Paiga -- github.com/chy/paiga

**Language:** Python wrapper for CityEngine's CGA
**Status:** Unknown activity

### 3.7 Complexity of Real CGA Rulesets

From surveying examples across these implementations and CityEngine tutorials:

| Building Type | Rule Count | LOC (approx) | Complexity |
|---------------|-----------|---------------|------------|
| Simple house (box + roof + windows) | 8-12 rules | 40-80 | Trivial |
| Medieval house (timber frame, varied facades) | 15-25 rules | 100-200 | Medium |
| Gothic cathedral | 30-50 rules | 200-400 | High |
| Full city with multiple styles | 50-100 rules | 400-800 | Very High |
| CityEngine tutorial building | 15 rules | ~100 | Medium |

**Key insight:** The grammar engine itself is small. The ruleset complexity is where the effort goes. A medieval tavern might be 20 rules; a cathedral might be 50. But the engine evaluating those rules is the same ~300 lines of code.

---

## MISSION 4: Implementation Design for VeilBreakers

### 4.1 Data Structures

#### Shape (Node in the shape tree)

```python
@dataclass
class Shape:
    """A node in the CGA shape tree."""
    symbol: str                          # Rule name ("Facade", "Floor", "Window")
    scope: Scope                         # Position, rotation, size
    parent: Optional["Shape"] = None     # Parent in tree
    children: list["Shape"] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)  # Per-shape params
    geometry: Optional[dict] = None      # Terminal geometry (MeshSpec)
    is_terminal: bool = False
    seed: int = 0
```

#### Scope (Oriented bounding box)

```python
@dataclass
class Scope:
    """Oriented bounding box defining shape position and size."""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    size: tuple[float, float, float] = (1.0, 1.0, 1.0)

    @property
    def sx(self) -> float: return self.size[0]
    @property
    def sy(self) -> float: return self.size[1]
    @property
    def sz(self) -> float: return self.size[2]
```

#### Grammar Rule

```python
@dataclass
class GrammarRule:
    """A single production rule in the grammar."""
    predecessor: str                     # Symbol this rule matches
    condition: Optional[Callable] = None # Guard condition
    probability: float = 1.0            # For stochastic selection
    body: Callable = None               # Function that produces child shapes
```

#### Ruleset

```python
@dataclass
class BuildingRuleset:
    """Complete set of rules for a building type."""
    name: str                           # "tavern", "cathedral", etc.
    style: str                          # "medieval", "gothic", etc.
    rules: dict[str, list[GrammarRule]] # symbol -> list of possible rules
    attributes: dict                    # Default attribute values
```

### 4.2 Grammar Engine (~300 lines)

```python
class GrammarEngine:
    """Evaluates a CGA-style shape grammar to produce a shape tree."""

    def __init__(self, ruleset: BuildingRuleset, seed: int = 0):
        self.ruleset = ruleset
        self.rng = random.Random(seed)
        self.max_depth = 20  # Safety limit

    def evaluate(self, initial_scope: Scope) -> Shape:
        """Evaluate grammar starting from 'Lot' symbol."""
        root = Shape(
            symbol="Lot",
            scope=initial_scope,
            seed=self.rng.randint(0, 2**31),
            attributes=dict(self.ruleset.attributes),
        )
        self._derive(root, depth=0)
        return root

    def _derive(self, shape: Shape, depth: int) -> None:
        """Recursively apply rules to expand the shape tree."""
        if depth > self.max_depth or shape.is_terminal:
            return

        rules = self.ruleset.rules.get(shape.symbol, [])
        if not rules:
            shape.is_terminal = True  # No rule = implicit terminal
            return

        # Select rule (stochastic + conditional)
        rule = self._select_rule(rules, shape)
        if rule is None:
            shape.is_terminal = True
            return

        # Execute rule body -- produces child shapes
        children = rule.body(shape, self.rng)
        shape.children = children
        for child in children:
            child.parent = shape
            self._derive(child, depth + 1)

    def _select_rule(self, rules: list[GrammarRule], shape: Shape) -> Optional[GrammarRule]:
        """Select a rule using conditions and probability."""
        # Filter by condition
        applicable = [r for r in rules if r.condition is None or r.condition(shape)]
        if not applicable:
            return None

        # Stochastic selection
        total = sum(r.probability for r in applicable)
        roll = self.rng.random() * total
        cumulative = 0.0
        for rule in applicable:
            cumulative += rule.probability
            if roll <= cumulative:
                return rule
        return applicable[-1]

    def collect_terminals(self, root: Shape) -> list[Shape]:
        """Collect all terminal (leaf) shapes for geometry generation."""
        terminals = []
        stack = [root]
        while stack:
            node = stack.pop()
            if node.is_terminal or not node.children:
                terminals.append(node)
            else:
                stack.extend(node.children)
        return terminals
```

### 4.3 Split/Repeat/Comp Operations as Helper Functions

```python
def split_shape(parent: Shape, axis: str, specs: list[tuple[str, float, str]],
                rng: random.Random) -> list[Shape]:
    """Split parent scope along axis into child shapes.

    Args:
        parent: Parent shape
        axis: "x", "y", or "z"
        specs: List of (size_type, value, symbol) where size_type is
               "abs", "rel", or "float"
        rng: Random generator

    Returns:
        List of child shapes with scopes set
    """
    axis_idx = {"x": 0, "y": 1, "z": 2}[axis]
    total = parent.scope.size[axis_idx]

    # First pass: calculate absolute and relative sizes
    fixed_total = 0.0
    float_specs = []
    resolved = []

    for size_type, value, symbol in specs:
        if size_type == "abs":
            resolved.append((value, symbol))
            fixed_total += value
        elif size_type == "rel":
            actual = value * total
            resolved.append((actual, symbol))
            fixed_total += actual
        else:  # float
            float_specs.append((value, symbol, len(resolved)))
            resolved.append((value, symbol))  # placeholder

    # Second pass: distribute remaining space to floating sizes
    remaining = max(0.0, total - fixed_total)
    if float_specs:
        float_total = sum(v for v, _, _ in float_specs)
        for value, symbol, idx in float_specs:
            proportion = value / float_total if float_total > 0 else 1.0 / len(float_specs)
            resolved[idx] = (remaining * proportion, symbol)

    # Create child shapes
    children = []
    offset = 0.0
    pos = list(parent.scope.position)
    for size, symbol in resolved:
        if size <= 0:
            continue
        child_pos = list(parent.scope.position)
        child_pos[axis_idx] += offset
        child_size = list(parent.scope.size)
        child_size[axis_idx] = size
        children.append(Shape(
            symbol=symbol,
            scope=Scope(
                position=tuple(child_pos),
                rotation=parent.scope.rotation,
                size=tuple(child_size),
            ),
            seed=rng.randint(0, 2**31),
            attributes=dict(parent.attributes),
        ))
        offset += size

    return children


def repeat_split(parent: Shape, axis: str, target_size: float,
                 symbol: str, rng: random.Random) -> list[Shape]:
    """Repeat a shape along an axis at approximately target_size intervals.

    Adjusts count and actual size so shapes fill the scope evenly.
    """
    axis_idx = {"x": 0, "y": 1, "z": 2}[axis]
    total = parent.scope.size[axis_idx]
    count = max(1, round(total / target_size))
    actual_size = total / count
    specs = [("abs", actual_size, symbol) for _ in range(count)]
    return split_shape(parent, axis, specs, rng)


def comp_split(parent: Shape, face_rules: dict[str, str],
               rng: random.Random) -> list[Shape]:
    """Component split: extract faces of a 3D scope as 2D child shapes.

    face_rules maps face selector to symbol name:
        {"front": "FrontFacade", "back": "BackFacade", "side": "SideFacade", "top": "Roof"}
    """
    sx, sy, sz = parent.scope.size
    px, py, pz = parent.scope.position
    children = []

    face_defs = {
        "front":  ((px, py, pz),          (0, 0, 0),   (sx, sy, 0)),
        "back":   ((px, py, pz + sz),     (0, 180, 0), (sx, sy, 0)),
        "left":   ((px, py, pz),          (0, 90, 0),  (sz, sy, 0)),
        "right":  ((px + sx, py, pz),     (0, -90, 0), (sz, sy, 0)),
        "top":    ((px, py + sy, pz),     (-90, 0, 0), (sx, sz, 0)),
        "bottom": ((px, py, pz),          (90, 0, 0),  (sx, sz, 0)),
    }

    for selector, symbol in face_rules.items():
        if selector == "side":
            # "side" expands to front + back + left + right
            for face_name in ("front", "back", "left", "right"):
                if face_name not in face_rules:
                    pos, rot, size = face_defs[face_name]
                    children.append(Shape(
                        symbol=symbol,
                        scope=Scope(position=pos, rotation=rot, size=size),
                        seed=rng.randint(0, 2**31),
                        attributes={**parent.attributes, "_face": face_name},
                    ))
        elif selector in face_defs:
            pos, rot, size = face_defs[selector]
            children.append(Shape(
                symbol=symbol,
                scope=Scope(position=pos, rotation=rot, size=size),
                seed=rng.randint(0, 2**31),
                attributes={**parent.attributes, "_face": selector},
            ))

    return children
```

### 4.4 Mapping Grammar Terminals to Existing 175 Modular Pieces

The existing `modular_building_kit.py` has 25 piece types x 5 styles = 125 variants (with 50 more planned). The grammar maps terminal symbols to kit pieces:

```python
TERMINAL_TO_KIT_PIECE: dict[str, str] = {
    # Walls
    "WallSolid":       "wall_solid",
    "WallWindow":      "wall_window",
    "WallDoor":        "wall_door",
    "WallDamaged":     "wall_damaged",
    "WallHalf":        "wall_half",
    "CornerInner":     "corner_inner",
    "CornerOuter":     "corner_outer",

    # Floors
    "FloorStone":      "floor_stone",
    "FloorWood":       "floor_wood",

    # Roofs
    "RoofSlope":       "roof_slope",
    "RoofPeak":        "roof_peak",
    "RoofFlat":        "roof_flat",

    # Stairs
    "StairStraight":   "stair_straight",
    "StairSpiral":     "stair_spiral",

    # Doors
    "DoorSingle":      "door_single",
    "DoorDouble":      "door_double",
    "DoorArched":      "door_arched",

    # Windows
    "WindowSmall":     "window_small",
    "WindowLarge":     "window_large",
    "WindowPointed":   "window_pointed",
}
```

For AAA quality, terminal geometry also maps to `building_quality.py` generators:

```python
TERMINAL_TO_QUALITY_GENERATOR: dict[str, Callable] = {
    "WallStone":       generate_stone_wall,
    "TimberFrame":     generate_timber_frame,
    "GothicWindow":    generate_gothic_window,
    "RoofTiles":       generate_roof,
    "Staircase":       generate_staircase,
    "Archway":         generate_archway,
    "Chimney":         generate_chimney,
    "Battlements":     generate_battlements,
    "InteriorTrim":    generate_interior_trim,
}
```

### 4.5 Gothic-Specific Grammar Rules

Gothic architecture has specific proportional rules (from existing `gothic_architecture_rules_research.md`):

```python
GOTHIC_PROPORTIONS = {
    "arch_height_ratio": 1.73,        # Equilateral pointed arch: H = W * sqrt(3)/2
    "lancet_height_ratio": 2.5,       # Lancet: taller and narrower
    "nave_height_ratio": 1.414,       # Ad quadratum: H = W * sqrt(2)
    "aisle_width_ratio": 0.5,         # Aisle = nave_width * 0.5
    "bay_length_ratio": 0.6,          # Bay = nave_width * 0.5-0.707
    "buttress_depth_ratio": 1.5,      # Buttress depth = 1.5x wall thickness
    "clerestory_height_fraction": 0.33,
    "triforium_height_fraction": 0.20,
    "arcade_height_fraction": 0.47,
}
```

These feed into conditional rules:

```python
def gothic_facade_rule(shape, rng):
    """Gothic facade: arcade -> triforium -> clerestory."""
    h = shape.scope.sy
    return split_shape(shape, "y", [
        ("rel", 0.47, "Arcade"),
        ("rel", 0.20, "Triforium"),
        ("rel", 0.33, "Clerestory"),
    ], rng)
```

### 4.6 Integration with Existing modular_building_kit.py

The grammar does NOT replace the existing system. It layers on top:

1. `evaluate_building_grammar()` stays as the entry point
2. Internally, it creates a `GrammarEngine` with the appropriate `BuildingRuleset`
3. The engine evaluates the grammar tree
4. Terminal shapes are collected
5. Each terminal maps to either a kit piece or quality generator
6. The resulting geometry ops are packaged into a `BuildingSpec` (same as current output)

**Integration point:**
```python
def evaluate_building_grammar(width, depth, floors, style, seed=0):
    ruleset = BUILDING_RULESETS[style]
    engine = GrammarEngine(ruleset, seed=seed)
    initial_scope = Scope(position=(0, 0, 0), size=(width, depth, floors * ruleset.attributes["floor_height"]))
    root = engine.evaluate(initial_scope)
    terminals = engine.collect_terminals(root)
    ops = _terminals_to_ops(terminals, style)
    return BuildingSpec(footprint=(width, depth), floors=floors, style=style, operations=ops)
```

### 4.7 Facade vs Structure Distinction

CGA naturally separates these through the derivation flow:

1. **Structure phase:** Lot -> extrude -> Building mass (3D box)
2. **Facade phase:** comp(f) -> individual faces -> split into floors/bays -> fill with detail

The structure defines the mass model (volume, proportions). The facade rules only operate on the 2D face shapes extracted by comp(f). This separation means:
- Structural changes (adding a wing, tower, annex) happen at the mass model level
- Facade changes (window style, door placement) happen at the face level
- They never interfere with each other

### 4.8 Building Variation from Same Grammar

Variation comes from four sources:

1. **Stochastic rules:** 30% chance of balcony, 70% plain wall
2. **Random attributes:** `height = rand(10, 18)`, `floor_count = rint(rand(2, 4))`
3. **Seed-based:** Same seed = same building. Different seed = different variation.
4. **Conditional rules:** Narrow lots get different facades than wide lots

```python
# Example: same "medieval_house" grammar, different seeds
house_1 = engine.evaluate(scope, seed=42)    # 2 floors, balcony, chimney left
house_2 = engine.evaluate(scope, seed=99)    # 3 floors, no balcony, chimney right
house_3 = engine.evaluate(scope, seed=7)     # 2 floors, shutters, dormers
```

### 4.9 Performance Estimate

The grammar engine is pure Python operating on dataclasses. No geometry computation happens during grammar evaluation -- it just builds a tree of scopes and symbols.

**Estimated performance (Python 3.10+):**

| Building Complexity | Tree Nodes | Grammar Eval Time | Geometry Gen Time |
|--------------------|-----------|-------------------|-------------------|
| Simple house (2 floors) | 30-60 | <1ms | 5-15ms |
| Medieval tavern (3 floors, detailed) | 80-150 | 1-3ms | 20-50ms |
| Castle tower (5 floors, battlements) | 100-200 | 2-5ms | 30-80ms |
| Cathedral (nave + transept) | 200-400 | 5-15ms | 50-200ms |

Grammar evaluation is trivially fast. The bottleneck is always geometry generation (creating actual mesh vertices/faces via building_quality.py generators). A settlement of 50 buildings would take 1-5 seconds total for grammar evaluation, then 5-20 seconds for geometry.

---

## MISSION 5: Medieval Gothic Grammar Rules for VeilBreakers

### 5.1 Tavern Grammar

```python
TAVERN_RULES = {
    "Lot": [GrammarRule("Lot", body=lambda s, r: [
        Shape("Building", scope=Scope(s.scope.position,
              s.scope.rotation,
              (s.scope.sx, s.scope.sy, s.scope.sz)))
    ])],

    "Building": [GrammarRule("Building", body=lambda s, r:
        # Extrude and decompose
        comp_split(s, {
            "front": "TavernFront",
            "back": "TavernBack",
            "side": "TavernSide",
            "top": "TavernRoof",
        }, r)
    )],

    "TavernFront": [GrammarRule("TavernFront", body=lambda s, r:
        split_shape(s, "y", [
            ("abs", 4.0, "GroundFloorFront"),    # Bar entrance + large windows
            ("float", 3.5, "UpperFloorFront"),   # Rooms + smaller windows
        ], r)
    )],

    "GroundFloorFront": [GrammarRule("GroundFloorFront", body=lambda s, r:
        split_shape(s, "x", [
            ("float", 1.0, "WallSolid"),
            ("abs", 1.5, "DoorArched"),          # Main tavern door
            ("float", 1.0, "WallSolid"),
            ("abs", 1.2, "WindowLarge"),          # Bar window
            ("float", 1.0, "WallSolid"),
            ("abs", 1.2, "WindowLarge"),          # Bar window
            ("float", 1.0, "WallSolid"),
        ], r)
    )],

    "UpperFloorFront": [GrammarRule("UpperFloorFront", body=lambda s, r:
        split_shape(s, "x", [
            ("float", 1.0, "TimberFrame"),
            *[item for _ in range(r.randint(2, 4))
              for item in [("abs", 0.8, "WindowSmall"), ("float", 0.8, "TimberFrame")]],
        ], r)
    )],

    "TavernRoof": [GrammarRule("TavernRoof", body=lambda s, r: [
        Shape("RoofGabled", scope=s.scope, is_terminal=True,
              attributes={**s.attributes,
                          "pitch": 35,
                          "material": "thatch",
                          "chimney": True,
                          "chimney_offset": r.uniform(0.3, 0.7)})
    ])],
}
```

**~15 rules, ~120 lines.** Produces: ground floor with arched door and large windows, upper floor with timber frame and small room windows, gabled thatch roof with chimney.

### 5.2 Castle Tower Grammar

```python
CASTLE_TOWER_RULES = {
    "Lot": [GrammarRule("Lot", body=lambda s, r:
        # Tower is a vertical stack
        split_shape(s, "y", [
            ("abs", 2.0, "TowerBase"),           # Solid stone base
            ("float", 3.5, "TowerMiddle"),       # Repeating middle sections
            ("abs", 2.5, "TowerTop"),            # Crenellations + roof
        ], r)
    )],

    "TowerBase": [GrammarRule("TowerBase", body=lambda s, r:
        comp_split(s, {"side": "WallFortressSolid", "bottom": "FloorStone"}, r)
    )],

    "TowerMiddle": [GrammarRule("TowerMiddle", body=lambda s, r:
        repeat_split(s, "y", 3.5, "TowerSection", r)
    )],

    "TowerSection": [GrammarRule("TowerSection", body=lambda s, r:
        comp_split(s, {
            "front": "TowerFacade",
            "side": "TowerFacade",
            "back": "TowerFacade",
        }, r)
    )],

    "TowerFacade": [GrammarRule("TowerFacade", body=lambda s, r:
        split_shape(s, "x", [
            ("float", 1.0, "WallFortressSolid"),
            ("abs", 0.15, "ArrowSlit"),           # Narrow arrow slit
            ("float", 1.0, "WallFortressSolid"),
        ], r)
    )],

    "TowerTop": [GrammarRule("TowerTop", body=lambda s, r:
        split_shape(s, "y", [
            ("abs", 0.5, "Parapet"),
            ("abs", 1.0, "Battlements"),          # Merlons + crenels
            ("abs", 1.0, "ConicalRoof"),          # Pointed tower cap
        ], r)
    )],
}
```

**~10 rules.** Produces: solid stone base, repeating middle sections with arrow slits, battlements with crenellations, conical roof cap.

### 5.3 Cathedral Grammar

```python
CATHEDRAL_RULES = {
    "Lot": [GrammarRule("Lot", body=lambda s, r: [
        # Cathedral is a compound of volumes
        Shape("Nave", scope=Scope(
            (s.scope.position[0] + s.scope.sx * 0.2, s.scope.position[1], s.scope.position[2]),
            s.scope.rotation,
            (s.scope.sx * 0.3, s.scope.sy, s.scope.sz * 0.7))),
        Shape("LeftAisle", scope=Scope(
            (s.scope.position[0], s.scope.position[1], s.scope.position[2]),
            s.scope.rotation,
            (s.scope.sx * 0.2, s.scope.sy * 0.6, s.scope.sz * 0.7))),
        Shape("RightAisle", scope=Scope(
            (s.scope.position[0] + s.scope.sx * 0.5, s.scope.position[1], s.scope.position[2]),
            s.scope.rotation,
            (s.scope.sx * 0.2, s.scope.sy * 0.6, s.scope.sz * 0.7))),
        Shape("Transept", scope=Scope(
            (s.scope.position[0], s.scope.position[1], s.scope.position[2] + s.scope.sz * 0.5),
            s.scope.rotation,
            (s.scope.sx, s.scope.sy * 0.8, s.scope.sz * 0.2))),
        Shape("Apse", scope=Scope(
            (s.scope.position[0] + s.scope.sx * 0.25, s.scope.position[1], s.scope.position[2] + s.scope.sz * 0.7),
            s.scope.rotation,
            (s.scope.sx * 0.25, s.scope.sy * 0.7, s.scope.sz * 0.3))),
        Shape("BellTower", scope=Scope(
            (s.scope.position[0] + s.scope.sx * 0.1, s.scope.position[1], s.scope.position[2] - 1.0),
            s.scope.rotation,
            (s.scope.sx * 0.15, s.scope.sy * 1.5, s.scope.sx * 0.15))),
    ])],

    "Nave": [GrammarRule("Nave", body=lambda s, r:
        comp_split(s, {
            "front": "NaveFacadeWest",
            "side": "NaveFacadeSide",
            "top": "NaveRoof",
        }, r)
    )],

    "NaveFacadeSide": [GrammarRule("NaveFacadeSide", body=lambda s, r:
        # Gothic vertical tripartite: arcade -> triforium -> clerestory
        split_shape(s, "y", [
            ("rel", 0.47, "Arcade"),
            ("rel", 0.20, "Triforium"),
            ("rel", 0.33, "Clerestory"),
        ], r)
    )],

    "Arcade": [GrammarRule("Arcade", body=lambda s, r:
        repeat_split(s, "x", s.scope.sx * 0.6, "ArcadeBay", r)
    )],

    "ArcadeBay": [GrammarRule("ArcadeBay", body=lambda s, r:
        split_shape(s, "x", [
            ("abs", 0.5, "Buttress"),
            ("float", 1.0, "PointedArchway"),
            ("abs", 0.5, "Buttress"),
        ], r)
    )],

    "Clerestory": [GrammarRule("Clerestory", body=lambda s, r:
        repeat_split(s, "x", s.scope.sx * 0.6, "ClerestoryBay", r)
    )],

    "ClerestoryBay": [GrammarRule("ClerestoryBay", body=lambda s, r:
        split_shape(s, "x", [
            ("float", 0.3, "WallStone"),
            ("float", 1.0, "GothicWindow"),
            ("float", 0.3, "WallStone"),
        ], r)
    )],

    "NaveRoof": [GrammarRule("NaveRoof", body=lambda s, r: [
        Shape("RoofPointed", scope=s.scope, is_terminal=True,
              attributes={**s.attributes, "pitch": 60, "material": "slate"})
    ])],

    "BellTower": [GrammarRule("BellTower", body=lambda s, r:
        split_shape(s, "y", [
            ("rel", 0.6, "TowerBody"),
            ("rel", 0.15, "Belfry"),
            ("rel", 0.25, "Spire"),
        ], r)
    )],
}
```

**~20 rules for nave structure alone.** Full cathedral with transept, apse, aisles, bell tower, flying buttresses would be ~40-50 rules. The compound volume approach (nave + aisles + transept) creates the cruciform plan.

### 5.4 House Grammar

```python
HOUSE_RULES = {
    "Lot": [GrammarRule("Lot", body=lambda s, r:
        comp_split(s, {
            "front": "HouseFront",
            "back": "HouseBack",
            "side": "HouseSide",
            "top": "HouseRoof",
        }, r)
    )],

    "HouseFront": [GrammarRule("HouseFront", body=lambda s, r:
        split_shape(s, "y", [
            ("abs", 3.0, "GroundFloor"),
            ("float", 3.0, "UpperFloor"),
        ], r)
    )],

    "GroundFloor": [GrammarRule("GroundFloor", body=lambda s, r:
        split_shape(s, "x", [
            ("float", 1.0, "WallSolid"),
            ("abs", 1.2, "DoorSingle"),
            ("float", 1.5, "WallSolid"),
            ("abs", 0.8, "WindowSmall"),
            ("float", 1.0, "WallSolid"),
        ], r)
    )],

    "UpperFloor": [
        # Stochastic: 60% timber frame, 40% stone
        GrammarRule("UpperFloor", probability=0.6, body=lambda s, r:
            split_shape(s, "x", [
                ("float", 0.5, "TimberFrame"),
                ("abs", 0.8, "WindowSmall"),
                ("float", 1.0, "TimberFrame"),
                ("abs", 0.8, "WindowSmall"),
                ("float", 0.5, "TimberFrame"),
            ], r)
        ),
        GrammarRule("UpperFloor", probability=0.4, body=lambda s, r:
            split_shape(s, "x", [
                ("float", 1.0, "WallSolid"),
                ("abs", 0.8, "WindowSmall"),
                ("float", 1.0, "WallSolid"),
                ("abs", 0.8, "WindowSmall"),
                ("float", 1.0, "WallSolid"),
            ], r)
        ),
    ],

    "HouseRoof": [GrammarRule("HouseRoof", body=lambda s, r: [
        Shape("RoofGabled", scope=s.scope, is_terminal=True,
              attributes={**s.attributes,
                          "pitch": r.choice([30, 35, 40, 45]),
                          "material": r.choice(["thatch", "tile", "slate"]),
                          "dormer_count": r.randint(0, 2)})
    ])],
}
```

### 5.5 Gatehouse Grammar

```python
GATEHOUSE_RULES = {
    "Lot": [GrammarRule("Lot", body=lambda s, r: [
        # Central archway
        Shape("ArchPassage", scope=Scope(
            (s.scope.position[0] + s.scope.sx * 0.3, s.scope.position[1], s.scope.position[2]),
            s.scope.rotation,
            (s.scope.sx * 0.4, s.scope.sy * 0.6, s.scope.sz))),
        # Left tower
        Shape("GateTower", scope=Scope(
            s.scope.position, s.scope.rotation,
            (s.scope.sx * 0.3, s.scope.sy * 1.2, s.scope.sz))),
        # Right tower
        Shape("GateTower", scope=Scope(
            (s.scope.position[0] + s.scope.sx * 0.7, s.scope.position[1], s.scope.position[2]),
            s.scope.rotation,
            (s.scope.sx * 0.3, s.scope.sy * 1.2, s.scope.sz))),
        # Wall walk connecting towers above arch
        Shape("WallWalk", scope=Scope(
            (s.scope.position[0] + s.scope.sx * 0.3, s.scope.position[1] + s.scope.sy * 0.6, s.scope.position[2]),
            s.scope.rotation,
            (s.scope.sx * 0.4, s.scope.sy * 0.2, s.scope.sz * 0.3))),
    ])],

    "ArchPassage": [GrammarRule("ArchPassage", body=lambda s, r:
        split_shape(s, "y", [
            ("rel", 0.7, "PointedArchway"),
            ("abs", 0.3, "Portcullis"),
            ("float", 1.0, "WallFortressSolid"),
        ], r)
    )],

    "GateTower": [GrammarRule("GateTower", body=lambda s, r:
        split_shape(s, "y", [
            ("abs", 2.0, "TowerBase"),
            ("float", 3.5, "TowerMiddle"),
            ("abs", 2.0, "TowerTop"),
        ], r)
    )],
}
```

### 5.6 Corruption System (VeilBreakers-Specific)

Dark fantasy corruption modifies grammar rules to produce twisted, damaged architecture:

```python
def apply_corruption(ruleset: BuildingRuleset, corruption_level: float) -> BuildingRuleset:
    """Apply Veil corruption to a building grammar.

    corruption_level: 0.0 = pristine, 1.0 = completely corrupted

    Effects by level:
    - 0.0-0.2: cosmetic (discoloration, moss, minor cracks)
    - 0.2-0.5: structural damage (missing pieces, broken windows, tilted walls)
    - 0.5-0.8: severe warping (twisted geometry, organic growths, impossible angles)
    - 0.8-1.0: eldritch transformation (non-euclidean, tentacles, eyes, reality tears)
    """
    corrupted = copy_ruleset(ruleset)

    if corruption_level >= 0.2:
        # Replace some WallSolid terminals with WallDamaged
        inject_stochastic(corrupted, "WallSolid", [
            (1.0 - corruption_level, "WallSolid"),
            (corruption_level * 0.5, "WallDamaged"),
            (corruption_level * 0.3, "WallCracked"),
            (corruption_level * 0.2, "WallHole"),
        ])

    if corruption_level >= 0.5:
        # Inject scope warping into structure rules
        inject_scope_warp(corrupted, max_tilt=corruption_level * 15)  # degrees
        # Add organic growths as additional terminals
        inject_growth_terminals(corrupted, [
            "VineGrowth", "MossCluster", "FungalBloom",
            "BoneProtrusion", "TentacleRoot",
        ], probability=corruption_level * 0.3)

    if corruption_level >= 0.8:
        # Impossible geometry: some scopes get non-uniform scale
        inject_eldritch_warp(corrupted, intensity=corruption_level)

    return corrupted
```

This works because the grammar tree is data -- we can modify rules and add stochastic alternatives without changing the engine. The same `GrammarEngine` evaluates both pristine and corrupted rulesets.

---

## Common Pitfalls

### Pitfall 1: Over-Engineering the Grammar Language
**What goes wrong:** Building a full CGA DSL parser with lexer/parser when Python functions work fine.
**Why it happens:** Academic CGA papers describe a custom language. Tempting to implement the language itself.
**How to avoid:** Use Python functions as rules. The grammar engine just needs to call functions and build a tree. No parsing needed.
**Warning signs:** Writing a tokenizer, building an AST, discussing "grammar of the grammar."

### Pitfall 2: Geometry in the Grammar
**What goes wrong:** Creating Blender mesh data inside grammar rules.
**Why it happens:** Seems natural to generate geometry as you derive the tree.
**How to avoid:** Grammar evaluation ONLY produces a shape tree with scopes and symbols. Geometry generation is a separate pass that walks the terminal shapes. This keeps grammar evaluation pure-Python testable (no bpy dependency).
**Warning signs:** Importing bpy or bmesh in grammar rule files.

### Pitfall 3: Floating-Point Accumulation in Split
**What goes wrong:** After many nested splits, child scopes don't perfectly tile the parent due to float rounding.
**Why it happens:** Each split divides and rounds independently.
**How to avoid:** Always compute child positions as `parent_start + offset` rather than accumulating `prev_end + gap`. Validate that children sum to parent size.
**Warning signs:** Visible gaps between wall sections, overlapping geometry.

### Pitfall 4: Infinite Recursion in Grammar
**What goes wrong:** A rule produces children with the same symbol, causing infinite recursion.
**Why it happens:** Stochastic rules that sometimes select the parent symbol. Conditional rules with impossible conditions.
**How to avoid:** Max depth limit (20 is safe). Symbol blacklisting after N expansions. Ensure every rule path eventually reaches terminals.
**Warning signs:** Stack overflow, max recursion depth errors.

### Pitfall 5: Ignoring Face Orientation in comp()
**What goes wrong:** Facades are flipped or windows face inward.
**Why it happens:** comp_split creates 2D shapes from 3D face extraction, but the rotation is wrong.
**How to avoid:** Each face needs its scope rotation set so that the face normal points outward, x is along the face width, and y is along the face height. Test with simple colored cubes first.
**Warning signs:** Windows visible from inside but not outside, reversed normals.

### Pitfall 6: Not Seeding Randomness Per Shape
**What goes wrong:** Same building produces different results each run, or all buildings in a settlement look identical.
**Why it happens:** Using a single global RNG. Or using the same seed for every building.
**How to avoid:** Each shape gets a child seed derived from parent seed + child index. This ensures reproducibility while maintaining variation.
**Warning signs:** Non-reproducible builds, identical buildings despite different seeds.

---

## Architecture Pattern: The Complete Pipeline

```
1. Settlement generator places building lots (position, footprint, type)
         |
2. Building type selects a BuildingRuleset ("tavern", "house", "cathedral")
         |
3. GrammarEngine evaluates ruleset with lot scope -> Shape tree
         |
4. collect_terminals() extracts leaf shapes with scopes + symbols
         |
5. Terminal mapper converts symbols to geometry ops:
   - Kit pieces: scope -> position/rotation for modular_building_kit piece
   - Quality generators: scope -> params for building_quality generator
   - Primitives: scope -> box/cylinder geometry
         |
6. All geometry ops packaged into BuildingSpec.operations
         |
7. Existing _building_ops_to_mesh_spec() converts to vertex/face data
         |
8. Existing _spec_to_bmesh() creates Blender mesh objects
```

**What changes:** Steps 3-6 replace the current imperative code in `evaluate_building_grammar()`.
**What stays the same:** Steps 1-2 (settlement placement), Steps 7-8 (Blender mesh creation).

---

## Code Size Estimates

| Component | Estimated LOC | Complexity |
|-----------|-------------|------------|
| Shape/Scope/GrammarRule dataclasses | 60 | Trivial |
| GrammarEngine (evaluate, derive, select) | 80 | Low |
| split_shape, repeat_split, comp_split | 120 | Medium |
| Terminal-to-geometry mapper | 80 | Low |
| Tavern ruleset | 80 | Low |
| House ruleset | 60 | Low |
| Castle tower ruleset | 70 | Low |
| Cathedral ruleset | 120 | Medium |
| Gatehouse ruleset | 60 | Low |
| Corruption system | 80 | Medium |
| Integration with existing grammar | 50 | Low |
| **Total** | **~860** | **Medium** |

The core engine is ~260 lines. Rulesets are ~400 lines for 5 building types. Integration/corruption ~200 lines.

---

## Sources

### Primary (HIGH confidence)
- [Muller/Wonka/Haegler/Ulmer/Van Gool, "Procedural Modeling of Buildings," SIGGRAPH 2006](http://peterwonka.net/Publications/pdfs/2006.SG.Mueller.ProceduralModelingOfBuildings.final.pdf)
- [Esri CityEngine CGA Shape Grammar Reference](https://doc.arcgis.com/en/cityengine/latest/cga/cityengine-cga-introduction.htm)
- [CityEngine CGA Split Operation](https://doc.arcgis.com/en/cityengine/latest/cga/cga-split.htm)
- [CityEngine CGA Component Split](https://doc.arcgis.com/en/cityengine/latest/cga/cga-comp.htm)
- [CityEngine CGA Extrude Operation](https://doc.arcgis.com/en/cityengine/latest/cga/cga-extrude.htm)
- [CityEngine CGA Essential Concepts](https://doc.arcgis.com/en/cityengine/latest/help/help-cga-essential-concepts.htm)
- [CityEngine CGA Stochastic Rules](https://doc.arcgis.com/en/cityengine/2019.0/help/help-stochastic-rule.htm)
- [CityEngine CGA Occlusion Queries](https://doc.arcgis.com/en/cityengine/latest/cga/cga-inside-function.htm)
- [CityEngine Tutorial 6: Basic Shape Grammar](https://doc.arcgis.com/en/cityengine/latest/tutorials/tutorial-6-basic-shape-grammar.htm)
- Existing codebase: `_building_grammar.py` (2716 lines), `building_quality.py` (2775 lines), `modular_building_kit.py` (1551 lines)
- Existing research: `gothic_architecture_rules_research.md`, `modular_building_kits_research.md`, `procedural_buildings_aaa_research.md`

### Secondary (MEDIUM confidence)
- [BCGA: Computer Generated Architecture for Blender](https://github.com/vvoovv/bcga)
- [Prokitektura: 3D buildings via Python functions for Blender](https://github.com/nortikin/prokitektura-blender)
- [ShapeML: Rule-based procedural 3D modeling framework](https://github.com/stefalie/shapeml)
- [CGAjs: JavaScript CGA Shape Grammar parser/processor](https://gromgull.github.io/cgajs/)
- [CGA Collection: Curated list of CGA repos](https://github.com/natowi/cga-collection)
- [Penn CIS700 Shape Grammar lecture slides](https://cis700-procedural-graphics.github.io/files/shape_grammar_2_7_17.pdf)
- [Penn State GEOG 497: Understanding CGA Shape Grammar](https://www.e-education.psu.edu/geogvr/node/891)

### Tertiary (LOW confidence -- training data, not verified recently)
- Performance estimates for Python grammar evaluation (based on similar tree traversal benchmarks, not CGA-specific measurements)
- Corruption system design (novel, not based on published CGA extensions)
