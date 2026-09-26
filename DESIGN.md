---
name: PRism Evidence Workbench
description: A warm, evidence-led interface for reviewing pull-request risk and verification.
colors:
  primary: "#b9332d"
  primary-hover: "#982c28"
  highlight: "#ed5148"
  primary-soft: "#fff2ef"
  surface-app: "#fbf8f3"
  surface-panel: "#ffffff"
  surface-warm: "#fffefa"
  ink-primary: "#211d1b"
  ink-secondary: "#655d58"
  line: "#e5ddd6"
  verified: "#065f46"
  verified-soft: "#ecfdf5"
  caution: "#92400e"
  caution-soft: "#fffbeb"
  critical: "#9f1239"
  critical-soft: "#fff1f2"
typography:
  display:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(56px, 7.3vw, 100px)"
    fontWeight: 700
    lineHeight: 0.91
    letterSpacing: "-0.055em"
  headline:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(38px, 4.3vw, 62px)"
    fontWeight: 700
    lineHeight: 0.98
    letterSpacing: "-0.055em"
  title:
    fontFamily: "Manrope, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Manrope, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.1em"
  code:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
spacing:
  1: "4px"
  2: "8px"
  3: "12px"
  4: "16px"
  5: "20px"
  6: "24px"
  8: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface-panel}"
    rounded: "{rounded.md}"
    padding: "14px 18px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-signin:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.primary}"
    rounded: "7px"
    padding: "11px 15px"
  card:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.lg}"
    padding: "24px"
  input:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.sm}"
    height: "40px"
---

# Design System: PRism Evidence Workbench

## Overview

**Creative North Star: “The Evidence Ledger”**

PRism is a focused engineering workbench for claims that need to hold up against evidence. Warm off-white surfaces, dark brown-black ink, and precise coral accents give the product a clear identity while keeping dense review material comfortable to scan. The public landing page uses an editorial, asymmetric hero and generous section spacing to introduce the product; signed-in routes carry the same paper-and-coral palette into a persistent workspace shell and compact review surfaces.

The interface keeps findings, citations, verification state, and coverage provenance close together. Manrope handles product and interface text; IBM Plex Mono marks file paths, line references, and other traceable identifiers. Semantic review colors remain reserved for meaning: green for accepted or verified evidence, amber for caution or unverified evidence, and red/rose for high severity or failure.

**Key Characteristics:**
- Warm paper canvas, dark ink, and coral action color.
- Editorial public-page hierarchy paired with a persistent signed-in review workbench.
- Compact, addressable evidence details with monospace identifiers.
- Green, amber, and red/rose retain distinct review-state meanings.

## Colors

The palette pairs Brainfloss-inspired bright coral highlights with deep coral controls and warm neutrals; status colors continue to communicate review outcomes.

### Primary
- **Deep Coral** (`colors.primary`): High-contrast buttons, active workspace navigation, focused controls, and emphasized links. Its white-text contrast ratio is 5.88:1.
- **Deep Coral Hover** (`colors.primary-hover`): Hover state for prominent actions.
- **Bright Coral Highlight** (`colors.highlight`): Large display text accents and the PRism logo mark.
- **Coral Wash** (`colors.primary-soft`): Quiet interactive emphasis and selected review rows.

### Neutral
- **Warm Canvas** (`colors.surface-app`): Shared light page background.
- **Paper Surface** (`colors.surface-panel`): Main content cards, report panels, and public evidence previews.
- **Warm White** (`colors.surface-warm`): Signed-in sidebar and navigation surfaces.
- **Dark Ink** (`colors.ink-primary`): Main headings and high-priority interface text.
- **Reading Ink** (`colors.ink-secondary`): Supporting copy and secondary labels.
- **Warm Rule** (`colors.line`): Dividers and section boundaries.

### Semantic
- **Verified Green** (`colors.verified`, `colors.verified-soft`): Accepted coverage and citation-verified findings.
- **Caution Amber** (`colors.caution`, `colors.caution-soft`): Unknown coverage, held claims, and unverified findings.
- **Critical Rose** (`colors.critical`, `colors.critical-soft`): High-severity findings and failure/error states.

### Named Rules
**The Evidence Color Rule.** Deep coral marks controls, active navigation, and focus; bright coral is a display and logo highlight. Keep green, amber, and red/rose dedicated to their existing verification, caution, and critical states; pair each state color with a label or other visible cue.

## Typography

**Display Font:** Manrope (with sans-serif fallback)  
**Body Font:** Manrope (with sans-serif fallback)  
**Label/Mono Font:** IBM Plex Mono (with ui-monospace fallback)

**Character:** Manrope gives the product a direct, contemporary voice, with tight display tracking for the public hero and compact, readable app labels. IBM Plex Mono separates evidence identifiers from explanatory prose without making the whole interface feel like a code editor.

### Hierarchy
- **Display** (700, responsive 56–100px, 0.91 line-height): Landing-page hero headline.
- **Headline** (700, responsive 38–62px, 0.98 line-height): Major landing-page section headings.
- **Title** (600, 20px, 1.3 line-height): Review panels and content sections.
- **Body** (400, 14px, 1.5 line-height): Interface and explanatory copy; public landing-page lead copy scales to 16px with 1.7 line-height.
- **Label** (600, 10px, 0.1em tracking, uppercase when used for kickers): Editorial metadata, evidence labels, and compact section markers.
- **Code** (400, 12px, 1.5 line-height): File paths, line citations, commit hashes, and diff text.

