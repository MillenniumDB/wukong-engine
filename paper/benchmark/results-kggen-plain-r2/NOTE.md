# KGGen plain, repetition 2

This run was launched as the `context` variant (folder `results-kggen-context-r1`, Oct 9), but KGGen's
`generate()` (6259b4c) never passes the context hint to its relation step, so the hint never reached the
model: it is a second run of the plain variant, and is kept as such. Its run records still say
`KGGen (context)` and carry the context string that was prepared but not used. Fixed in d1b4a09; the real
context variant is `results-kggen-context-r1`.
