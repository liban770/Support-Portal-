---
name: Academic Support Operations
colors:
  surface: '#f9f9ff'
  surface-dim: '#d6dae7'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f3ff'
  surface-container: '#eaedfb'
  surface-container-high: '#e4e8f5'
  surface-container-highest: '#dfe2f0'
  on-surface: '#171c25'
  on-surface-variant: '#544246'
  inverse-surface: '#2c303b'
  inverse-on-surface: '#edf0fe'
  outline: '#877276'
  outline-variant: '#dac0c5'
  surface-tint: '#9c3e5c'
  primary: '#4d0021'
  on-primary: '#ffffff'
  primary-container: '#6b1736'
  on-primary-container: '#ee809f'
  inverse-primary: '#ffb1c4'
  secondary: '#605d65'
  on-secondary: '#ffffff'
  secondary-container: '#e6e0ea'
  on-secondary-container: '#66636b'
  tertiary: '#002a0e'
  on-tertiary: '#ffffff'
  tertiary-container: '#00421b'
  on-tertiary-container: '#74af7d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffd9e0'
  primary-fixed-dim: '#ffb1c4'
  on-primary-fixed: '#3f001a'
  on-primary-fixed-variant: '#7e2644'
  secondary-fixed: '#e6e0ea'
  secondary-fixed-dim: '#cac5ce'
  on-secondary-fixed: '#1c1b21'
  on-secondary-fixed-variant: '#48454d'
  tertiary-fixed: '#b3f2ba'
  tertiary-fixed-dim: '#97d59f'
  on-tertiary-fixed: '#00210a'
  on-tertiary-fixed-variant: '#165128'
  background: '#f9f9ff'
  on-background: '#171c25'
  surface-variant: '#dfe2f0'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  caption:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

The design system establishes an institutional, accessible, and structured environment tailored for university administration, staff, and students. The interface emphasizes institutional prestige balanced with modern software utility: it communicates academic authority, procedural clarity, and efficiency without feeling bureaucratic or antiquated.

The aesthetic philosophy draws primarily from **Corporate / Modern SaaS** with quiet editorial touches:
- **Tone:** Authoritative, calm, transparent, and service-oriented.
- **Visual Cadence:** High density of organized information supported by generous component breathing room, clean lines, and crisp division of procedural states.
- **Emotional Target:** Trustworthy and reassuring. Students feel heard and guided; administrators feel equipped with clear operational leverage and low visual fatigue during high-volume workflows.

## Colors

The color palette centers on university heritage anchored by clear operational utility. 

- **Primary (`#6B1736` - University Maroon):** Reserved for core brand recognition, focal action triggers, selected navigation rails, and verified markers.
- **Secondary / Headings (`#25232A` - Charcoal):** High-contrast neutral for dominant typography, labels, and administrative data points. Replaces pure black to reduce eye strain while maintaining WCAG AAA legibility.
- **Muted Neutral (`#737783` - Slate Gray):** Used for metadata, secondary descriptions, timestamps, and input placeholders.
- **Surfaces & Canvases:**
  - App Canvas / Page Background: Off-white (`#F7F7F9`) to anchor foreground panels.
  - Surface / Panels / Cards: Pure White (`#FFFFFF`).
  - Dividers & Outlines: Subtle Gray (`#E5E7EB`).
- **Ticket Lifecycle & Status Palette:** Status badges pair soft background tints with matching deep text values for contrast:
  - **Submitted:** Surface `#E2E8F0` / Text `#334155`
  - **Under Review:** Surface `#DBEAFE` / Text `#1E40AF`
  - **In Progress:** Surface `#F3E8FF` / Text `#6B21A8`
  - **Waiting for Student:** Surface `#FEF3C7` / Text `#92400E`
  - **Escalated:** Surface `#FFEDD5` / Text `#9A3412`
  - **Resolved:** Surface `#DCFCE7` / Text `#166534`
  - **Rejected:** Surface `#FEE2E2` / Text `#991B1B`
  - **Closed:** Surface `#F1F5F9` / Text `#475569`

## Typography

The typography relies entirely on **Inter** to maximize screen legibility across tabular records, complex operational dashboards, and student documentation. 

- **Headlines:** Use tightened negative tracking (`-0.01em` to `-0.02em`) with medium-to-bold weights to convey editorial authority.
- **Body:** Neutral tracking at `14px` and `16px` optimizes reading efficiency across academic requests and lengthy review timelines.
- **Labels & Metadata:** Feature deliberate micro-tracking (`+0.01em` to `+0.03em`) in medium weights to prevent uppercase badges, system tags, and table column headers from collapsing at small sizes.

