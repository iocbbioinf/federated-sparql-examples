# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "rdflib>=7.6.0",
#     "requests>=2.34.2",
# ]
# ///
"""Load all SPARQL examples into a local RDF graph and run each one against its target endpoint."""

import argparse
import time
from pathlib import Path

import requests
from rdflib import Graph

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX spex: <https://purl.expasy.org/sparql-examples/ontology#>
PREFIX schema: <https://schema.org/>

SELECT ?sq ?question ?query ?local_KG (GROUP_CONCAT(DISTINCT COALESCE(?federated_KG, ""); separator="|") AS ?federated_KG)
WHERE {
    ?sq a sh:SPARQLExecutable ;
        rdfs:comment ?question ;
        sh:select|sh:ask|sh:construct|spex:describe ?query ;
        schema:target ?local_KG .
    OPTIONAL {
        ?sq spex:federatesWith ?federated_KG.
    }
}
GROUP BY ?sq ?question ?query ?local_KG
"""


def load_examples(examples_dir: Path) -> Graph:
    graph = Graph()
    for path in sorted(examples_dir.glob("*/*.ttl")):
        graph.parse(path, format="turtle")
    return graph


def run_query(endpoint: str, query: str, timeout: float) -> str:
    """Run a query and return "ok", "empty", "timeout" or an error description."""
    try:
        response = requests.post(
            endpoint,
            data={"query": query},
            headers={
                "Accept": "application/sparql-results+json, text/turtle;q=0.9",
                "User-Agent": "elixir-federated-sparql-examples/0.1",
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.Timeout:
        return "timeout"
    except requests.HTTPError as e:
        return f"http error {e.response.status_code}"
    except requests.RequestException as e:
        return f"request error: {e.__class__.__name__}"

    if "json" in response.headers.get("Content-Type", ""):
        body = response.json()
        # ASK queries return a boolean, SELECT queries return bindings
        if "boolean" in body or body.get("results", {}).get("bindings"):
            return "ok"
        return "empty"
    return "ok" if response.text.strip() else "empty"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=120, help="per-query timeout in seconds")
    args = parser.parse_args()

    graph = load_examples(EXAMPLES_DIR)
    examples = sorted(graph.query(QUERY), key=lambda row: str(row.sq))
    print(f"{len(examples)} examples retrieved from {len(list(EXAMPLES_DIR.glob('*/*.ttl')))} files.")

    problems = []
    for i, row in enumerate(examples, 1):
        start = time.monotonic()
        status = run_query(str(row.local_KG), str(row.query), args.timeout)
        print(f"{i}/{len(examples)} [{status}] {row.sq} ({time.monotonic() - start:.1f}s)", flush=True)
        if status != "ok":
            problems.append((row, status))

    print("\nProblematic examples:")
    for row, status in problems:
        print(f"[{status}] {row.sq} ({row.local_KG})\n    {row.question}")
    print(f"{len(examples) - len(problems)} ok, {len(problems)} problematic.")
