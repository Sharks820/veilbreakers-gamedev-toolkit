# Gothic Medieval Architecture - Procedural Generation Rules

**Researched:** 2026-04-02
**Domain:** Architectural proportional systems for procedural building generation
**Confidence:** HIGH (architectural proportions are well-documented historical fact)
**Purpose:** Provide exact numerical rules for procedural generators in `building_quality.py`, `_building_grammar.py`, and settlement systems

## Summary

This document codifies the proportional rules of late medieval Gothic architecture into numerical parameters suitable for procedural generation. All values are expressed as ratios, angles, or metric dimensions that can be directly plugged into Python generator functions. The research covers five domains: Gothic structural proportions, medieval construction rules, weathering/aging patterns, town layout rules, and game-specific adaptations.

The existing codebase already has good foundations in `building_quality.py` (arch curves, stone blocks, battlements) and `_building_grammar.py` (5 style configs), but many proportional constants are either hardcoded without source or missing entirely. This research provides the authoritative reference values.

**Primary recommendation:** Update `STYLE_CONFIGS` and `FACADE_STYLE_RULES` dictionaries in `_building_grammar.py` to use these researched proportions, and add new constant dictionaries for the missing systems (crenellation ratios, weathering placement rules, town layout spacing).

---

## MISSION 1: Gothic Architecture Proportional Systems

### 1.1 Pointed Arch Proportions

Gothic arches are constructed from two intersecting circular arcs. The key variable is where the arc centers sit relative to the span.

| Arch Type | Height:Width Ratio | Center Offset (from midpoint, as fraction of half-span) | Character |
|-----------|-------------------|----------------------------------------------------------|-----------|
| **Equilateral** | 1.73:1 (sqrt(3):1) | 0.0 (centers at spring points) | Standard Gothic, most common |
| **Lancet** | 2.0:1 to 3.0:1 | 0.3-0.6 inward of spring points | Early English, tall and narrow |
| **Depressed/Drop** | 1.2:1 to 1.5:1 | 0.2-0.4 outward of spring points | Late Gothic, wider and lower |
| **Ogee** | 1.5:1 to 2.0:1 | S-curve, 4-center construction | Decorated period, ornamental |
| **Four-centered (Tudor)** | 0.8:1 to 1.2:1 | Two tight + two wide radii | Late medieval, nearly flat |

**Geometric construction rule:** For an equilateral pointed arch of span W:
- Arc radius R = W (each arc center sits at the opposite spring point)
- Peak height H = W * sqrt(3)/2 = W * 0.866
- For lancet: R > W, centers move inward by `offset = R - W/2`
- For depressed: R < W, centers move outward

**Historical evolution of "sharpness" (center offset as fraction of span):**
- Early (700s): 1/10 of span
- Mid (730s): 1/6 of span
- Late (740s): 1/5 of span
- Mature Gothic (860s+): 1/3 of span

**Implementation note:** The existing `_arch_curve()` in `building_quality.py` uses `offset = hw * 0.3` for gothic_pointed, which corresponds to a 0.3 fraction -- this is historically accurate for mature Gothic. The lancet uses `offset = hw * 0.6`, also correct.

### 1.2 Ad Quadratum and Ad Triangulum Proportional Systems

These are the two master proportional systems used to derive ALL dimensions in a Gothic building from a single base measurement.

**Ad Quadratum (to the square):**
- Start with a circle of diameter D (typically the nave width)
- Inscribe a square: side = D / sqrt(2) = D * 0.707
- Rotate 45 degrees to get octagon
- Total height of nave = D (height equals combined width of nave + aisles)
- Each successive geometric division produces a ratio of 1 : sqrt(2) = 1 : 1.414

**Ad Triangulum (to the triangle):**
- Start with a circle of diameter D
- Inscribe equilateral triangle: side = D * sqrt(3)/2 = D * 0.866
- Rotate 180 degrees to get hexagon
- Height of triangle = D * sqrt(3)/2 = D * 0.866
- Each successive division produces a ratio of 1 : sqrt(3) = 1 : 1.732

**Practical application for generators:**

| Building Element | Derive From | Ratio System | Formula |
|-----------------|-------------|--------------|---------|
| Nave height (to vault) | Nave width | Ad quadratum | height = width * 1.0 to 1.414 |
| Aisle width | Nave width | Ad quadratum | aisle = nave * 0.5 |
| Bay length | Nave width | Ad quadratum | bay = nave * 0.5 to 0.707 |
| Clerestory height | Total wall height | Ad triangulum | clerestory = wall * 0.33 |
| Triforium height | Total wall height | Ad triangulum | triforium = wall * 0.20 |
| Arcade height | Total wall height | Ad triangulum | arcade = wall * 0.47 |

### 1.3 Flying Buttress Rules

| Parameter | Early Gothic | High Gothic | Late Gothic |
|-----------|-------------|-------------|-------------|
| Buttress-to-wall thickness ratio | 2:1 | 1.5:1 | 1:1 |
| Number of tiers | 1 | 2 | 2-3 |
| Spacing | Every bay (1 per bay) | Every bay | Every bay, sometimes every half-bay |
| Angle from horizontal | 50-60 degrees | 40-55 degrees | 35-50 degrees |
| Projection from wall | 0.5x to 0.8x nave width | 0.4x to 0.7x nave width | 0.3x to 0.6x nave width |

**Placement rule:** One flying buttress pier per structural bay. The pier aligns with the point where the vault rib meets the wall (the tas-de-charge). The flyer arc connects the pier's top to the wall at approximately 2/3 of the total wall height.

### 1.4 Rose Window Proportions

