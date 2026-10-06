# The design proposal

Present this before you edit the browser. Keep it compact. Wait for approval.

## Required contents

1. **Homepage and navigation hierarchy.** The proposed landing page, and the path from it to
   a collection.
2. **Terminology changes.** Each stock STAC or Portolan word you replace, and the publisher
   word that replaces it. Name the locale key for each one.
3. **Visual tokens and reused elements.** The palette, the fonts, the spacing, and the
   publisher assets you reuse. Give the source of each value.
4. **Catalog-derived navigation.** The topics, departments, tags, or statistics you propose,
   and the count of collections that carry each one.
5. **Card and thumbnail presentation.** The card layout, and how a thumbnail fits the card.
6. **Collection page changes.**
7. **Expected custom code.** The components you expect to add or change, and the approved
   requirement that each one meets.
8. **Verification set.** The pages, collections, and interface states you will check.
9. **What you do not copy** from the publisher site, and why.
10. **Known catalog limits** that the interface cannot correct.

## How to read publisher evidence

### Take real values, never approximations

Read computed styles from the publisher's own pages. A screenshot supports the evidence. It
does not replace the live site when the site is available.

Record where each value came from. Mark any value you chose rather than sampled. The
St. Louis fork states that its two neutral text colors are choices, and that every other
value was fetched. Follow that habit, because the next reader cannot tell the two apart.

### Copy the mechanism, not only the appearance

The TriMet developer site underlines links with a dotted bottom border, not with
`text-decoration`. The fork copied the bottom border. The two sites then degrade the same way
under a font or zoom change. A visual match that uses a different mechanism drifts apart.

The same rule applies to fonts. The TriMet fork uses `"Trebuchet MS", Arial, Helvetica,
sans-serif` because the publisher site uses that stack, so both fall back together and
neither downloads a file.

### One home for every brand value

Put each color and font in `src/theme/variables.scss`. Name the variables for the publisher,
such as `$stl-blue` or `$tm-orange`. A component reads a variable. A component never holds a
hex literal.

When the publisher runs two sites with two palettes, say so in the proposal and keep them
apart. The TriMet fork follows `trimet.org` for the header, and `developer.trimet.org` for
the body and the links, because the data is published on the developer site.

### Derive navigation from what the catalog holds

Count the collections behind a proposed facet before you propose it. A publisher taxonomy
with 40 topics and a catalog that uses 6 of them gives you 6 topics, not 40. Say in the
proposal how many collections carry each value.

Empty states still need a design. A section whose data is absent should not render at all.

### Restraint

Reuse the visual language, the words, and a few recognizable motifs. Do not attempt a
pixel-for-pixel clone unless the user asks for one. The result must stay a coherent Portolan
browser.

Lead with data discovery and browsing. A decorative portal homepage that delays the first
collection is worse than a plain one that shows it.

Treat the browser as more than a map. Downloads, license, provenance, descriptions,
documentation, and source links stay first-class.

Use public-facing words where they help a reader. Do not erase technical precision that a
reader needs.

## What earlier projects decided, and what does not transfer

Department filters above the cards, a tag cloud below them, a particular statistics row, an
icon grid, and the words "datasets" and "rows" were outcomes for one publisher and one
catalog. They are not requirements. Derive the equivalent decisions from the inputs in front
of you.
