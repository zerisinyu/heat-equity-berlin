# Heat Equity Berlin

A small, reproducible attempt to map **heat vulnerability** across Berlin at the
neighbourhood level (the 542 *Planungsräume*, Berlin's official planning areas).

The map shades each neighbourhood by a combined vulnerability index and lets you
switch on cool-spot layers — drinking fountains, parks, libraries, and the city's
official "cool rooms". Click any area to see the score broken down: is it flagged
because it gets very hot, because vulnerable people live there, or because there's
nowhere nearby to cool off?

It tries to answer two modest questions: **where might people need attention first
during a heatwave**, and **where is the nearest relief**. It is meant less as a
finished product and more as a starting point that others can inspect, question,
and recompute.

**Live map:** https://zerisinyu.github.io/heat-equity-berlin/

> This is a diagnostic snapshot, not a predictor, and not an authority. The index
> is built from public data and a set of choices that are all open to challenge.
> Please read the **"How this map should *not* be read"** section below before
> drawing conclusions from it.

## Reproducing it

```bash
uv sync
make pipeline   # fetch -> process -> export, fully automatic; raw data cached in data/raw
make serve      # open http://localhost:8000
```

Run a single step for debugging:

```bash
uv run python run.py <step>
# step ∈ fetch / geo_base / exposure / indicators / index / refuges / surfaces / export
```

The frontend in `web/` is a single static HTML page (MapLibre GL JS) plus the
exported data, so it can be served by any static host.

## How the index is built

Public-health geography commonly splits heat vulnerability into three dimensions.
This project follows that framing:

| Dimension | In plain words | Underlying indicators (data year) |
|---|---|---|
| **Exposure** | how hot it gets here | PET 2 pm, UTCI 2 pm, night-time cooling (Klimaanalysekarten 2022, aggregated area-weighted from ~16k settlement blocks) |
| **Sensitivity** | who is more at risk | share 65+, share under 6 (2025); welfare receipt, child poverty, children in single-parent households (MSS 2023) |
| **Lack of coping capacity** | how hard it is to find relief | street-tree density, public green-space share, distance to nearest fountain (2025) |

Each underlying indicator is turned into a **percentile rank** across the 542
neighbourhoods (so different units become comparable), averaged within its
dimension, and the three dimensions are then combined — by default with equal
weights. Every weight lives in [`config/indicators.yaml`](config/indicators.yaml);
change the file and rerun to recompute.

**On missing data:** missing values are kept as missing (never silently filled
with zero); weights are re-normalised over the indicators that *are* present.
Neighbourhoods that lack a full set of dimension scores, or have fewer than 100
residents, are left unranked and shown as "insufficient data" — a freight yard or
a forest has no meaningful "vulnerability".

## The weights are a value judgement, not a fact

Weighting the three dimensions equally is a **choice**, not a truth. To see how
much that choice matters, the pipeline recomputes the index under four weighting
scenarios (equal / exposure-heavy / sensitivity-heavy / capacity-heavy). The
top-20 most-vulnerable lists overlap by 15–17 out of 20, and **11 neighbourhoods
land in the most-affected group under every scenario** (listed in
[NOTES.md](NOTES.md)). The map can highlight just those 11 — only that subset is
robust to the weighting choice. Treat the rest of the ranking as indicative, not
definitive.

## How this map should *not* be read

- **A neighbourhood average is not any individual's fate.** Aggregating climate
  blocks to a whole neighbourhood erases what happens inside it; the average hides
  the hottest top-floor flat on the block (the ecological fallacy).
- **This is not a list of "problem areas."** The index points to where help might
  be sent first, not to a deficiency score for a community. Using it for property
  prices, insurance, or stigma would be a misuse.
- **The data years don't line up.** Climate is 2022, social monitoring 2023,
  population 2025, greenery 2025. They are not a single snapshot in time.
- **Known gaps.** The 80+ age share is currently missing (the statistics office
  changed its site; 65+ is used instead and weights adjusted). Air-conditioning
  access has no direct data and is not included. See [NOTES.md](NOTES.md).
- Every step in the construction — the normalisation method, the weights, the
  minimum-population cutoff — is open to question and recomputation. That is the
  whole reason the code is public.

## Data sources & licences

Everything comes from Berlin's official open data ([gdi.berlin.de](https://gdi.berlin.de)
WFS / [daten.berlin.de](https://daten.berlin.de)). Per-layer endpoints, fields,
and years are documented in [`config/indicators.yaml`](config/indicators.yaml)
and [NOTES.md](NOTES.md).

- LOR Planungsräume 2021 — CC-BY-3.0-DE
- Klimaanalysekarten 2022 (Umweltatlas) — dl-de/by-2-0
- Monitoring Soziale Stadtentwicklung 2023 — dl-de/by-2-0
- Baumbestand (Straßenbäume), Grünanlagen — dl-de/by-2-0
- Trinkwasserbrunnen (Berliner Wasserbetriebe) — dl-de/zero-2-0
- Kühle Räume / Hitzeschutz (official indoor cool rooms, 111 sites) — dl-de/by-2-0
- Public library locations — © OpenStreetMap contributors, ODbL (no official dataset exists)
- Population: Amt für Statistik Berlin-Brandenburg, SB A I 16 hj (31 Dec 2025) — CC-BY

Basemap © OpenStreetMap contributors © CARTO.

With gratitude to the public servants and open-data teams in Berlin who publish and
maintain these datasets — this project is only possible because that work exists.

## Layout

```
src/            pipeline steps (fetch -> geo_base -> exposure -> indicators
                -> index -> refuges -> surfaces -> export)
config/         data sources, field mappings, all weights
web/            single-page map (MapLibre GL JS) + exported data
data/raw        cached raw downloads (git-ignored)
data/processed  intermediate outputs and check figures (git-ignored)
NOTES.md        fetch log, data quirks, sensitivity-analysis findings
```

## A note on scope

This was built as a learning project and a proof of concept. The code favours
clarity and honesty about its data over polish, and there is plenty it does not do
(no real-time temperature, no forecasting, no indoor microclimate). Corrections and
questions about the method are very welcome.

## Licence

Code released under the MIT Licence. The underlying datasets keep their own
licences as listed above; if you reuse the data, please attribute the original
providers accordingly.