| Parameter | Value | Notes |
|-----------|-------|-------|
| Diameter | 0.5x to 0.7x facade width | Centered horizontally |
| Placement height | Center at 0.65x to 0.75x total facade height | Above main entrance, below gable |
| Tracery divisions | 8, 12, or 16 radiating spokes | Powers of 2 or multiples of 4 |
| Inner circle | 0.15x to 0.25x of window diameter | Central medallion |
| Outer ring width | 0.08x to 0.12x of window diameter | Stone frame |
| Historical diameters | 10m to 15m (Notre-Dame north: 12.9m, Strasbourg: 15m) | Scale with facade |

**Tracery subdivision rule:**
1. Central circle (oculus)
2. N radiating bars (where N = 8, 12, or 16)
3. Each sector subdivided by secondary bars into trefoils or quatrefoils
4. Outer ring of pointed arches, one per sector

### 1.5 Ribbed Vault Geometry

| Vault Type | Ribs | Bay Shape | Era |
|------------|------|-----------|-----|
| Sexpartite | 6 compartments, diagonal + transverse ribs | Rectangular, 2 bays wide | Early Gothic (1140-1200) |
| Quadripartite | 4 compartments, diagonal ribs cross at center | Square or rectangular | High Gothic (1200+) |
| Tierceron | Additional ribs from springer to ridge | Rectangular | Decorated Gothic |
| Fan vault | All ribs equal length, fan-shaped | Square | Perpendicular Gothic |
| Lierne | Short decorative ribs between main ribs | Any | Late Gothic |

**Keystone placement:** Always at the geometric center of the bay plan. For a rectangular bay of width W and length L:
- Keystone position: (W/2, L/2) in plan
- Keystone height above springing: For pointed vault, H = W * 0.6 to W * 0.9 (higher = more pointed)
- Rib thickness: 0.02x to 0.04x of span width
- Rib depth (projection below vault surface): 0.03x to 0.06x of span width

### 1.6 Tracery Patterns (Window Subdivisions)

**Geometric subdivision rules for window tracery:**

| Pattern | Construction | Era |
|---------|-------------|-----|
| **Plate tracery** | Holes punched in solid stone wall | Early Gothic (1150-1250) |
| **Bar tracery** | Thin stone mullions subdivide opening | High Gothic (1250+) |
| **Geometric** | Circles and arcs only (trefoils, quatrefoils) | 1250-1310 |
| **Curvilinear/Flowing** | S-curves, ogee arcs, mouchettes | 1310-1350 |
| **Perpendicular/Rectilinear** | Vertical and horizontal mullions dominate | 1350-1530 |

**Trefoil construction:** Three overlapping circles, each with radius R = window_width * 0.25, centers 120 degrees apart at radius R * 0.6 from center.

**Quatrefoil construction:** Four overlapping circles, each with radius R = window_width * 0.2, centers 90 degrees apart at radius R * 0.5 from center.

**Mullion proportions:**
- Width: 0.04x to 0.08x of window opening width
- Depth: 0.8x to 1.2x of mullion width
- Spacing: Divide window into 2, 3, or 4 lights (openings)
- Each light width: (window_width - (N-1) * mullion_width) / N

### 1.7 Column Proportions

| Column Type | Diameter:Height Ratio | Typical Height | Notes |
|-------------|----------------------|----------------|-------|
| **Romanesque pier** | 1:4 to 1:6 | 3-5m | Massive, cylindrical |
| **Early Gothic clustered** | 1:6 to 1:8 | 5-8m | Central core + 4 attached shafts |
| **High Gothic compound** | 1:8 to 1:12 | 8-15m | Thin shafts, each carrying one rib |
| **Late Gothic attenuated** | 1:10 to 1:15 | 10-20m | Very slender, minimal capitals |

**Clustered pier construction:**
- Central core diameter: D
- Attached colonette diameter: D * 0.3 to D * 0.5
- Number of colonettes: 4 (one per vault rib direction) to 8+ (one per rib)
- Colonette spacing: evenly around core, aligned to rib directions
- Capital height: D * 0.8 to D * 1.2
- Base height: D * 0.5 to D * 0.8

**Human-scale rule:** Medieval builders sized individual stones to what one man could handle. Column shaft circumference approximately equals a man's arm span (~1.7m), giving diameter ~0.55m. Clustered pier total diameter: 1.0m to 2.5m.

### 1.8 Crenellation Dimensions

| Element | Dimension | Ratio/Rule |
|---------|-----------|------------|
| **Merlon width** | 0.5m to 0.8m (1.5-2.5 ft) | -- |
| **Crenel (embrasure) width** | 1/3 of merlon width | Historical standard: crenel = merlon / 3 |
| **Merlon height** | 0.6m to 1.0m (2-3.5 ft) | Enough to cover a crouching defender |
| **Merlon depth** | Same as wall thickness at top (0.6-1.0m) | -- |
| **Wall walk width** | 1.2m to 2.0m (4-6.5 ft) | Wide enough for two men to pass |
| **Parapet height** | 0.9m to 1.2m on inner side | Waist-height safety wall |
| **Battlement total height** | Merlon height + parapet = 1.5m to 2.2m | -- |

**Merlon variations:**
- Squared (English): Simple rectangular blocks
- Swallow-tail (Ghibelline/Italian): V-notch in top, each prong = 35% of merlon width
- Rounded (Irish/Welsh): Semicircular cap on top

### 1.9 Machicolation Proportions

| Element | Dimension | Rule |
|---------|-----------|------|
| **Projection from wall face** | 0.3m to 0.6m (1-2 ft) | Enough to drop objects straight down |
| **Corbel depth** | 3-5 stepped courses | Each stepping out ~0.1m |
| **Opening width** | 0.2m to 0.4m | Between each pair of corbels |
| **Spacing** | One per merlon width (0.5-0.8m centers) | Aligned with battlement rhythm |
| **Height placement** | Just below parapet level | Top 10-15% of wall height |
| **Corbel width** | 0.1m to 0.15m | -- |

### 1.10 Tower Proportions

