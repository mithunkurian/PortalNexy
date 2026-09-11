```markdown
# Design System Specification: The Executive Monolith

This document outlines the visual language and structural principles for a high-end, executive-grade digital workspace. Moving away from the traditional "green for growth" executive tropes, this system leverages a deep, sophisticated Navy Blue to convey authority, stability, and intellectual depth.

---

## 1. Creative North Star: "The Digital Atelier"
The design system is built on the concept of **The Digital Atelier**. It treats the UI not as a collection of widgets, but as a curated, high-end physical workspace. 

### The Editorial Shift
To achieve a "signature" feel, we break the traditional SaaS "box-in-a-box" layout.
*   **Intentional Asymmetry:** Use the 8.5rem (24) spacing token to create wide, asymmetrical margins that allow content to breathe, mimicking a luxury editorial magazine.
*   **Tonal Depth:** We abandon 1px borders in favor of "Tonal Islands"—grouping related content via subtle shifts in surface color rather than rigid lines.
*   **The Overlap:** Elements should occasionally "break the grid" by overlapping surface containers, creating a sense of physical layering and sophisticated depth.

---

## 2. Color Strategy & The "No-Line" Rule

The palette is anchored by `#182053` (Primary Container), a navy so deep it acts as a neutral anchor, allowing the Manrope typography to stand out with crystalline clarity.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning or containment. 
*   **Boundaries:** Use `surface-container-low` (#f6f2f8) sections sitting on a `surface` (#fbf8fd) background. 
*   **The Transition:** Contrast is achieved through the 4%–12% shift in tonal value between nested containers, never through a stroke.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked premium paper stocks:
1.  **Base:** `surface` (#fbf8fd) – The foundation.
2.  **Navigation/Sidebar:** `surface-container-low` (#f6f2f8) – Receded.
3.  **Primary Workspace:** `surface-container-lowest` (#ffffff) – The "Active Paper" where the user works.
4.  **Floating Elements:** `surface-bright` (#fbf8fd) with a glassmorphism blur.

### Glass & Gradient
To provide "visual soul," use subtle radial gradients on Hero backgrounds:
*   **Primary Gradient:** From `primary` (#01073e) to `primary-container` (#182053). 
*   **Glassmorphism:** For floating modals or dropdowns, use `surface-container-lowest` at 80% opacity with a `20px` backdrop-blur.

---

## 3. Typography: The Manrope Scale

Manrope is used as a modern geometric sans-serif that balances technical precision with warmth.

*   **Display (Editorial Impact):** `display-lg` (3.5rem) should be used sparingly with `-0.04em` letter spacing to create a high-fashion, "dense" headline look.
*   **Headline (The Authority):** `headline-md` (1.75rem) serves as the primary anchor for page sections.
*   **The Body-Label Contrast:** Pair `body-lg` (1rem) for reading with `label-md` (0.75rem) in **All Caps** with `0.1em` letter spacing for metadata. This creates a functional, executive hierarchy.

---

## 4. Elevation & Depth: Tonal Layering

We eschew traditional drop shadows for **Ambient Occlusion** and **Layered Surfaces**.

*   **The Layering Principle:** Depth is achieved by placing a `surface-container-lowest` card on a `surface-container-high` background. This creates a natural "lift" without visual noise.
*   **Ambient Shadows:** When an object must float (e.g., a primary action menu), use a diffused shadow: 
    *   `box-shadow: 0 24px 48px rgba(13, 22, 73, 0.06);` 
    *   Note: The shadow is tinted with the `on-primary-fixed` (#0d1649) color to ensure it feels like a natural part of the navy ecosystem.
*   **The Ghost Border Fallback:** If a border is required for accessibility, use the `outline-variant` token at **15% opacity**. High-contrast outlines are strictly forbidden.

---

## 5. Component Signature

### Buttons
*   **Primary:** Background: `primary-container` (#182053); Text: `on-primary` (#ffffff). Shape: `md` (0.375rem). No shadow on rest; subtle `surface-tint` glow on hover.
*   **Tertiary (The Executive Link):** Text: `primary-container` (#182053). No background. Underline is a 2px `primary-fixed` (#dfe0ff) bar that appears only on hover.

### Cards & Lists
*   **No Dividers:** Lists should never use horizontal lines. Use `spacing-4` (1.4rem) between items. Use a `surface-container-highest` background on hover to define the interactive area.
*   **Cards:** Use `rounded-xl` (0.75rem) and define the edge using a background color shift (e.g., White card on a `surface-container-low` background).

### Input Fields
*   **Style:** Modern "Bottom-Line" or "Soft-Box." Use `surface-container-highest` as the field background with no border. On focus, the bottom edge gains a 2px `primary` (#01073e) accent.

---

## 6. Do’s and Don’ts

| **DO** | **DON'T** |
| :--- | :--- |
| **Do** use `20` (7rem) and `24` (8.5rem) spacing to create "The Void"—intentional white space that signals luxury. | **Don't** use 1px solid borders (`#CCCCCC` or similar) to separate content sections. |
| **Do** use `primary-fixed-dim` (#bbc3ff) for subtle accents or icons against the dark navy. | **Don't** use pure black (#000000) for text. Use `on-surface` (#1b1b1f) for better legibility. |
| **Do** overlap a `surface-container-lowest` card across two different background color sections. | **Don't** use traditional "Material Design" high-opacity shadows. Keep them "Ambient" (4-8%). |
| **Do** use glassmorphism for top-level navigation bars to allow page colors to bleed through. | **Don't** crowd the interface. If an element feels "stuck," add two levels of spacing from the scale. |

---

## 7. Signature Spacing Philosophy
Executive layouts are defined by their "Gutter Logic." Every major layout section must be padded with at least `spacing-12` (4rem). Information density should be low—this is a workspace for clarity and decision-making, not a data-entry terminal. Use the **0.75rem (xl)** corner radius to soften the authoritative navy, making the high-end environment feel approachable yet disciplined.```