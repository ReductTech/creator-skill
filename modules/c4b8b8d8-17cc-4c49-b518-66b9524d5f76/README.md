# ICTone Figures 1–3

Editable React / HTML / SVG reconstructions of Figures 1, 2, and 3 in `ICTone_CR.pdf`.

## Preview

The preview uses port **5176**. Commands below run from the `creator-paper/` repository root.

- [Figure 1: Showcases](http://127.0.0.1:5176/?course=c4b8b8d8-17cc-4c49-b518-66b9524d5f76&view=ppt&page=e47ad853-d766-47d4-81ed-f2010270a665)
- [Figure 2: Dataset construction](http://127.0.0.1:5176/?course=c4b8b8d8-17cc-4c49-b518-66b9524d5f76&view=ppt&page=d4d982cc-62a2-4b36-b80d-9e6a7d85482b)
- [Figure 3: Scorer training](http://127.0.0.1:5176/?course=c4b8b8d8-17cc-4c49-b518-66b9524d5f76&view=ppt&page=ecd21b35-097b-4d71-95d3-ad61e1d04750)
- [All three pages](http://127.0.0.1:5176/?course=c4b8b8d8-17cc-4c49-b518-66b9524d5f76&view=guide)

## Editing

| File | Purpose |
| --- | --- |
| `pages/ShowcasesPage/ShowcasesPage.tsx` | Eight triplets; 24 independent photos |
| `pages/DatasetPipelinePage/DatasetPipelinePage.tsx` | Collection, presets, scorers, filtering, triplets |
| `pages/ScorerTrainingPage/ScorerTrainingPage.tsx` | Two training stages, sample pairs, encoders, loss labels |
| `FigureElements.tsx` | Shared photo, arrow, cube and rejection-mark elements |
| `figures.css` | Figure sizing and typography |
| `photos.ts` | Explicit asset imports |
| `assets/photos/` | 68 photo assets extracted from the PDF |
| `assets/source-manifest.json` | Original figure and crop coordinates for every photo |
| `outlines.json` | Three stable page UUIDs, titles and entry metadata |

The full figures are **not** embedded screenshots. Photos are independently cropped from the original embedded PDF images without synthesis or sharpening. Labels, arrows, frames, icons and geometric shapes are editable elements. Figure 1 consists entirely of independent photographic elements, matching its source layout.

The source PDF figures were located on PDF pages 2, 5 and 6. Per-photo source coordinates are recorded in `assets/source-manifest.json`.

## Preview setup

Install Node.js 24 or newer from the [official download page](https://nodejs.org/en/download). From the repository root, install dependencies if needed and start the preview:

```sh
npm --prefix player-preview ci
npm --prefix player-preview run dev -- --host 127.0.0.1 --port 5176 --strictPort
```

If dependencies are already available, skip the installation command. These commands use the existing project preview configuration. Machine-specific settings belong in local configuration files, not in shared documentation.

See the repository [README](../../README.md) and [drawing instructions](../../SKILL.md) for setup, relative paths and the paper-figure workflow.

Basic source checks, TypeScript checks, local esbuild bundles and browser checks passed for the current pages: image loading, navigation, Guide order and figure bounds. A full isolated production build was not verified.
