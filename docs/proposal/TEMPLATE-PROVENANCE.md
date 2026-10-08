# Proposal template source

## Active NeurIPS template

The proposal uses the supplied `Formatting_Instructions_For_NeurIPS_2026.zip`. All three original files are unpacked, unchanged, in `templates/neurips/`: `neurips_2026.tex`, `neurips_2026.sty`, and `checklist.tex`. The style is also copied into this proposal folder without modifications.

The assignment screenshot says NeurIPS 2024, while its linked Overleaf template and the supplied archive identify themselves as NeurIPS 2026. This revision follows the supplied archive. The [current Overleaf template](https://www.overleaf.com/latex/templates/neurips-2024/tpsbbrdqcmsh) credits the NeurIPS 2026 Program Chairs and lists CC BY 4.0 licensing; the original attribution and style headers are preserved.

The proposal uses `preprint` mode to display named authors without review line numbers or a conference acceptance notice. The first-page notice is the supplied style's original `Preprint.` text. The style intentionally suppresses the printed number on page 1; subsequent pages display their normal numbers. It retains the template's standard single-column US-letter layout and typography. Author-year citations use the standard `plainnat` bibliography style. No template examples, conference checklist, or technical appendix are included in this course proposal; the supplied originals remain in the template directory.

| File | SHA-256 |
| --- | --- |
| Supplied NeurIPS ZIP | `5d1674ec2e6acf4c0d72b48ea5b83afeabe9f5307b50b3d6863a689a7d787fc1` |
| neurips_2026.sty | `c3fc2894e83d2517ca18b66741d6c595986d97957dc08ec08bb2125a7ec4555a` |

## Retained ACL source

The inactive ACL files in this directory come from the previously supplied `Association_for_Computational_Linguistics__ACL__conference.zip`. Its full contents remain unpacked in `templates/acl/` at the repository root.

`acl.sty` and `acl_natbib.bst` are unchanged from that archive. Keep these retained source files unchanged.

| File | SHA-256 |
| --- | --- |
| Original ZIP | `3975e9198239f8a15f52e2a29d54fd989a937a7239dad5a333ea20fa073fb8fd` |
| acl.sty | `19dfeddc2c0e448f3926a0bef048a9db3f3611b46265b760caabd7ada4f361de` |
| acl_natbib.bst | `e332fd51dcea48e2a8a89754892c3cb99674a1cd70b527b661e9aaffc235e83c` |

The bibliography style includes an LPPL notice; `LICENSE-LPPL-1.3c.txt` supplies the license text. The supplied archive has no separate license grant for `acl.sty`, so its original attribution is preserved.

## Editing and submission

Edit `proposal.md`, then run `python tools/build_proposal.py` from the repository root to update `proposal.tex`. The bibliography metadata stays in `references.bib`. Compile `proposal.tex` with Tectonic or upload the three active LaTeX files listed in the repository README to Overleaf. The proposal's body limit is two pages excluding references; references start on a separate page. The final report limit is eight pages excluding references. Student ID lines are omitted at the team's request.