### Named Rules
**The Addressable Evidence Rule.** Keep file paths, line numbers, and commit identifiers visually distinct in monospace wherever they identify evidence.

## Layout

The public site uses a centered responsive content column, a coral top navigation bar, and an asymmetric two-column hero that pairs the product story with a review preview. Supporting sections alternate open editorial layouts, ruled lists, comparison rows, and contained panels. At 850px and below, multi-column content stacks; the evidence preview changes to one column at 560px, and public navigation simplifies at 440px.

Signed-in pages use a persistent left workspace rail beside a fluid content area, with a compact top header and collapsible navigation on smaller screens. The dashboard remains a review workspace: the review launcher leads, repository access is a secondary panel, and review history is its own area. On review routes, the findings register is the scanning surface and the evidence inspector sits alongside it on wide screens; narrower layouts stack these regions while keeping provenance available. Use the observed 4px spacing rhythm, with 16–24px panel padding and larger gaps between major sections.

### Named Rules
**The Register-First Rule.** Keep the findings register and its selected evidence companion visually connected, with the register leading the scan.

## Elevation & Depth

Depth is a restrained hybrid of warm tonal surfaces, fine borders, and small shadows. The landing-page evidence preview and inspector use a diffuse, low shadow; signed-in review panels primarily use borders and surface contrast, with stronger shadow limited to transient menus or sticky content that needs separation.

### Shadow Vocabulary
- **Evidence preview** (`0 22px 48px -36px rgba(67,39,31,.4)`): Public review-preview panels.
- **Inspector preview** (`0 22px 44px -36px rgba(67,39,31,.4)`): Raised landing-page inspector mockup.
- **Menu lift** (`shadow-lg shadow-slate-900/10`): Transient action menus.

### Named Rules
**The Quiet Surface Rule.** Let borders and warm surface shifts group ordinary content; use diffuse shadows for preview emphasis and temporary overlays.

## Shapes

Controls have softly rounded corners (6–8px); review panels and preview cards use 10–12px corners, with larger overview surfaces reaching 16px. Thin warm borders define contained areas. The deep-coral marketing navigation has a compact 11px radius. Small status badges may be pill-shaped; large work areas remain panel-like rather than pill forms.

## Components

### Buttons
- **Character:** Clear, compact actions with a brief color and lift response.
- **Primary:** Deep coral fill, white bold label, and 14px by 18px padding on the public landing action.
- **Sign-in:** White button set into the coral marketing bar, with deep coral text and a 7px radius.
- **Workspace actions:** Compact controls use coral or deep coral according to emphasis; secondary actions use white or transparent surfaces with a fine warm border.
- **Hover / Focus:** The landing action darkens to deep coral hover and lifts by 1px; global keyboard focus uses a visible 2px deep coral outline with 3px offset.

### Chips
- **Style:** Compact, text-first labels; signed-in review statuses use soft backgrounds and darker text.
- **State:** Green is verified/accepted, amber is unverified/unknown, and red/rose is critical/failed. Preserve the label alongside color.

### Cards / Containers
- **Corner Style:** Soft 10–12px corners, with 16px on larger overview surfaces.
- **Background:** White or warm white against the warm canvas.
- **Shadow Strategy:** Borders and tonal differences do most of the work; use diffuse lift for public evidence previews.
- **Border:** Fine warm-neutral rules.
- **Internal Padding:** Commonly 16–24px; dense rows use tighter spacing.

### Inputs / Fields
- **Style:** White fill, neutral border, 6px corners, and 40px control height for search and filter fields.
- **Focus:** Coral border/ring with the global visible focus outline.
- **Error / Disabled:** Keep the field label visible; use the semantic error tone for errors and visibly lower emphasis for disabled controls.

### Navigation
- **Public:** Deep coral rounded bar with white brand and section links; the sign-in action is a white inset button.
- **Signed-in:** Persistent sidebar with icon-and-label destinations; active navigation uses deep coral fill and white text. A compact header exposes a labeled menu on small screens.
- **Responsive:** Public links simplify on narrow screens; signed-in navigation moves into an explicit mobile menu.

### Findings Register and Evidence Inspector

The register uses a compact header, search and filters, severity, finding, category, file, and evidence columns. Selecting a finding updates the adjacent inspector with the claim, citations, diff context, and verification result. The unverified appendix stays visually distinct and includes the reason a claim was held back.

### Coverage Provenance

Show whether coverage evidence was accepted, rejected, or unavailable, and tie it to the pull request head commit. Missing or mismatched evidence remains unknown; never imply coverage completeness from an absent artifact.

## Do's and Don'ts

### Do:
- **Do** use deep coral for controls, active navigation, and focus; reserve bright coral for large display and logo highlights.
- **Do** keep finding claims, citations, verification state, and coverage provenance close together.
- **Do** keep file paths, line numbers, and commit identifiers in monospace.
- **Do** pair green, amber, and red/rose status colors with explicit labels or other visible cues.
- **Do** keep authored report previews visibly synthetic and benchmark views honest when measured results are unavailable.

### Don't:
- **Don't** use the cursorarc.com reference's colors; the structural reference informs layout only.
- **Don't** use bright coral as the fill for small white-text controls; use the high-contrast deep coral token.
- **Don't** replace the Brainfloss-inspired coral and warm-paper palette with cobalt or a cool gray system.
- **Don't** repurpose verification colors as decoration or imply unsupported benchmark, coverage, or customer outcomes.
- **Don't** make the signed-in product resemble a generic AI chat wrapper or an unsupported metrics dashboard.
