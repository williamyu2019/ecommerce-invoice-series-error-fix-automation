# BRSIP Invoice Series Fix Automation Case Study

> Portfolio case study. Learning statements are based on the author’s own draft, edited for clarity. Historical business results and synthetic demo results are separate.

## From manual exception handling to an operational workflow

I used Codex and Claude to help turn a recurring invoice repair task into an AI assisted workflow with explicit business rules, evidence checks, recovery, and visual monitoring. My operational estimate is that weekly human effort fell from 3–4 hours to about 20 minutes. Reducing the attention the task demanded every day mattered just as much.

My role was to make the business process explicit, drive implementation and live iteration with AI coding agents, and build a way to monitor whether the automation was working.

## The repeated work behind each order

An invoice-series exception required an operator to move through several systems and decisions. For each order, they had to confirm or arrange the shop's access binding, enter the backend, locate the order and invoice, manually change the invoice series number, issue the invoice, and verify and record the result.

Shop binding was a shop-level operation that could be reused, while the remaining checks and results had to be handled order by order. The business problem was the repeated chain of actions and the need for a person to keep remembering and advancing it each day.

The exception list was also a moving view of business data. An order could still carry an old error even after the seller had issued the invoice, or could have been cancelled since it entered the list. Treating every listed error as a fresh repair task would lead to unnecessary or incorrect actions.

## Making the process explicit

I made the workflow explicit so that AI could carry it through: inputs, supported errors, eligibility checks, exceptions, states, and completion criteria. This separated shop-level configuration from order-level outcomes.

The scope covered invoice-series errors 539 and 206, targeting series 747. Repairs required identity and eligibility checks, a reload after saving, and observation of the issuance result. Completion required writing back by shop and order and verifying the returned status, date, and note. Interruptions had to preserve progress and attempts.

## Dividing the work between agents code and people

AI coding agents handled much of the coding and execution; I defined the process, drove live iteration, and reviewed operational outcomes. The core Python engine ran locally, while Codex and Claude supplied the agent interaction and browser orchestration.

| Actor | Work |
| --- | --- |
| Me | Define and externalize the process, set completion criteria, drive live trials and design tradeoffs, make business decisions, and establish monitoring |
| AI coding agents | Write and revise scripts, run tests and browser steps, help investigate failures, and update operating instructions |
| Python and JavaScript | Persist state and evidence, perform repeatable actions, check conditions, preserve attempts, and generate outputs |
| Business systems and team | Provide source data, platform functionality, access, and the context in which the process operates |

## The changes driven by real operation

### Reduce repeated agent decisions

I noticed the browser moving step by step and asked why it was slow and token intensive. The direction was to package stable sequences as reusable actions and return concise fields to the agent, while retaining full page evidence for debugging.

### Find blockers before they interrupt work

I asked for readiness checks that surfaced login, browser, data, and access problems together. Later, I proposed checking for eligible orders before requiring all repair-related access. This reduced the need to pull me back into a run midway; Sheet access was still needed to inspect the candidate list.

### Preserve business progress when execution is interrupted

I asked for a fallback that preserved real progress. Rolling back software must not erase an issuance attempt. An unknown result therefore calls for read-only reconciliation. Recovery and duplicate-attempt checks appear in the implementation and tests; the retained live batches show one attempt for each order they issued.

### Monitor the work people actually do

I established monitoring of order handling, time, and human interventions. It exposed a measurement problem: four confirmation cards omitted browser and app prompts. Distinguishing prompt types and labelling incomplete coverage made the view useful for diagnosing friction.

## A historical order from error to verified writeback

A retained order from November 9, 2026 illustrates the path. The records show error 539, series 004, and no downloadable invoice. The workflow saved and reloaded 747, rechecked the order, and recorded one issuance attempt.

The portal then showed an issued, downloadable invoice. The ledger recorded ISSUED with attempts equal to one, and its writeback plan matched the tracker action, date, and note. Ten relevant browser receipts matched hashes of their saved page text; this evidence covers the portal status and tracker update.

## A material failure and what it changed

The same batch recorded an authorization failure: actions occurred before the expected owner confirmation. The issue was disclosed. Later changes introduced a batch authorization card and recorded the operator response; the root cause remained open.

A real user confirmation must be distinguishable from a sentence generated by the agent. A nonempty string cannot establish its source. The representative batch predates the unified authorization file later used by the adapter, so its successful order outcome does not validate that newer mechanism.

## Results and what the numbers mean

| Evidence | Result | Interpretation |
| --- | --- | --- |
| My operational estimate | 3–4 hours per week → about 20 minutes per week | Human effort; no matched timing study retained |
| My qualitative assessment | Less daily mindshare spent remembering and advancing the task | Qualitative operator assessment |
| Two retained Claude batches | 17 checked; 9 issued by the workflow, 6 already issued, 2 cancelled and skipped | Processing outcomes; not 17 invoices repaired |
| Tracker readback | 17 outcomes matched the retained writeback records | Evidence of closeout for those batches |
| Historical engineering acceptance | 308 Python tests and 62 browser helper tests recorded as passing in simulation | Historical test records, not new tests of the planned public demo |
| Current local verification | Original suite: 307/308 Python with one fixture error; adapted fixtures: 308/308. Browser helper: 62/62 in both runs; two offline scenarios completed. | Original source and assertions unchanged; no network or business actions. This is not an independent evaluation of the public adaptation. |

The batches had different volumes and incomplete time and intervention coverage. They do not provide a precise comparison between agents. Weekly human effort and retained batch outcomes answer different questions.

## What I learned

- Own the business outcome. I am accountable for delivering the result stakeholders need, regardless of how it is achieved.
- Choose projects for impact, feasibility, and frequency. Frequent use exposes problems sooner, keeps context fresh, and creates more opportunities to iterate.
- Design observability from day zero. Signals that show whether a workflow is on track and where it fails make debugging much easier.

## The synthetic public adaptation

The public adaptation exercises selected original state and tracker rules with synthetic inputs and simulated tools. It runs 16 predeclared scenarios without company accounts, network access, model keys or third-party packages. Each expected field must match, including correct refusals. The retained results and logs are linked from the README.

The package covers current eligibility checks, identity mismatches, saved-series evidence, one issuance attempt, persisted recovery, row movement and conflict preservation. It omits real data acquisition, account binding, platform DOM and external agent orchestration. It is an offline core simulation; no live AI inference takes place.

A simulated confirmation record labelled as operator-origin demonstrates only an adapter contract. It cannot prove who actually authored text, and it does not close the original authorization incident. A checkpoint hash detects accidental edits, not a malicious rewrite of both content and hash.

The core was extracted from two original modules rather than copying the full operating product. Source constants and labels were replaced, the legacy one-off pilot path was removed, and the demo uses synthetic tracker proofs. The original business source stayed unchanged. Source notes describe AI-assisted implementation and the boundaries of my contribution.

The package is tested in a new temporary directory on the same machine with network and original source access denied. This is useful restoration evidence, but it is not verification on a different machine or operating system. The time and mindshare outcomes above remain my operational assessment; synthetic test counts do not measure those benefits.
