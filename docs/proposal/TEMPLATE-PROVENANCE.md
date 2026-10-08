# ACL template source

The ACL files in this directory come from the supplied `Association_for_Computational_Linguistics__ACL__conference.zip`. Its full contents are unpacked in `templates/acl/` at the repository root. The project uses named `final` formatting for a course proposal.

`acl.sty` and `acl_natbib.bst` are unchanged from that archive. Keep their original headers and layout settings when editing the proposal.

| File | SHA-256 |
| --- | --- |
| Original ZIP | `3975e9198239f8a15f52e2a29d54fd989a937a7239dad5a333ea20fa073fb8fd` |
| acl.sty | `19dfeddc2c0e448f3926a0bef048a9db3f3611b46265b760caabd7ada4f361de` |
| acl_natbib.bst | `e332fd51dcea48e2a8a89754892c3cb99674a1cd70b527b661e9aaffc235e83c` |

The bibliography style includes an LPPL notice; `LICENSE-LPPL-1.3c.txt` supplies the license text. The supplied archive has no separate license grant for `acl.sty`, so its original attribution is preserved.

Edit `proposal.md`, then run `python tools/build_proposal.py` from the repository root to update `proposal.tex`. The bibliography metadata is in `references.bib`. Compile `proposal.tex` with Tectonic or upload the files in this folder to Overleaf. The proposal's page limit is two pages; the final report limit is eight pages excluding references.
