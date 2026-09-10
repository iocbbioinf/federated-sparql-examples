# iocb-inf-void — informational queries answered from VoID

The same four informational questions as `examples/iocb_inf`, but answered
from **dataset descriptions** (VoID + SPARQL service descriptions) instead of
from instance data.

The `iocb_inf` versions answer by fetching example records — a known protein,
a known reaction — and letting the returned values stand as evidence. The
queries here never read a protein, molecule or structure. They read what each
endpoint publishes *about itself* at its `/.well-known/void` graph. That makes
the answers complete (every graph, every format, every declared mapping,
rather than one illustrative row) and fast, since the numbers are
pre-computed by the servers.

| File | Question | Answered from |
|------|----------|---------------|
| `001.ttl` | What are UniProt and Rhea, and what data is in them? | `dcterms:title`, `pav:version`, per-graph `void:triples` / `void:classes` / `void:distinctSubjects`, `dcterms:license` |
| `002.ttl` | How do I access PDB, UniProt, Rhea, PubChem, ChEMBL programmatically? | `sd:endpoint`, `sd:supportedLanguage`, `sd:feature`, plus `up:urlTemplate` from UniProt's database registry |
| `003.ttl` | Which data formats, and where is the documentation? | `sd:resultFormat` (URIs in the W3C formats registry), `voidext:datatype`, and the format-defining DOIs in `up:citation` |
| `004.ttl` | How is UniProt interconnected, with what cardinality? | `void:linkPredicate` + `void:triples` / `void:distinctSubjects` / `void:distinctObjects` |
| `005.ttl` | One combined profile of the whole federation | all of the above, aggregated per endpoint |

## Cardinality is derived, not asserted

`004.ttl` is the query where VoID earns its keep. A VoID **linkset** records,
for one predicate joining one pair of classes, the triple count and the number
of *distinct* subjects and objects. Those three numbers give the cardinality
directly:

```
triples / distinctSubjects = objects per subject  (fan-out)
triples / distinctObjects  = subjects per object  (fan-in)
```

so `one-to-one`, `one-to-many`, `many-to-one` and `many-to-many` fall out of a
comparison rather than a hand-written label. Measured results (2026-09):

| Mapping | triples | subjects | objects | fan-out | verdict |
|---|---|---|---|---|---|
| ChEMBL target → **UniProt** | 12,782 | 12,782 | 12,782 | 1.000 | one-to-one |
| ChEMBL target → **PDB** | 89,206 | 5,471 | 76,621 | 16.305 | many-to-many |
| ChEMBL molecule → **PubChem** | 1,879,197 | 1,856,640 | 1,879,197 | 1.012 | one-to-one |
| ChEMBL molecule → **ChEBI** | 39,866 | 39,475 | 39,866 | 1.010 | one-to-one |

The exact 1:1:1 on `cco:UniprotRef` is what makes the **UniProtKB accession**
the central entity: it identifies a target component uniquely, and everything
else (PDB structures, PubChem compounds, Rhea reactions) fans out from it.

## Known endpoint limitations

Encountered while writing these; each is noted in the query that hits it.

* **UniProt publishes no `void:distinctSubjects`/`distinctObjects`** on its
  property partitions, and its `void:entities` is a graph-wide figure repeated
  on every class partition. So UniProt's own PDB and Rhea links can be *sized*
  (235,142 and 28,879,241 triples) but their cardinality cannot honestly be
  computed from what it publishes — `004.ttl` reports that rather than guessing.
* **IDSM crashes on `STRSTARTS`** over these graph names
  (`NullPointerException: ... "prefix" is null`); `002.ttl` uses `CONTAINS`.
* **IDSM rejects `SELECT`/`SELECT DISTINCT` inside `SERVICE`** with
  "The SERVICE pattern cannot be evaluated"; `004.ttl` uses plain triple
  patterns and de-duplicates with an outer `DISTINCT`. This is also why
  `005.ttl` targets UniProt: it aggregates inside each remote `SERVICE`.
* **IDSM publishes several graph-scoped copies of each linkset**, so linkset
  queries need `DISTINCT` to avoid reporting the same mapping ~8 times.
* **UniProt ignores the `Accept` header** — request results with the `format`
  query parameter (`format=json`), or POST with
  `Content-Type: application/sparql-query`. It also returns
  *"Too many concurrent queries"* under load; retry with spacing.

## Running them

`schema:target` names the endpoint each query is meant to be sent to:

```bash
# 001, 002, 003, 005 -> UniProt
curl -G --data-urlencode query@<(sed -n '/sh:select """/,/"""/p' 001.ttl) \
     --data-urlencode format=json https://sparql.uniprot.org/sparql

# 004 -> IDSM
curl -X POST -H 'Content-Type: application/sparql-query' \
     --data-binary @query.rq https://idsm.elixir-czech.cz/sparql/endpoint/idsm
```
