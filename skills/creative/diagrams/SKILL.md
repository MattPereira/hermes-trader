---
name: diagrams
description: "Technical diagrams: dark-themed SVG architecture diagrams and hand-drawn Excalidraw JSON diagrams. Use when creating system architecture, flowcharts, sequence diagrams, or concept maps."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [diagrams, architecture, excalidraw, svg, html, flowcharts, visualization, infrastructure]
    related_skills: [sketch, claude-design]
---

# Technical Diagrams

Two diagramming approaches — choose based on what the user needs.

| Need | Use | Output |
|------|-----|--------|
| Dark-themed architecture/cloud/infra diagrams | § Architecture Diagrams | Standalone HTML with inline SVG |
| Hand-drawn style flowcharts, sequence diagrams | § Excalidraw | `.excalidraw` JSON file |

---

## Architecture Diagrams (Dark SVG)

Generate professional, dark-themed technical architecture diagrams as standalone HTML files with inline SVG. No external tools, no API keys, no rendering libraries.

### Best suited for
- Software system architecture (frontend/backend/database layers)
- Cloud infrastructure (VPC, regions, subnets, managed services)
- Microservice / service-mesh topology
- Database + API map, deployment diagrams

### Look elsewhere for
- Hand-drawn whiteboard sketches → Excalidraw (below)
- Scientific subjects, physical objects → specialized skills
- Animated explainers → animation skills

### Workflow

1. User describes system architecture (components, connections, technologies)
2. Generate HTML following the design system below
3. Save with `write_file` to `.html` file
4. User opens in any browser — works offline, no dependencies

### Design System

**Color Palette (Semantic Mapping):**

| Component Type | Fill (rgba) | Stroke (Hex) |
|:---|:---|:---|
| Frontend | `rgba(8, 51, 68, 0.4)` | `#22d3ee` (cyan) |
| Backend | `rgba(6, 78, 59, 0.4)` | `#34d399` (emerald) |
| Database | `rgba(76, 29, 149, 0.4)` | `#a78bfa` (violet) |
| AWS/Cloud | `rgba(120, 53, 15, 0.3)` | `#fbbf24` (amber) |
| Security | `rgba(136, 19, 55, 0.4)` | `#fb7185` (rose) |
| Message Bus | `rgba(251, 146, 60, 0.3)` | `#fb923c` (orange) |
| External | `rgba(30, 41, 59, 0.5)` | `#94a3b8` (slate) |

**Typography:** JetBrains Mono (Google Fonts), 12px names, 9px sublabels, 8px annotations
**Background:** Slate-950 (`#020617`) with subtle 40px grid pattern
**Components:** Rounded rectangles (`rx="6"`) with 1.5px strokes, double-rect masking for semi-transparent fills

### Document Structure
1. **Header:** Title with pulsing dot indicator and subtitle
2. **Main SVG:** Diagram in rounded border card
3. **Summary Cards:** Grid of three cards for high-level details
4. **Footer:** Minimal metadata

### Connection Rules
- Draw arrows early (behind component boxes)
- Security flows: dashed lines in rose color
- Security groups: dashed (`4,4`), rose
- Regions: large dashed (`8,4`), amber, `rx="12"`
- Legend: outside all boundary boxes, 20px below lowest boundary

### Output Requirements
- Single self-contained `.html` file
- All CSS and SVG inline (except Google Fonts)
- No JavaScript — pure CSS for animations
- Must render in any modern browser

---

## Excalidraw Diagrams (Hand-Drawn JSON)

Create diagrams by writing Excalidraw element JSON and saving as `.excalidraw` files. Drag-and-drop onto [excalidraw.com](https://excalidraw.com) for viewing/editing. No accounts, no API keys.

### Workflow

1. Write elements JSON — array of Excalidraw element objects
2. Save with `write_file` to `.excalidraw` file
3. Optionally upload for shareable link: `python references/scripts/upload.py diagram.excalidraw`

### Envelope Format
```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "hermes-agent",
  "elements": [ ... ],
  "appState": { "viewBackgroundColor": "#ffffff" }
}
```

### Required Fields (all elements)
`type`, `id` (unique string), `x`, `y`, `width`, `height`

### Element Types

**Rectangle:** `{ "type": "rectangle", "id": "r1", "x": 100, "y": 100, "width": 200, "height": 100 }`
- `roundness: { "type": 3 }` for rounded corners

**Ellipse:** `{ "type": "ellipse", ... }`

**Diamond:** `{ "type": "diamond", ... }`

**Arrow:** `{ "type": "arrow", ..., "points": [[0,0],[200,0]], "endArrowhead": "arrow" }`

### Labeled Shapes (Container Binding)

⚠️ **Do NOT use `"label": { "text": "..." }`** — this is NOT valid. Use container binding:

```json
{ "type": "rectangle", "id": "r1", "x": 100, "y": 100, "width": 200, "height": 80,
  "roundness": { "type": 3 }, "backgroundColor": "#a5d8ff", "fillStyle": "solid",
  "boundElements": [{ "id": "t_r1", "type": "text" }] },
{ "type": "text", "id": "t_r1", "x": 105, "y": 110, "width": 190, "height": 25,
  "text": "Hello", "fontSize": 20, "fontFamily": 1, "strokeColor": "#1e1e1e",
  "textAlign": "center", "verticalAlign": "middle",
  "containerId": "r1", "originalText": "Hello", "autoResize": true }
```

### Arrow Bindings
```json
{ "type": "arrow", ..., 
  "startBinding": { "elementId": "r1", "fixedPoint": [1, 0.5] },
  "endBinding": { "elementId": "r2", "fixedPoint": [0, 0.5] } }
```

### Z-Order & Drawing Order
Array order = z-order (first = back, last = front). Emit progressively: background → shape → its bound text → its arrows → next shape.

### Sizing
- Minimum `fontSize`: 16 for body, 20 for titles, 14 for secondary annotations
- Minimum shape size: 120x60 for labeled shapes
- Leave 20-30px gaps between elements

### Color Palette

| Use | Fill Color | Hex |
|-----|-----------|-----|
| Primary / Input | Light Blue | `#a5d8ff` |
| Success / Output | Light Green | `#b2f2bb` |
| Warning / External | Light Orange | `#ffd8a8` |
| Processing / Special | Light Purple | `#d0bfff` |
| Error / Critical | Light Red | `#ffc9c9` |
| Notes / Decisions | Light Yellow | `#fff3bf` |
| Storage / Data | Light Teal | `#c3fae8` |

### Tips
- Use color palette consistently
- Text contrast is CRITICAL — minimum text color on white: `#757575`
- Do NOT use emoji — they don't render in Excalidraw's font
- For dark mode, see `references/excalidraw-dark-mode.md`
- For full color tables, see `references/excalidraw-colors.md`
- For larger examples, see `references/excalidraw-examples.md`

### Upload Script
Located at `references/scripts/upload.py`. Requires `cryptography` pip package.
