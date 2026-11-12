---
version: alpha
name: Romanian Archival Editorial
description: Warm parchment archival catalog design system for unindexed Romanian historical PDFs.
colors:
  canvas: "#FDFBF7"
  surface: "#FFFFFF"
  surface-subtle: "#F8F5EE"
  primary: "#0F172A"
  secondary: "#475569"
  tertiary: "#9A3412"
  tertiary-hover: "#7C2D12"
  tertiary-tint: "#FFF7ED"
  border: "#E2E8F0"
  border-strong: "#CBD5E1"
  success: "#166534"
  danger: "#991B1B"
typography:
  h1:
    fontFamily: Newsreader, Source Serif 4, Georgia, serif
    fontSize: 2.25rem
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  h2:
    fontFamily: Newsreader, Source Serif 4, Georgia, serif
    fontSize: 1.375rem
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  body-md:
    fontFamily: Inter, system-ui, sans-serif
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: Inter, system-ui, sans-serif
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.45
  mono-sm:
    fontFamily: ui-monospace, SFMono-Regular, Menlo, monospace
    fontSize: 0.8125rem
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: 4px
  md: 8px
  lg: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: 12px
    height: 44px
  button-primary-hover:
    backgroundColor: "{colors.tertiary-hover}"
    textColor: "#FFFFFF"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: 12px
    height: 44px
  card-record:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: 16px
  badge-source:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.sm}"
    padding: 4px
  badge-period:
    backgroundColor: "{colors.tertiary-tint}"
    textColor: "{colors.tertiary}"
    rounded: "{rounded.sm}"
    padding: 4px
---

## Overview

Romanian Archival Editorial pairs warm parchment surfaces with disciplined Swiss grid typography for scanning and inspecting historical document catalogs without visual fatigue.

## Colors

- **Canvas (`#FDFBF7`):** Warm archival paper canvas that softens glare during long bibliographic sessions.
- **Surface (`#FFFFFF`):** Crisp card and inspector background providing subtle elevation against parchment.
- **Primary (`#0F172A`):** Slate 900 ink delivering >14:1 contrast on white and parchment.
- **Secondary (`#475569`):** Slate 600 muted metadata text meeting WCAG AA/AAA contrast (>7:1 on white).
- **Tertiary (`#9A3412`):** Archival Terracotta used exclusively for primary actions (Copilot handoff, active filters, focus rings).

## Typography

Editorial serif (`Newsreader` / `Source Serif 4` / `Georgia`) distinguishes historical document titles and catalog headings from modern UI controls (`Inter` / `system-ui`). Tabular numerals (`font-variant-numeric: tabular-nums`) keep publication years, record counts, and SHA checksums aligned across columns.

## Layout

Built on a strict 8pt spacing grid (`4px`, `8px`, `16px`, `24px`, `32px`, `48px`). The Explore surface leads immediately with a compact masthead, sticky faceted search toolbar, scannable record list, and slide-over document inspector.

## Shapes

Restrained corner radii (`4px` badges, `8px` cards/controls, `12px` panels) avoid pill-heavy SaaS aesthetics while preserving clean touch affordances.

## Components

- All interactive buttons, filter selects, and links enforce a `44px` minimum hit target height (`min-height: 44px`).
- Focus rings use high-contrast `2px solid #9A3412` outlines with `2px` offset via `:focus-visible`.
- Iconography uses crisp inline SVG strokes only; no emoji icons.

## Do's and Don'ts

- **Do** validate every external URL in client-side JS (`https:` only, non-loopback) before enabling Copilot or PDF links.
- **Do** preserve diacritic-insensitive Romanian search (`ăâîșț` / `şţ`).
- **Don't** add centered marketing hero sections, decorative gradients, or arbitrary monument stats.
