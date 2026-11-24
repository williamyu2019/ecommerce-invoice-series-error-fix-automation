# Verification of release 0.3.0

The predeclared synthetic evaluation passed 16/16 required scenarios. All expected fields matched; a negative-case pass means the workflow correctly refused or requested review, not that an invoice was issued. Fifteen integration tests cover the matrix and additional failure modes. The tests and expectations are included for rerunning.

A separate restoration used a newly copied package in a temporary directory and a new Python 3.12.14 virtual environment with no pip or third-party packages. macOS sandbox denied network access and reading the original business source or shared planning checkout. Tests and the CLI completed successfully. No company account, browser session, model key or downloaded model was used.

This is a same-machine isolated restoration. A different machine, operating system, or Python version has not been tested. Python 3.10+ is required by the code; Python 3.12 is the recommended tested version. The runtime version is recorded in `.python-version`; there is no dependency installation step.

No business-time or model-cost improvement is inferred from these synthetic runs. Observation timestamps are synthetic and labelled; log `recorded_at` timestamps record the actual run time. The original 308 Python / 62 browser helper historical records and the separate local original-engine rerun are not the test counts of this smaller package.

Evidence: `examples/verified-run/evaluation-results.json`, each scenario's `result.json`, state, synthetic receipts, mock tracker snapshots and logs. The top-level retained result page links each scenario to its evidence.

The three Learning statements reflect the author’s own draft, edited for clarity and accepted by the author. The release target is williamyu2019/ecommerce-invoice-series-error-fix-automation. Technical verification does not validate real platform access or real user-consent provenance.

Fresh code review identified and corrected four material test/adapter issues before packaging: complete-matrix validation before output writes; actual row movement with unrelated-row preservation; a writer process exiting before a fresh recovery reader; and case-specific rejection-stage, status, tracker-action/date/note assertions. The original v1 expectations were strengthened before the corrected implementation; no expected business outcome or threshold was relaxed. Fifteen integration tests passed after corrections.

The Operations layout now covers 14 explicitly illustrative dates. Dashboard checks require consecutive distinct days, coherent population/outcome totals, a zero-task day, open work, numeric examples and missing samples, and equality between the displayed inline data and the JSON asset. These checks validate the display fixture, not real operational efficiency.