| Tower Type | Height:Base Width Ratio | Notes |
|------------|------------------------|-------|
| **Corner tower** | 1.5:1 to 2.5:1 | Projects from wall corners |
| **Interval/curtain tower** | 1.5:1 to 2.0:1 | Spaced along wall, projects outward |
| **Keep/donjon** | 2:1 to 3:1 | Central stronghold, tallest structure |
| **Gate tower** | 2:1 to 2.5:1 | Flanking gatehouse entrance |
| **Church tower** | 3:1 to 5:1 | Bell tower, landmark |
| **Spire (on tower)** | Additional 0.5x to 1.5x tower height | Total can reach 6:1+ |

**Tower spacing along curtain wall:** Every 30-50m (100-160 ft), or approximately one bowshot apart to ensure overlapping fields of fire.

---

## MISSION 2: Medieval Building Construction Rules

### 2.1 Wall Thickness vs. Height

| Structure Type | Wall Thickness | Wall Height | Ratio (H:T) | Notes |
|---------------|---------------|-------------|--------------|-------|
| **Cottage (1 storey)** | 0.45-0.6m (18-24") | 2.5-3.0m | 5:1 to 6:1 | Cob, rubble, or timber |
| **Town house (2-3 storey)** | 0.3-0.5m (12-20") | 6-10m | 15:1 to 20:1 | Timber frame, thin infill |
| **Stone house (2 storey)** | 0.6-0.9m (24-36") | 6-8m | 8:1 to 10:1 | Rubble with dressed quoins |
| **Church nave** | 0.9-1.5m (3-5 ft) | 10-25m | 10:1 to 17:1 | With buttresses providing stability |
| **Castle curtain wall** | 2.5-6.0m (8-20 ft) | 9-13m (30-44 ft) | 3:1 to 5:1 | Thickest at base, thinning upward |
| **Keep/tower** | 3-6m (10-20 ft) | 20-30m | 4:1 to 6:1 | Walls taper toward top |

**Batter (wall taper) rule:** Castle walls typically batter (slope inward) at approximately 1:12 to 1:20 (horizontal:vertical). Bottom is thicker than top by 20-40%.

### 2.2 Foundation Rules

| Soil Type | Foundation Depth | Spread Beyond Wall | Notes |
|-----------|-----------------|-------------------|-------|
| **Rock** | To bedrock | 0 (direct on rock) | Best case |
| **Firm clay** | 0.6-1.0m | 0.3-0.5m per side | Standard medieval |
| **Soft ground** | 1.0-2.0m | 0.5-1.0m per side | Often with timber piles |
| **Marshy** | 2.0m+ or pile foundations | Raft foundations used | Timber pile grids |

**Foundation width rule:** Foundation spread = wall_thickness + (2 * overhang), where overhang = 0.15m to 0.5m per side depending on ground quality.

### 2.3 Timber Frame Construction

**Post-and-beam (box frame):**
- Post section: 150mm to 250mm square (6-10")
- Beam section: 200mm to 300mm wide x 200-400mm deep (8-12" x 8-16")
- Bay spacing: 3.0m to 5.0m (10-16 ft) center to center
- Storey height: 2.4m to 3.0m (8-10 ft) floor to floor
- Brace angle: 45-60 degrees from horizontal
- Infill panels: wattle and daub (75-100mm thick) or brick nogging

**Cruck frame:**
- Cruck blade spans from ground to ridge in one piece
- Blade spacing: 3.0m to 5.0m (one per bay)
- Ridge height: typically 5-7m for a single-storey hall
- Width at base: 4-6m
- Collar beam at approximately 60% of total height

**Jettied upper floors:**
- Typical overhang: 0.3m to 0.4m (12-16") per storey
- Maximum overhang: up to 1.2m (48") in extreme cases
- Jetty bressummer: 200mm to 300mm deep beam supporting projecting wall
- Each successive storey can jetty further, cumulative overhang up to 1.5m over 3 storeys
- Dragon beams at corners: 45 degrees, supporting corner jetties

### 2.4 Stone-Timber Hybrid Construction

Common pattern in late medieval towns:
- **Ground floor:** Stone or rubble, 0.5-0.8m thick, typically used for shop/storage
- **Upper floors:** Timber frame with plaster/wattle infill
- **Transition:** Stone corbels or a continuous stone course supporting timber wall plate
- **Roof:** Timber structure regardless of wall material

### 2.5 Roof Pitch Angles

| Material | Pitch Angle | Min Overlap | Weight (kg/m2) | Notes |
|----------|-------------|-------------|-----------------|-------|
| **Thatch (straw)** | 50-55 degrees | 300mm | 30-40 | Steepest pitch, fire risk |
| **Thatch (reed)** | 45-50 degrees | 250mm | 35-45 | More durable than straw |
| **Clay tiles** | 35-45 degrees | 75mm | 50-70 | Common in towns |
| **Slate** | 25-35 degrees | 75mm | 35-50 | Can go lower due to flat profile |
| **Stone slates** | 30-40 degrees | 100mm | 60-80 | Very heavy, needs strong timber |
| **Wood shingles** | 35-45 degrees | 50mm | 15-25 | Lightest option |
| **Lead sheet** | 5-15 degrees | n/a | 35-50 | Cathedral/church roofs only |
| **Cathedral Gothic** | 55-65 degrees | n/a | varies | Deliberately steep for silhouette |

**Roof overhang (eaves):** 0.3m to 0.6m beyond wall face. Protects wall from rain.

### 2.6 Window Proportions

| Building Type | Window Width | Window Height | W:H Ratio | % of Wall Area |
|---------------|-------------|---------------|-----------|----------------|
| **Cottage** | 0.4-0.6m | 0.4-0.6m | 1:1 | 5-10% |
| **Town house** | 0.6-0.9m | 0.9-1.5m | 1:1.5 to 1:2 | 15-25% |
| **Gothic church** | 0.6-1.5m | 2.0-6.0m | 1:2.5 to 1:4 | 30-50% |
| **Castle (arrow slit)** | 0.05-0.15m | 0.6-1.2m | 1:8 to 1:12 | 1-3% |
| **Castle (later window)** | 0.6-1.0m | 0.9-1.5m | 1:1.5 | 5-10% |
| **Great hall** | 0.8-1.2m | 1.5-3.0m | 1:2 to 1:2.5 | 20-30% |

**Window placement rules:**
- Sill height: 0.8m to 1.0m above floor (waist height for seated person)
- Head height: minimum 2.0m above floor
- Horizontal spacing: 1.5x to 3x window width between windows
- Never closer than 0.5m to a corner

### 2.7 Door Proportions

| Door Type | Width | Height | W:H Ratio | Notes |
|-----------|-------|--------|-----------|-------|
| **Cottage** | 0.7-0.9m | 1.6-1.8m | 1:2 to 1:2.3 | Low, ducking required |
| **Town house** | 0.9-1.2m | 2.0-2.4m | 1:2 to 1:2.5 | Standard proportions |
| **Church main** | 1.5-2.5m | 3.0-5.0m | 1:2 | Often double doors |
| **Cathedral portal** | 2.5-4.0m | 5.0-8.0m | 1:2 | Triple portal common |
| **Castle gate** | 2.5-3.5m | 3.0-4.5m | 1:1.2 to 1:1.5 | Wide for mounted riders |
| **Postern gate** | 0.8-1.0m | 1.8-2.0m | 1:2 | Small, hidden |

**Door frame depth:** 0.15m to 0.3m for houses, wall_thickness for castle gates.

### 2.8 Staircase Dimensions

| Element | Measurement | Notes |
|---------|-------------|-------|
| **Riser height** | 175-200mm (7-8") | Steeper than modern: medieval went to 230mm |
| **Tread depth** | 225-280mm (9-11") | Often irregular in stone |
| **Width** | 0.7-1.0m (spiral), 1.0-1.5m (straight) | Spiral always clockwise ascending (right-handed defender advantage) |
| **Headroom** | 1.8m minimum | Often lower in castles |
| **Spiral newel diameter** | 0.15-0.25m | Central column |
| **Spiral outer diameter** | 1.5-2.5m | Total staircase diameter |

### 2.9 Floor-to-Floor Heights

| Building Type | Floor Height | Ceiling Height | Notes |
|---------------|-------------|----------------|-------|
| **Cottage** | 2.2-2.5m | 2.0-2.3m | Low, timber beam ceiling |
| **Town house ground** | 2.8-3.2m | 2.5-3.0m | Taller for shop |
| **Town house upper** | 2.4-2.8m | 2.2-2.5m | Progressively lower |
| **Great hall** | 6.0-10.0m | 5.0-9.0m | Double height, open to roof |
| **Church nave** | 15-35m | to vault | Gothic verticality |
| **Castle room** | 3.0-4.0m | 2.5-3.5m | Thick floors eat height |

---

## MISSION 3: Weathering and Aging Rules

### 3.1 Moss Growth Placement Rules

| Surface Condition | Moss Probability | Growth Density | Notes |
|------------------|-----------------|----------------|-------|
| **North-facing wall** | HIGH (0.7-1.0) | Heavy | Stays moist, shaded from midday sun |
| **East-facing wall** | MEDIUM (0.3-0.5) | Moderate | Morning sun dries slowly |
| **South-facing wall** | LOW (0.0-0.1) | Minimal | Too dry from sun exposure |
| **West-facing wall** | MEDIUM (0.2-0.4) | Moderate | Receives rain-bearing winds |
| **Base of wall (0-0.5m)** | HIGH (0.6-0.8) | Heavy | Splash-back moisture + soil contact |
| **Under overhangs/drip lines** | HIGH (0.8-1.0) | Very heavy | Constant water feed |
| **Horizontal ledges** | HIGH (0.7-0.9) | Heavy | Water pools, debris collects |
| **Mortar joints** | MEDIUM (0.4-0.6) | Moderate | Moisture-retaining, nutrient-rich |
| **Vertical smooth stone** | LOW (0.1-0.2) | Sparse | Water runs off too fast |
| **Cracks and crevices** | HIGH (0.7-0.9) | Heavy | Traps moisture and soil |

**Implementation formula for procedural placement:**
```
moss_weight = (
    0.4 * north_facing_factor     # 1.0 if north, 0.0 if south
  + 0.25 * moisture_factor        # 1.0 near ground/drip lines
  + 0.2 * shade_factor            # 1.0 if fully shaded
  + 0.15 * surface_roughness      # 1.0 for rough, 0.0 for smooth
)
```

### 3.2 Stone Darkening Patterns

| Zone | Darkening Intensity | Cause | Visual Character |
|------|-------------------|-------|------------------|
| **Base (0-0.5m)** | HIGH (0.6-0.9) | Splash-back from rain hitting ground | Dark band, irregular top edge |
| **Under window sills** | HIGH (0.5-0.8) | Rainwater runoff concentrated at sill edges | Vertical dark streaks below sill corners |
| **Below drip courses** | MEDIUM (0.3-0.6) | Water running off horizontal stone courses | Horizontal dark band |
| **Sheltered alcoves** | MEDIUM (0.3-0.5) | Soot and grime accumulate, not washed away | Even dark coating |
| **Exposed upper walls** | LOW (0.1-0.2) | Rain washes clean, wind-dried | Lighter than sheltered areas |
| **Around chimneys** | HIGH (0.5-0.8) | Soot deposition | Black staining, heaviest downwind |

**Key insight:** The cleanest stone is often at the TOP of a wall (rain-washed), while the dirtiest is at the BOTTOM (splash-back) and under horizontal projections (concentrated runoff).

### 3.3 Iron Rust Patterns

| Location | Rust Probability | Stain Pattern | Notes |
|----------|-----------------|---------------|-------|
| **Iron cramps/ties in stone** | HIGH after 50+ years | Orange-brown stains radiating outward | Expands, cracks surrounding stone |
| **Door hinges** | HIGH | Vertical streaks below hinge line | More at top hinge (more water) |
| **Window bars/grilles** | HIGH | Drip streaks on sill and below | Concentrated at joints |
| **Chain/ring bolts** | MEDIUM-HIGH | Circular stain around bolt | Ring pattern |
| **Nails in timber** | MEDIUM | Black staining in wood grain | Galvanic reaction with tannins |
| **Drainage grates** | HIGH | Fan-shaped stain below | Water flow concentrates rust |

**Stain direction:** Always follows gravity/water flow -- predominantly downward with slight wind-driven bias.

**Expansion cracking:** Rust expands to 2-6x the volume of original iron, causing spalling of surrounding stone. Add small cracks radiating from iron fixtures.

### 3.4 Timber Weathering Patterns

| Surface | Weathering Character | Speed | Notes |
|---------|---------------------|-------|-------|
| **Exposed end grain** | Fastest, deepest cracking | HIGH | Checks (cracks along grain) within years |
| **South-facing surfaces** | Silver-grey color, surface checking | HIGH | UV + heat cycling |
| **North-facing surfaces** | Dark grey-green, possible algae | MEDIUM | Stays damp, biological growth |
| **Under overhangs (protected)** | Retains original color longest | LOW | Shielded from UV and rain |
| **Ground contact** | Rot from bottom up, soft/spongy | HIGHEST | Moisture wicking, fungal decay |
| **Joints/connections** | Darkening, possible separation | MEDIUM-HIGH | Water infiltration at joints |

**Color progression of exposed timber:**
1. Fresh: golden/honey brown
2. 1-5 years: tan to light grey
3. 5-20 years: silver grey
4. 20-50 years: dark grey
5. 50+ years: dark grey-black, deep checking

### 3.5 Plaster/Render Deterioration

| Location | Failure Probability | Pattern | Cause |
|----------|-------------------|---------|-------|
| **Corners/edges** | HIGHEST (0.8-1.0) | Chunks breaking away from sharp edges | Mechanical impact + freeze-thaw |
| **Below windows** | HIGH (0.6-0.8) | Peeling/bubbling in drip zone | Concentrated water runoff |
| **Base of wall (0-0.5m)** | HIGH (0.7-0.9) | Blistering, salt crystallization | Rising damp + splash-back |
| **Around door frames** | MEDIUM-HIGH (0.5-0.7) | Cracking along frame edges | Differential movement |
| **Center of large panels** | LOW (0.1-0.3) | Last to fail | Best adhered, least stress |
| **Under eaves (sheltered)** | LOWEST (0.0-0.2) | Mostly intact | Protected from rain |

**Exposed material beneath:** When plaster falls, it reveals underlying structure:
- Over stone: rough rubble stone, darker than plaster
- Over timber: dark, possibly rotted timber frame
- Over wattle: woven hazel sticks with daub remnants

### 3.6 Ivy and Vine Growth

| Growth Pattern | Rule | Notes |
|---------------|------|-------|
| **Origin point** | Always from ground level or from cracks above ground | Seeds germinate in soil or collected debris |
| **Climbing direction** | Upward, then laterally | Follows available light and support |
| **Attachment** | Aerial rootlets grip rough surfaces | Cannot climb smooth/polished stone |
| **Preferred surfaces** | Mortar joints, rough stone, timber | Avoids metal, glass |
| **Density gradient** | Thickest at base, thinning with height | More resources at base |
| **Maximum height** | 20-30m for mature ivy | Takes decades to reach full height |
| **Wall coverage** | Starts as single vine, spreads laterally over years | V-shaped pattern: narrow at base, wide above |
| **Damage pattern** | Loosens mortar, lifts tiles, blocks gutters | Destructive to weak joints |

**Implementation rule:** Generate vine origin points at base of wall (every 5-15m of wall length). Grow upward with branching factor of 2-3 per meter height, with random lateral drift of +/- 0.5m per meter height.

### 3.7 Differential Stone Weathering

| Stone Type | Weathering Behavior | Surface Change | Hardness (Mohs) |
|------------|-------------------|----------------|-----------------|
| **Soft limestone** | Dissolves, rounds edges, deep erosion | Smooth, hollowed | 3 |
| **Hard limestone** | Slow surface pitting | Rough but intact | 3-4 |
| **Sandstone** | Granular disintegration, face spalling | Crumbling surface | 6-7 |
| **Granite** | Extremely slow, lichen growth | Dark patina, lichen spots | 6-7 |
| **Marble** | Sugaring (surface becomes granular) | Rough matte surface | 3-4 |
| **Flint** | Almost no weathering | Remains sharp and glossy | 7 |

**In a mixed-stone wall (common in medieval construction):**
- Soft stone blocks erode faster, becoming recessed by 5-20mm
- Hard stone blocks remain proud (projecting) by comparison
- Creates natural relief pattern that deepens with age
- Mortar joints erode faster than most stone: recessed 5-30mm

---

## MISSION 4: Medieval Town Layout Rules

### 4.1 Town Center and Market Square

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Market square size** | 30m x 50m to 80m x 120m | Rectangular, not square |
| **Square as % of town area** | 3-8% | Larger in market towns |
| **Shape** | Rectangular or triangular | Triangle common at road junctions |
| **Market cross/fountain** | Center of square | Landmark and gathering point |
| **Well/pump** | In or adjacent to square | Central water access |
| **Key buildings on square** | Church, guild hall, merchant houses | Highest-status frontages |

### 4.2 Church/Cathedral Placement

| Rule | Description |
|------|-------------|
| **Highest ground** | On hilltop or most prominent location available |
| **Churchyard** | Surrounding the church, 20-40m wide |
| **Orientation** | Altar at east end, entrance at west |
| **Dominance** | Tower/spire visible from all approaches to town |
| **If no high ground** | At center, or at the most important crossroads |
| **Adjacent** | Often adjacent to market square, sometimes one side of it |

### 4.3 Street Dimensions

| Street Type | Width | Paving | Notes |
|-------------|-------|--------|-------|
| **Main street/high street** | 6-10m (20-33 ft) | Cobbled or beaten earth | Wide enough for carts to pass |
| **Secondary street** | 4-6m (13-20 ft) | Partially cobbled | Cart passage, single direction |
| **Side street/lane** | 2.5-4m (8-13 ft) | Earth or rough cobble | Pedestrian + pack animals |
| **Alley/passage** | 1.5-2.5m (5-8 ft) | Earth | Between buildings, pedestrian only |
| **Gate passage** | 3-4m wide, 3-4m high | Cobbled | Through fortified gate |

**Street layout patterns:**
- **Organic:** Radiating from center, following contours, winding
- **Grid (bastide):** Regular blocks, planned towns, 8m x 24m lots
- **Linear:** Single main street, buildings along both sides
- **Radial:** Streets radiating from central square/castle

### 4.4 Building Lots

| District/Wealth | Lot Width (frontage) | Lot Depth | Storeys | Notes |
|----------------|---------------------|-----------|---------|-------|
| **Rich merchant** | 8-12m | 20-40m | 3-4 | Wide frontage, courtyard behind |
| **Middle craftsman** | 5-8m | 15-25m | 2-3 | Narrow frontage, workshop behind |
| **Poor worker** | 3-5m | 10-15m | 1-2 | Very narrow, deep |
| **Bastide standard** | 8m | 24m | 2 | Planned town standard |

**Lot rules:**
- Frontage (width) faces the street
- Building fills front portion of lot (40-60%)
- Rear: garden, workshop, or yard
- Buildings touch side walls of neighbors (party walls)
- Deeper lots = wealthier districts (more garden/work space)

### 4.5 Building Overhangs (Jettying)

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Typical overhang per floor** | 0.3-0.4m (12-16") | Standard jettying |
| **Maximum overhang per floor** | up to 1.2m (48") | Exceptional cases |
| **Cumulative (3 storeys)** | up to 1.5m total | Street becomes a tunnel |
| **Street narrowing effect** | Both sides jettying can reduce street to 2-3m gap at upper floors | Creates dark, enclosed feeling |
| **Banned after** | 1520 (Rouen), 1667 (London) | Fire safety |

### 4.6 Well and Fountain Placement

| Rule | Description |
|------|-------------|
| **Market square well** | Central or adjacent to market square |
| **Neighborhood wells** | Every 100-200m in residential areas |
| **Fountain** | In wealthy district squares, gravity-fed from higher ground |
| **Access** | Always on public ground, never in private lots |
| **Cluster** | Often paired with trough for animals |

### 4.7 Fortified Town Walls and Gates

| Element | Dimension/Rule | Notes |
|---------|---------------|-------|
| **Wall height** | 6-12m (20-40 ft) | Town walls lower than castle walls |
| **Wall thickness** | 1.5-3.0m (5-10 ft) | Thinner than castle walls |
| **Tower spacing** | 30-50m (100-160 ft) | One bowshot apart |
| **Gate width** | 3-4m passage | Single or double gate |
| **Gatehouse depth** | 6-10m | Space for portcullis + murder holes |
| **Moat/ditch** | 5-10m wide, 2-4m deep | Not always present |
| **Wall walk** | 1.2-1.5m wide | Narrower than castle |
| **Number of gates** | 2-6 per town | One per major road approach |
| **Building setback from wall** | 3-5m (pomerium) | Clear zone inside wall for defense |

### 4.8 Bridge Construction

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Width** | 4-8m | Widened sections for market stalls |
| **Pier spacing** | 5-15m arches | Limited by stone arch span technology |
| **Material** | Stone (major), timber (minor/temporary) | Stone = permanent, timber = replaceable |
| **Features** | Chapel, gate towers, shops built on bridge | Medieval bridges were buildings |
| **Approach** | Often the only crossing, creating chokepoint | Toll collection point |

### 4.9 Concentric Ring Districts (from existing _settlement_grammar.py)

The existing codebase already implements this as `RING_THRESHOLDS`:

| Ring | Radius % | Building Types | Wealth Level |
|------|----------|---------------|--------------|
| **Market square** | 0-15% | Merchants, guild hall, church | Highest |
| **Civic ring** | 15-35% | Wealthy houses, professionals | High |
| **Residential** | 35-60% | Craftsmen, workers | Medium |
| **Industrial** | 60-80% | Smithies, tanneries, breweries | Medium-low |
| **Outskirts** | 80-100% | Poor houses, farms, slums | Lowest |

---

## MISSION 5: Game-Specific Architectural Rules

### 5.1 Readability at Game Camera Distance

| Distance | What Must Be Readable | Minimum Feature Size | Notes |
|----------|----------------------|---------------------|-------|
| **Close (5-15m)** | Door handles, window panes, mortar joints | 0.05m+ | Detail pass matters |
| **Medium (15-50m)** | Windows, doors, floor divisions, roof type | 0.2m+ | Silhouette + color |
| **Far (50-200m)** | Building type, roof shape, tower presence | 1.0m+ | Silhouette only |
| **Skyline (200m+)** | Spires, towers, walls vs. open ground | 3.0m+ | Landmark features |

**Rule:** Every building must be identifiable by type from the "medium" camera distance (15-50m). This means:
1. Unique roof silhouette per building type
2. Distinct color/value per building function
3. Landmark features visible at "far" distance

### 5.2 Silhouette Design Rules

| Building Type | Silhouette Feature | Distinguishing Element |
|--------------|-------------------|----------------------|
| **Tavern/Inn** | Wide, low, sprawling roof | Chimney with smoke, hanging sign, warm light |
| **Church/Chapel** | Tall spire or bell tower | Pointed roof, cross at peak, rose window |
| **Blacksmith** | Low with prominent chimney | Large chimney, open-sided workshop |
| **Market stall** | Low, temporary, canopy roof | Fabric awning, open front |
| **Keep/Castle** | Massive, blocky, crenellated | Battlements, flag/banner, thick walls |
| **Watchtower** | Tall, narrow, conical/flat top | Tallest non-church structure |
| **Residence (rich)** | Multi-storey, ornate roof | Jettied upper floors, glazed windows |
| **Residence (poor)** | Low, single-storey, thatch | Minimal features, small windows |
| **Guard post** | Small, blocky, functional | Torch brackets, weapon rack silhouette |
| **Bridge** | Horizontal arch rhythm | Arches reflected in water |

### 5.3 Color Coding by Function

| Building Function | Dominant Color Palette | Lighting Temperature | VeilBreakers Dark Fantasy Adjustment |
|------------------|----------------------|---------------------|--------------------------------------|
| **Tavern/Inn** | Warm ochre, amber, orange | Warm (3000K-4000K) | Firelight glow through windows, smoke |
| **Church/Temple** | Cool grey stone, blue-grey | Cool (5500K-7000K) | Eerie cold light, purple corruption hints |
| **Blacksmith** | Dark iron, red embers | Hot (2000K-3000K) | Forge glow, sparks, dark soot |
| **Merchant/Shop** | Rich colors (red, blue awnings) | Neutral (4000K-5000K) | Slightly desaturated for dark fantasy |
| **Barracks/Military** | Muted stone grey, banner colors | Neutral-cool | Torchlight on stone, flag accents |
| **Residential (rich)** | White/cream plaster, dark timber | Warm interior | Candlelight through glass |
| **Residential (poor)** | Brown/grey, unpainted | Dim warm | Minimal light, soot-stained |
| **Abandoned/Corrupted** | Dark purple, black, green-grey | Cold (7000K+) | Corruption veins, unnatural glow |

### 5.4 Scale Exaggeration for Game Feel

| Element | Real Scale | Game Scale | Multiplier | Reason |
|---------|-----------|------------|------------|--------|
| **Doors** | 2.0m high | 2.5m high | 1.25x | Player character needs headroom + readability |
| **Door width** | 0.9m | 1.2m | 1.3x | Gameplay: easy passage, feels welcoming |
| **Ceilings** | 2.5m | 3.25m | 1.3x | Camera clearance + spacious feel |
| **Windows** | 0.8m wide | 1.0m wide | 1.25x | Readability at distance |
| **Stairs** | 0.2m riser | 0.25m riser | 1.25x | Gameplay: character step animation |
| **Stair width** | 0.9m | 1.2m | 1.3x | Gameplay: camera + character width |
| **Street width** | 4m | 6m | 1.5x | Gameplay: movement + combat space |
| **Ground floor height** | 3.0m | 3.9m | 1.3x | Gameplay: interior space |
| **Upper floors** | 2.5m | 2.75m | 1.1x | Less exaggeration needed |

**VeilBreakers already uses `FURNITURE_SCALE_REFERENCE` in `_building_grammar.py` with correct real-world scales. Apply the 1.25-1.3x multiplier on top of these for game-ready output.**

### 5.5 Navigation Landmarks

| Landmark Priority | Feature | Visibility Range | Purpose |
|------------------|---------|------------------|---------|
| **Primary** | Church spire / castle keep | Town-wide (200m+) | "Where am I?" orientation |
| **Secondary** | Gate towers, bridge, market square | District-wide (100m) | District identification |
| **Tertiary** | Unique building (tavern sign, forge chimney) | Street-level (50m) | Local wayfinding |
| **Quaternary** | Banners, flags, colored awnings | Close range (20m) | Function identification |

**Rules for procedural landmark generation:**
1. Exactly ONE tallest structure per settlement (church or keep)
2. 2-4 secondary landmarks visible from the primary
3. Each street has at least one tertiary landmark (unique feature)
4. Every building entrance has at least one quaternary marker

### 5.6 Making Procedural Buildings NOT Look Procedural

**The 7 variation axes:**

| Axis | Technique | Parameter Range | Impact |
|------|-----------|----------------|--------|
| **1. Asymmetry** | Windows/doors not perfectly centered | +/- 5-15% of ideal position | HIGH -- breaks machine-like precision |
| **2. Subtle rotation** | Building not perfectly aligned to grid | +/- 1-3 degrees | HIGH -- organic feel |
| **3. Foundation settling** | Slight lean/sag | 0.5-2 degrees tilt | MEDIUM -- suggests age |
| **4. Weathering variation** | Different parts weather differently | Varies per face | HIGH -- breaks uniformity |
| **5. Material mixing** | Stone types, timber tones vary | 2-4 variants per building | HIGH -- mimics real construction |
| **6. Addition/alteration** | Obvious later additions (different style) | 1 per building | HIGH -- suggests history |
| **7. Imperfect geometry** | Walls not perfectly flat, roofs sag | +/- 0.02m to 0.05m noise | MEDIUM -- organic curves |

**Critical anti-pattern:** Never place more than 3 identical buildings in a row. Minimum variation between adjacent buildings:
- Different roof pitch (+/- 5 degrees)
- Different floor count or height
- Different window count or placement
- Different weathering level
- At least one unique detail (chimney, balcony, sign, etc.)

### 5.7 Procedural Variation Techniques

**Per-building random seed strategy:**
1. Building seed = hash(lot_position + district_type + wealth_level)
2. Use seed to drive ALL random choices for that building
3. Regenerating from same seed produces identical building
4. Changing lot position produces completely different building

**Variation budget per building type:**

| Building Type | Fixed Elements | Variable Elements |
|--------------|---------------|-------------------|
| **Tavern** | Ground floor with large door, hanging sign | Roof type, floor count, chimney position, sign design |
| **Church** | Pointed windows, tower, entrance portal | Tower height, window count, tracery style, buttress count |
| **Blacksmith** | Open forge side, chimney | Building size, chimney height, roof material |
| **House** | Door, windows, roof | Everything else: size, floors, materials, details |

---

## Integration Notes for VeilBreakers Codebase

### Current vs. Needed Constants

| System | Current State | What to Add |
|--------|--------------|-------------|
| `STYLE_CONFIGS` (5 styles) | Has basic proportions | Add arch ratio types, column proportions, tracery rules |
| `FACADE_STYLE_RULES` | Has plinth, cornice, pilaster | Add per-style window-to-wall ratios, door proportions |
| `generate_gothic_window` | Good arch curves | Add tracery subdivision rules, proportional mullion spacing |
| `generate_battlements` | Has merlons/machicolations | Add correct crenel:merlon ratio (1:3), historical dimensions |
| `_settlement_grammar.py` | Has ring districts | Add street width rules, lot dimension rules, landmark rules |
| `weathering.py` | Has 5 effects | Add directional placement rules (north-face moss, splash zones) |
| **NEW** | n/a | `GAME_SCALE_MULTIPLIERS` dict for 1.25-1.3x exaggeration |
| **NEW** | n/a | `WEATHERING_PLACEMENT_RULES` dict with directional weights |
| **NEW** | n/a | `TOWN_LAYOUT_RULES` dict with street widths, lot sizes |
| **NEW** | n/a | `VARIATION_AXES` config for anti-procedural-look techniques |

### Specific Code Corrections

1. **`generate_battlements` line 2516-2517:** `merlon_w = 0.6`, `crenel_w = 0.4` -- this gives crenel:merlon = 0.67:1. Historical ratio is 1:3 (crenel = merlon/3). Should be `crenel_w = 0.2` for accuracy, or keep current values for gameplay readability.

2. **`STYLE_CONFIGS["gothic"]["walls"]["height_per_floor"]` = 4.5:** This is reasonable for a single floor of a Gothic building. For full cathedral proportions, use ad quadratum system (height = width) which would be much taller.

3. **`STYLE_CONFIGS["gothic"]["roof"]["pitch"]` = 60:** Correct for Gothic cathedral roofs (55-65 degrees). Good.

4. **`STYLE_CONFIGS["medieval"]["roof"]["pitch"]` = 35:** Should be 45-55 for thatch, 35 is correct for tile/slate. Consider making this depend on `roof.material`.

5. **Weathering handler lacks directional placement:** Current implementation applies uniform weathering. Should weight by face orientation (north vs. south), height (base splash zone vs. exposed top), and feature proximity (drip lines under sills).

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Arch proportions | HIGH | Based on geometric construction rules documented across multiple architectural sources |
| Ad quadratum/triangulum | HIGH | Well-documented medieval proportional systems used at Milan, Bourges, Chartres |
| Wall dimensions | HIGH | Castle/fortification measurements widely documented from archaeological surveys |
| Timber frame | HIGH | Building conservation literature extensively documents historical construction |
| Weathering patterns | HIGH | Conservation science and geology provide clear rules |
| Town layout | HIGH | Bastide towns and archaeological evidence provide measured layouts |
| Game-scale exaggeration | MEDIUM | Based on industry practice (GDC talks, AAA game analysis), not formal standards |
| Variation techniques | MEDIUM | Best practices from procedural generation community, not formal research |

## Sources

### Primary (HIGH confidence)
- [Gothic Architecture - Wikipedia](https://en.wikipedia.org/wiki/Gothic_architecture) - Proportional systems, structural elements
- [Pointed Arch - Wikipedia](https://en.wikipedia.org/wiki/Pointed_arch) - Arch construction geometry, historical evolution
- [Battlement - Wikipedia](https://en.wikipedia.org/wiki/Battlement) - Crenel:merlon ratio (1:3)
- [Machicolation - Wikipedia](https://en.wikipedia.org/wiki/Machicolation) - Defensive projection terminology
- [Rose Window - Wikipedia](https://en.wikipedia.org/wiki/Rose_window) - Tracery patterns, historical diameters
- [Jettying - Wikipedia](https://en.wikipedia.org/wiki/Jettying) - Overhang construction system
- [Bastide - Wikipedia](https://en.wikipedia.org/wiki/Bastide) - Planned town lot dimensions (8m x 24m)
- [Britannica - Early Gothic](https://www.britannica.com/art/Western-architecture/Early-Gothic) - Flying buttress evolution
- [Gothic Arch Calculator](https://www.blocklayer.com/gothic-archeng) - Construction geometry verification
- [Lancet Arch Dimensions](https://www.dimensions.com/element/arch-lancet) - Specific lancet measurements

### Secondary (MEDIUM confidence)
- [Castle Walls Architecture](https://www.castlesandmanorhouses.com/architecture_03_walls.htm) - Wall thickness measurements
- [Medieval Chroniclers - Castle Walls](https://www.medievalchronicles.com/medieval-castles/medieval-castle-parts/medieval-castle-walls/) - Height data
- [Building Conservation - Timber](https://www.buildingconservation.com/articles/timber/wood93.htm) - Timber frame construction
- [Medieval Village Layout](https://medievus.com/blog/medieval-village-layout/) - Town planning principles
- [Geometry in Gothic Architecture - Medium](https://medium.com/swlh/geometry-in-gothic-architecture-3f74423bffb7) - Proportional analysis
- [Medieval Vaults Proportions](https://www.tracingthepast.org.uk/2021/04/09/designing_medieval_vaults_measurements_proportions/) - Vault geometry
- [Natural Navigator - Moss](https://www.naturalnavigator.com/the-library/the-truth-about-moss/) - Moss growth direction rules

### Tertiary (LOW confidence - marked for validation)
- Game scale exaggeration multipliers (1.25-1.3x) -- derived from analysis of AAA games, not formally published standard
- Color temperature associations by building type -- industry convention, not architectural fact
