# Website source validation

This is the first version-controlled snapshot of the previously local website.
It contains the project/learning page generators, bilingual templates, shared
navigation and reading-position logic, local preview server, teaching examples,
small icon assets and tests. It does not reconstruct earlier Git history.

## Source-only checkout

`python -m learning.preview` builds a fresh local preview from the tracked source
and existing tracked proposal documents. It does not import the neural experiment
runtime, load model weights, run inference or copy saved experiment datasets.
Existing output directories are refused. Missing measurement/media assets remain
explicitly unavailable; the preview does not fabricate research results.

The website-only requirements omit PyTorch and model packages. The full optional
lesson environment remains documented separately in `README.md`.

## Verification scope

- Python tests cover bilingual content structure, local links, safe embedded JSON,
  result-import provenance, source references, asset allowlists, source-only
  generation, protection of existing runs and the local HTTP preview server.
- One additional cohort check uses local saved results excluded from Git. It runs
  when `CS550_SITE_OUTPUT` points to an available site, otherwise it is explicitly
  skipped. Fresh checkouts still run the source-only cohort/template checks.
- JavaScript syntax is checked for the shared interactions and browser harnesses.
- The source-publication check also exports only Git-tracked content to a fresh
  local directory and reruns the portable tests and source-only build there.

## Source-publication checks (2026-10-21)

- Existing local environment: **86 website tests passed**, including the optional
  saved-cohort integration check.
- Fresh export of Git-tracked source: **85 passed, 1 skipped**. The skipped check
  needs the locally retained cohort assets; all portable checks passed.
- The source-only CLI built **54 HTML pages** without model-runtime imports or
  saved experiment resources. Its test checks every local file/anchor reference
  and every page's ID uniqueness; absent logs are shown as unavailable.
- JavaScript syntax, Git whitespace checks, staged-path/size review and credential
  pattern checks passed. Existing unrelated experiment edits were preserved.

## Earlier browser verification

The 2026-10-20 reading-position audit covered the then-current 12 bilingual page
families (24 pages, 99 main sections): 111 desktop positions, 24 mobile positions,
12 mobile menus and five expanded-content/selected-state scenarios. All 280
language switches passed, with maximum measured block-position error below
0.5 pixels. Both language directions, paragraph/row progress, closed disclosures,
sidebar expansion/visibility and selected frames/program steps were checked.

Those measurements predate the separate cohort-page addition. Current cohort
template/assets checks are recorded by the Python suite; the earlier browser grid
is not presented as browser verification of later features. Raw browser artifacts
and workstation/network operation logs remain local.

## Excluded resources

Generated HTML/result trees, raw data, predictions, model weights, videos,
third-party checkouts, virtual environments, caches and private connection files
remain ignored. Only the website sources and small static icons are shared.
