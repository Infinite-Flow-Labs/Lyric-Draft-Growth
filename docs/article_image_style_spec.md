# Article Image Style Spec

This spec defines the default image system for X Articles produced by the pipeline.

It is based on a decomposition of these reference articles:

- `https://x.com/dotey/status/2035015960537485507`
- `https://x.com/dotey/status/2029969547927658673`

The goal is not "pretty AI art". The goal is a reusable editorial image system:

- one cover image that explains the article's main idea at a glance
- several inline images that reset attention at major section transitions
- a consistent knowledge-graphic visual language across articles

## Scope

This style spec is global. It is not family-specific.

It should work for:

- `podcast`
- `official_x`
- `article_x`

## Core Visual Direction

### Overall feel

- editorial, explanatory, and calm
- knowledge-card / infographic first
- light hand-drawn flat illustration feel
- not glossy startup marketing
- not cyberpunk / neon / sci-fi wallpaper
- readable on mobile first

### Background

- warm white
- cream
- light beige paper-like field

Avoid:

- dark backgrounds by default
- pure stark white with no warmth
- heavy gradients

### Palette

Use a restrained palette with 3-5 main colors:

- warm orange
- coral red
- teal / mint green
- light gray
- dark gray line work

Recommended palette behavior:

- one warm accent for action / emphasis
- one cool accent for system / structure
- neutral base for cards, labels, and background

Avoid:

- rainbow palettes
- saturated blue "AI" gradients
- too many competing accents

### Illustration language

- simple flat shapes
- rounded cards and modules
- arrows, connectors, paths, and boxes
- small icon-level objects only when they clarify meaning
- light linework and soft shadows at most

Preferred recurring motifs:

- quadrants
- step flows
- stage transitions
- files / folders / blocks
- pipelines
- side-by-side comparisons
- layered system diagrams

Avoid:

- photorealistic people
- generic robots as main subject
- abstract glowing chips / neural mesh / digital rain
- cinematic poster compositions

## Cover Image Rules

### Job of the cover

The cover image must do all of the following:

- communicate the article's core idea before reading
- establish the visual language for the rest of the article
- compress the article into one system, framework, or comparison

### Preferred cover types

Choose one primary cover structure:

- quadrant map
- stage evolution diagram
- workflow map
- comparison board
- layered system map
- before/after transition map

### Cover composition

- wide editorial banner
- target aspect ratio: `5:2`
- central diagram on left or center-left
- headline block on right or integrated with diagram
- enough empty space for legibility

### Cover text rules

- Chinese headline can appear inside the image
- headline should be short and direct
- one supporting subtitle is enough
- the image must still work if the viewer only scans it for 1 second

Avoid:

- paragraph text inside the image
- crowded labels everywhere
- more than 4-6 labeled nodes in the main structure

## Inline Image Rules

### Job of inline images

Inline images are not decorative breaks.

Each inline image should do one of these jobs:

- reset attention at a major section transition
- summarize a new concept block
- explain a mechanism
- compare two approaches
- visualize a workflow or system evolution
- make a dense section skimmable

### Insertion rhythm

Insert images by structural transition, not by word count.

Default rule:

- 1 cover image per article
- 1 inline image after the early framing section
- then roughly 1 image per major `H2` section
- no image for sections that add no new structure

Good insertion points:

- after the opening problem statement, before the first main framework
- at the start of each major section
- after a long dense explanatory section, if a visual reset is needed

Avoid:

- inserting images every few paragraphs
- placing two images too close without a strong structural reason
- ending the article with a decorative image unless the conclusion is itself a summary framework

### Preferred inline image types

- section reset diagram
- process flow
- concept comparison
- layered stack diagram
- file / artifact map
- evolution timeline
- example breakdown

## Information Density Rules

Images should simplify, not duplicate the full section text.

Each image should usually encode:

- one main concept
- 2-4 labeled sub-points
- one directional logic, comparison, or relationship

Avoid:

- stuffing the whole section into the image
- tiny unreadable labels
- too many arrows and nodes

## Typography Rules Inside Images

- strong primary heading
- one secondary supporting line at most
- labels should be short
- prioritize scan speed over completeness

Avoid:

- multi-line paragraphs inside diagrams
- tiny footnotes
- decorative typography experiments

## Image Placement Heuristics by Article Type

These are heuristics, not hard family rules.

### Framework / decision articles

- cover: framework summary diagram
- inline: one image per framework branch, quadrant, or decision tier

### Workflow / tool articles

- cover: end-to-end workflow map
- inline: one image for each major stage or redesign step

### Opinion / interpretation articles

- cover: key tension visualized as a comparison or transition
- inline: use fewer images, only where a new mental model is introduced

## Anti-Patterns

Do not generate:

- generic AI wallpaper
- random "tech" images unrelated to section meaning
- cover art that only repeats the title without structure
- inline art that exists only to beautify
- image styles that change radically inside one article
- low-information illustrations that add no skimmability

## Production Default

Until a different profile is explicitly selected, the default house style is:

- `editorial knowledge graphic`
- warm light background
- orange + teal accent system
- flat diagram-first composition
- short labels
- high mobile legibility