## Layout & Spacing

The application architecture follows a **fluid grid** paradigm pinned inside a maximum content width of 1440px for desktop workflows, shifting into flexible single-column flows on mobile.

- **Desktop (1024px+):** 12-column system, `1.5rem` (24px) gutters, and `2rem` (32px) screen margins. A fixed 260px administrative navigation sidebar pins to the left while central content and contextual action sidebars flex within the grid.
- **Tablet (768px - 1023px):** 8-column layout, `1.5rem` gutters, and `1.5rem` margins. The navigation collapses into an overlay or icon rail.
- **Mobile (<768px):** 4-column layout, `1rem` (16px) gutters, and `1rem` (16px) margins. Multi-column forms and split ticket-thread panels collapse to a vertical, single-stack flow.

## Elevation & Depth

Visual hierarchy uses a refined combination of **low-contrast outlines** and **subtle ambient shadows** to create a structured, professional environment.

- **Flat Canvas:** Background base sits at `#F7F7F9` without shadows or borders.
- **Cards & Data Tables:** Surfaces sit at `#FFFFFF` paired with a sharp `1px solid #E5E7EB` border and an ultra-soft micro-shadow (`0 1px 2px 0 rgba(0, 0, 0, 0.05)`). This delineates panels without introducing visual weight.
- **Interactive Modals & Slide-overs:** Elevated with a diffused layer (`0 10px 15px -3px rgba(37, 35, 42, 0.08), 0 4px 6px -2px rgba(37, 35, 42, 0.04)`) alongside the `#E5E7EB` perimeter border to emphasize direct focus over blurred backdrops.

## Shapes

The design system employs a **Rounded** shape language calibrated to keep administrative tools crisp while preventing cards from appearing harsh or utilitarian:

- **Cards and Major Panels:** Use `1.5rem` (`rounded-xl` equivalent in component logic) or `1rem` for compact containers to soften data-dense pages.
- **Buttons, Form Inputs, and Dropdowns:** Use standard `0.5rem` (8px) corner curvature, reinforcing a stable, aligned boundary for tabular interfaces.
- **Status Badges & Chips:** Use a full pill radius (`9999px`) to create clear differentiation between actionable inputs and informational status indicators.

## Components

### Buttons
- **Primary:** Solid `#6B1736` fill, `#FFFFFF` text, `0.5rem` border radius, subtle hover transition to `#54122A`. Focus state uses a `2px` offset ring in `#6B1736`.
- **Secondary:** Surface `#FFFFFF`, border `1px solid #E5E7EB`, text `#25232A`. Hover transitions surface to `#F7F7F9`.
- **Tertiary/Ghost:** Transparent surface, text `#6B1736`, hover surface `rgba(107, 23, 54, 0.06)`.

### Form Inputs & Selects
- Height standard is 40px for desktop operational balance.
- Background `#FFFFFF`, border `1px solid #E5E7EB`, radius `0.5rem`, text `#25232A`, placeholder `#737783`.
- Active focus state features an outline transition to `#6B1736` with a faint `3px` translucent maroon glow (`rgba(107, 23, 54, 0.12)`).

### Status Badges & Chips
- Compact pill height (24px), font size `12px`, weight `500`.
- Text and backgrounds use specified semantic pairing combinations (e.g., Escalated uses `#FFEDD5` background with `#9A3412` text).
- Free of outer borders to keep lists legible and uncluttered.

### Cards & Panels
- White `#FFFFFF` background, border `1px solid #E5E7EB`, radius `1rem` (`rounded-xl`), padding `1.5rem`.
- Divided header and footer zones use horizontal borders in `#E5E7EB` with `0.75rem` vertical spacing.

### Data Tables
- Table header: `#F7F7F9` background, `12px` uppercase tracking label in `#737783`, border-bottom `1px solid #E5E7EB`.
- Row cells: Height 48px, text `14px` `#25232A`, bottom border `1px solid #F1F5F9`. Hover state shifts cell row to `#F7F7F9`.

### Ticket Timeline / Activity Feed
- Left-aligned `2px` vertical connecting line in `#E5E7EB`.
- Circular nodal avatars (32px) with `#FFFFFF` borders.
- Message cards set within secondary borders (`#E5E7EB`) with muted timestamp headers.