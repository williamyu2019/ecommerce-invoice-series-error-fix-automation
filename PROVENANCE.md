# Source and adaptation

This is a synthetic, offline adaptation of selected Python logic from the BRSIP invoice-series workflow. William authorized personal retention and sanitized public adaptation on November 23, 2026. The owner subsequently selected the public repository williamyu2019/ecommerce-invoice-series-error-fix-automation for this release on November 24, 2026. This notice does not select an open-source license or establish ownership of third-party work.

The original implementation was developed and revised with AI coding agents in a business environment. William's supported contribution is defining and externalizing the workflow, driving operational iteration and tradeoffs, and establishing visual monitoring. This package does not claim he personally wrote every line or originated the pre-existing spreadsheet tooling.

`invoice_demo/state_machine.py` extracts and adapts `fresh_eligible_check` and `reduce_event` from the original runner. `supports_series_error` is simplified to configured 539/206 handling; the historical one-off pilot authorization path is deliberately omitted. The transition checks for identity, current eligibility, saved-series readback, evidence, prior attempts and terminal status are retained.

`invoice_demo/tracker.py` extracts the original scope, membership, series-history, writeback planning and closeout validation functions. The spreadsheet ID, tab, method allowlist and labels are replaced with synthetic values. It imports the adapted state helper locally. It has no web client or company connector. The demo always uses workflow version 2 and `test_mode=True` with `environment=SIMULATION` and `live_readback=False`.

The simulation adapter, CLI, result page, fixtures, expectations, tests and diagram were prepared for this portfolio version with Codex assistance. The adapter enforces a small simulated confirmation contract and an all-or-nothing mock-table conflict check. These are demonstration controls, not evidence that an actual person's consent or identity has been verified.

Original source paths, fingerprints, business inputs, historical permits, browser page text, invoice files, company credentials and real records are excluded. A local adaptation map is retained outside this distribution for the owner's review. The original business folder was not modified.

# Scope of verification

Predeclared synthetic expectations are in `examples/expectations.json`, separate from the runtime code. Tests compare every named field and include successful processing, negative cases, recovery and conflict preservation. They are reference assertions authored for this adaptation, not an independent business time study or live platform acceptance.

A checkpoint's SHA-256 detects accidental edits to its payload; it is not a signature and cannot protect against someone who can rewrite both content and hash. A simulated operator-origin field can be fabricated and therefore establishes no real user provenance. Historical authorization issues remain disclosed in the case study.

Only the core demonstration is reproduced here. External agent decisions, business data acquisition, real account binding, browser DOM actions, production scheduling, handover and tax validity are outside the executable scope.

# The two original dashboard interfaces

`dashboards/evolution.html` adapts the original Codex `dashboard_template.html` with the five phase descriptions from its Nov 6 snapshot. The returned Claude engine mirror had no phases. Original performance history, evidence paths and order identities are excluded; the performance tab contains a synthetic, unmeasured fixture.

`dashboards/monitoring.html` retains the layout and chart logic from the returned Claude Operations `page/index.html`, using the latest local `dashboard_data.json` generation timestamp (Nov 12, 2026) as its source-version reference. The online Claude artifact was not inspected. The original Data artifact's `dash.calc/data/draw` API is replaced with a small local shim, host CSS tokens receive local defaults, and D3 is bundled locally. Four original chart types and the distinction between unavailable/estimated metrics remain visible.

The evolution performance tab uses a small synthetic core fixture. The Operations monitor instead uses 14 manually authored illustrative daily samples (Jan 5–18), stored in `dashboards/monitoring-layout-fixture.json`. Its order volumes, runtime and human-intervention values are invented display examples; they are not measurements of business operations or of the core runs. Missing sample values show NA; explicit zero is preserved. No efficiency improvement is inferred. The 16 actual core scenario outputs remain separate in `dashboards/monitoring-core-results.json` and the evaluation page.

The five historical development phases remain retained source descriptions, not new claims of performance. The dashboard origin is unchanged: Codex five-phase evolution and the Nov 12 returned Claude Operations UI.

D3 7.9.0 was obtained from the official npm registry (`https://registry.npmjs.org/d3/-/d3-7.9.0.tgz`). Its copyright and ISC license are retained in `dashboards/vendor/D3-LICENSE.txt`. That third-party license covers D3; no project-wide open-source license has been selected.
