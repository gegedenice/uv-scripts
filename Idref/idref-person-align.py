#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "sentence-transformers>=3.0.0",
# ]
# ///
"""Align an extracted person name to an IdRef PPN candidate.

The script is intentionally deterministic: it generates candidates from
Qualinka's find-ra-idref endpoint, enriches each PPN with attrra and IdRef
references, computes transparent evidence scores, and emits JSON.
Default weights for scoring are 
  --weight-name 0.40
  --weight-attrra-source 0.25
  --weight-attrra-note 0.15
  --weight-references 0.15
  --weight-institution-year 0.05

Usage:
  uv run --script idref_person_align.py --help
  python3 idref_person_align.py --help
  
Examples:
  uv run --script idref_person_align.py \
    --name "Valérie Robert" \
    --title "Satisfaction et vécu périopératoire des patients opérés sous anesthésie péribulbaire" \
    --degree-type "Thèse d'exercice" \
    --year 2003
  uv run --script idref_person_align.py \
    --name "Maria Bas" \
    --title "Essays on labor markets, gender, and external shocks in manufacturing firms in Indonesia" \
    --discipline "Economie" \
    --institution "UNIVERSITÉ PARIS 1 PANTHÉON SORBONNE" \
    --doctoral-school "UFR 02" \
    --degree-type "Thèse de doctorat" \
    --year 2022 \
    --embedding-model "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" \
    --weight-name 0.40 \
    --weight-attrra-source 0.10 \
    --weight-attrra-note 0.10 \
    --weight-references 0.35 \
    --weight-institution-year 0.05
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FIND_RA_ENDPOINT = "https://qualinka.idref.fr/data/find-ra-idref/api/v2/req"
ATTRRA_ENDPOINT = "https://qualinka.idref.fr/data/attrra/api/v2/req"
REFERENCES_ENDPOINT = "https://www.idref.fr/services/references/{ppn}.json"
USER_AGENT = "smartbiblia-idref-person-align/0.1"
EMBEDDER = None
EMBEDDING_CACHE: dict[str, list[float]] = {}
DEFAULT_WEIGHT_NAME = 0.40
DEFAULT_WEIGHT_ATTRRA_SOURCE = 0.25
DEFAULT_WEIGHT_ATTRRA_NOTE = 0.15
DEFAULT_WEIGHT_REFERENCES = 0.15
DEFAULT_WEIGHT_INSTITUTION_YEAR = 0.05


@dataclass
class EvidenceScore:
    name: float = 0.0
    attrra_source: float = 0.0
    attrra_note: float = 0.0
    references: float = 0.0
    institution_year: float = 0.0
    final: float = 0.0


@dataclass
class Candidate:
    ppn: str
    first_name: str | None = None
    last_name: str | None = None
    attrra: dict[str, Any] | None = None
    references: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    score: EvidenceScore = field(default_factory=EvidenceScore)
    evidence: dict[str, Any] = field(default_factory=dict)


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_similarity(left: Any, right: Any) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm and not right_norm:
        return 1.0
    if not left_norm or not right_norm:
        return 0.0

    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    intersection = left_tokens & right_tokens
    token_f1 = (
        2 * len(intersection) / (len(left_tokens) + len(right_tokens))
        if left_tokens and right_tokens
        else 0.0
    )
    char_ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    return 0.6 * token_f1 + 0.4 * char_ratio


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def text_vector(value: str) -> dict[str, float]:
    tokens = normalize_text(value).split()
    vector: dict[str, float] = {}
    for token in tokens:
        if len(token) <= 2:
            continue
        vector[token] = vector.get(token, 0.0) + 1.0
    return vector


def lexical_similarity(left: str, right: str) -> float:
    """Lightweight lexical semantic score.

    This is deliberately dependency-free for batch jobs. If you later add a
    sentence-transformers model, pass --embedding-model to use it.
    """

    return cosine_similarity(text_vector(left), text_vector(right))


def load_embedder(model_name: str) -> Any:
    global EMBEDDER
    if EMBEDDER is None:
        from sentence_transformers import SentenceTransformer

        EMBEDDER = SentenceTransformer(model_name)
    return EMBEDDER


def embedding_vector(text: str, model_name: str) -> list[float]:
    cache_key = f"{model_name}\0{text}"
    if cache_key not in EMBEDDING_CACHE:
        model = load_embedder(model_name)
        EMBEDDING_CACHE[cache_key] = model.encode(text, normalize_embeddings=True).tolist()
    return EMBEDDING_CACHE[cache_key]


def embedding_similarity(left: str, right: str, model_name: str) -> float:
    left_vec = embedding_vector(left, model_name)
    right_vec = embedding_vector(right, model_name)
    return sum(a * b for a, b in zip(left_vec, right_vec))


def semantic_similarity(left: str, right: str, embedding_model: str | None = None) -> float:
    if not left.strip() or not right.strip():
        return 0.0
    if embedding_model:
        return max(0.0, embedding_similarity(left, right, embedding_model))
    return lexical_similarity(left, right)


def request_json(url: str, timeout: float, retries: int, backoff: float) -> tuple[Any | None, str | None]:
    last_error = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload), None
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.reason}"
        except URLError as exc:
            last_error = f"URL error: {exc.reason}"
        except Exception as exc:
            last_error = str(exc)
        if attempt < retries:
            time.sleep(backoff * (2 ** attempt))
    return None, last_error


def parse_person_name(full_name: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", full_name.strip())
    if "," in cleaned:
        last, first = [part.strip() for part in cleaned.split(",", 1)]
        return first, last

    particles = {"de", "du", "des", "del", "della", "van", "von", "le", "la"}
    parts = cleaned.split()
    if len(parts) <= 1:
        return "", cleaned

    last_start = len(parts) - 1
    while last_start > 0 and normalize_text(parts[last_start - 1]) in particles:
        last_start -= 1
    return " ".join(parts[:last_start]), " ".join(parts[last_start:])


def iter_candidate_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [item for item in payload.get("ids", []) if isinstance(item, dict)]

    items = []
    if isinstance(payload, list):
        for block in payload:
            if isinstance(block, dict):
                items.extend(item for item in block.get("results", []) if isinstance(item, dict))
    return items


def find_candidates(
    full_name: str,
    first_name_override: str | None,
    last_name_override: str | None,
    timeout: float,
    retries: int,
    backoff: float,
    max_candidates: int,
) -> tuple[list[Candidate], dict[str, Any]]:
    parsed_first_name, parsed_last_name = parse_person_name(full_name)
    first_name = first_name_override or parsed_first_name
    last_name = last_name_override or parsed_last_name
    query = {"lastName": last_name}
    if first_name:
        query["firstName"] = first_name
    url = f"{FIND_RA_ENDPOINT}?{urlencode(query)}"
    payload, error = request_json(url, timeout, retries, backoff)
    meta = {
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "parsed_first_name": parsed_first_name,
        "parsed_last_name": parsed_last_name,
        "url": url,
        "error": error,
    }
    if error:
        return [], meta

    candidates: list[Candidate] = []
    seen = set()
    for item in iter_candidate_items(payload):
        ppn = str(item.get("ppn") or "").strip()
        if not ppn or ppn in seen:
            continue
        seen.add(ppn)
        candidates.append(
            Candidate(
                ppn=ppn,
                first_name=item.get("firstName"),
                last_name=item.get("lastName"),
            )
        )
        if len(candidates) >= max_candidates:
            return candidates, meta
    return candidates, meta


def fetch_attrra(candidate: Candidate, timeout: float, retries: int, backoff: float) -> None:
    url = f"{ATTRRA_ENDPOINT}?{urlencode({'ra_id': candidate.ppn})}"
    payload, error = request_json(url, timeout, retries, backoff)
    if error:
        candidate.errors.append(f"attrra: {error}")
        return
    candidate.attrra = payload if isinstance(payload, dict) else None


def fetch_references(
    candidate: Candidate,
    timeout: float,
    retries: int,
    backoff: float,
    max_docs_per_role: int,
) -> None:
    url = REFERENCES_ENDPOINT.format(ppn=candidate.ppn)
    payload, error = request_json(url, timeout, retries, backoff)
    if error:
        candidate.errors.append(f"references: {error}")
        return
    if not isinstance(payload, dict):
        candidate.references = None
        return

    for role in iter_reference_roles(payload):
        for docs_key in ("docs", "doc"):
            docs = role.get(docs_key)
            if isinstance(docs, list):
                role[docs_key] = docs[:max_docs_per_role]
            elif isinstance(docs, dict) and max_docs_per_role == 0:
                role[docs_key] = []
    candidate.references = payload


def as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def attrra_notes(attrra: dict[str, Any]) -> list[str]:
    return as_text_list(attrra.get("noteGen")) + as_text_list(attrra.get("bioNote"))


def preferred_forms(candidate: Candidate) -> list[str]:
    forms = []
    attrra = candidate.attrra or {}
    for item in attrra.get("preferedform", []):
        if isinstance(item, dict) and item.get("value"):
            forms.append(str(item["value"]))
    joined_name = " ".join(part for part in [candidate.first_name, candidate.last_name] if part)
    if joined_name:
        forms.append(joined_name)
    return forms


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def iter_reference_roles(refs: dict[str, Any]) -> list[dict[str, Any]]:
    roles = [role for role in listify(refs.get("roles")) if isinstance(role, dict)]

    for service_payload in refs.values():
        if not isinstance(service_payload, dict):
            continue
        result = service_payload.get("result")
        if not isinstance(result, dict):
            continue
        roles.extend(role for role in listify(result.get("role")) if isinstance(role, dict))

    return roles


def reference_citations(candidate: Candidate) -> list[dict[str, str]]:
    refs = candidate.references or {}
    citations = []
    for role in iter_reference_roles(refs):
        role_name = str(role.get("role_name") or role.get("roleName") or "")
        for docs_key in ("docs", "doc"):
            for doc in listify(role.get(docs_key)):
                if isinstance(doc, dict) and doc.get("citation"):
                    citations.append({"role": role_name, "citation": str(doc["citation"])})
    return citations


def current_context(args: argparse.Namespace) -> str:
    parts = [
        args.name,
        args.title,
        args.subtitle,
        args.discipline,
        args.institution,
        args.doctoral_school,
        args.degree_type,
        args.year,
    ]
    return " ".join(part for part in parts if part)


def ranked_similarities(
    query: str,
    texts: list[str],
    embedding_model: str | None,
) -> list[tuple[float, str]]:
    ranked = []
    for text in texts:
        ranked.append((semantic_similarity(query, text, embedding_model), text))
    return sorted(ranked, key=lambda item: item[0], reverse=True)


def best_similarity(
    query: str,
    texts: list[str],
    embedding_model: str | None,
) -> tuple[float, str | None]:
    ranked = ranked_similarities(query, texts, embedding_model)
    if not ranked:
        return 0.0, None
    return ranked[0]


def top_k_average_similarity(
    query: str,
    texts: list[str],
    embedding_model: str | None,
    top_k: int,
) -> tuple[float, list[str]]:
    ranked = ranked_similarities(query, texts, embedding_model)[:top_k]
    if not ranked:
        return 0.0, []
    return sum(score for score, _ in ranked) / len(ranked), [text for _, text in ranked]


def institution_year_score(args: argparse.Namespace, candidate: Candidate) -> float:
    attrra = candidate.attrra or {}
    evidence_text = " ".join(
        attrra_notes(attrra)
        + as_text_list(attrra.get("source"))
        + [item["citation"] for item in reference_citations(candidate)]
    )
    score = 0.0
    if args.institution and normalize_text(args.institution) in normalize_text(evidence_text):
        score += 0.5
    if args.doctoral_school and normalize_text(args.doctoral_school) in normalize_text(evidence_text):
        score += 0.25
    if args.year and re.search(rf"\b{re.escape(str(args.year))}\b", evidence_text):
        score += 0.25
    return min(score, 1.0)


def score_candidate(args: argparse.Namespace, candidate: Candidate) -> None:
    forms = preferred_forms(candidate)
    candidate.score.name = max((name_similarity(args.name, form) for form in forms), default=0.0)

    query = current_context(args)
    attrra = candidate.attrra or {}
    sources = as_text_list(attrra.get("source"))
    notes = attrra_notes(attrra)
    refs = reference_citations(candidate)
    ref_texts = [item["citation"] for item in refs]

    embedding_model = args.embedding_model or None
    candidate.score.attrra_source, best_source = best_similarity(query, sources, embedding_model)
    candidate.score.attrra_note, best_note = best_similarity(query, notes, embedding_model)
    candidate.score.references, best_refs = top_k_average_similarity(
        query,
        ref_texts,
        embedding_model,
        args.reference_top_k,
    )
    candidate.score.institution_year = institution_year_score(args, candidate)

    candidate.score.final = (
        args.weight_name * candidate.score.name
        + args.weight_attrra_source * candidate.score.attrra_source
        + args.weight_attrra_note * candidate.score.attrra_note
        + args.weight_references * candidate.score.references
        + args.weight_institution_year * candidate.score.institution_year
    )
    candidate.evidence = {
        "preferred_forms": forms,
        "best_attrra_source": best_source,
        "best_attrra_note": best_note,
        "best_references": best_refs,
    }


def status_for_ranked(ranked: list[Candidate], accept_threshold: float, margin_threshold: float) -> str:
    if not ranked:
        return "not_found"
    top = ranked[0]
    if top.score.final < accept_threshold:
        return "low_confidence"
    if len(ranked) > 1 and top.score.final - ranked[1].score.final < margin_threshold:
        return "ambiguous"
    return "accepted"


def score_weights_to_json(args: argparse.Namespace) -> dict[str, float]:
    return {
        "name": args.weight_name,
        "attrra_source": args.weight_attrra_source,
        "attrra_note": args.weight_attrra_note,
        "references": args.weight_references,
        "institution_year": args.weight_institution_year,
    }


def candidate_to_json(candidate: Candidate) -> dict[str, Any]:
    return {
        "ppn": candidate.ppn,
        "first_name": candidate.first_name,
        "last_name": candidate.last_name,
        "url": f"https://www.idref.fr/{candidate.ppn}",
        "score": {
            "final": round(candidate.score.final, 4),
            "name": round(candidate.score.name, 4),
            "attrra_source": round(candidate.score.attrra_source, 4),
            "attrra_note": round(candidate.score.attrra_note, 4),
            "references": round(candidate.score.references, 4),
            "institution_year": round(candidate.score.institution_year, 4),
        },
        "evidence": candidate.evidence,
        "errors": candidate.errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score IdRef PPN candidates for an extracted person name.")
    parser.add_argument("--name", required=True, help="Extracted full person name.")
    parser.add_argument("--first-name", default="", help="Override parsed first name for Qualinka search.")
    parser.add_argument("--last-name", default="", help="Override parsed last name for Qualinka search.")
    parser.add_argument("--title", default="", help="Extracted document title.")
    parser.add_argument("--subtitle", default="", help="Extracted document subtitle.")
    parser.add_argument("--discipline", default="", help="Extracted discipline.")
    parser.add_argument("--institution", default="", help="Extracted granting institution.")
    parser.add_argument("--doctoral-school", default="", help="Extracted doctoral school.")
    parser.add_argument("--degree-type", default="", help="Extracted degree type.")
    parser.add_argument("--year", default="", help="Extracted defense year.")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--max-docs-per-role", type=int, default=20)
    parser.add_argument("--reference-top-k", type=int, default=3)
    parser.add_argument("--weight-name", type=float, default=DEFAULT_WEIGHT_NAME)
    parser.add_argument("--weight-attrra-source", type=float, default=DEFAULT_WEIGHT_ATTRRA_SOURCE)
    parser.add_argument("--weight-attrra-note", type=float, default=DEFAULT_WEIGHT_ATTRRA_NOTE)
    parser.add_argument("--weight-references", type=float, default=DEFAULT_WEIGHT_REFERENCES)
    parser.add_argument("--weight-institution-year", type=float, default=DEFAULT_WEIGHT_INSTITUTION_YEAR)
    parser.add_argument(
        "--embedding-model",
        default="",
        help="Optional sentence-transformers model name. Omit to use lexical cosine scoring.",
    )
    parser.add_argument("--accept-threshold", type=float, default=0.65)
    parser.add_argument("--margin-threshold", type=float, default=0.08)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--backoff", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidates, search_meta = find_candidates(
        args.name,
        first_name_override=args.first_name or None,
        last_name_override=args.last_name or None,
        timeout=args.timeout,
        retries=args.retries,
        backoff=args.backoff,
        max_candidates=args.max_candidates,
    )

    for candidate in candidates:
        fetch_attrra(candidate, args.timeout, args.retries, args.backoff)
        fetch_references(candidate, args.timeout, args.retries, args.backoff, args.max_docs_per_role)
        score_candidate(args, candidate)

    ranked = sorted(candidates, key=lambda item: item.score.final, reverse=True)
    status = status_for_ranked(ranked, args.accept_threshold, args.margin_threshold)
    result = {
        "source": "idref_qualinka_alignment",
        "query": {
            "name": args.name,
            "title": args.title,
            "subtitle": args.subtitle,
            "discipline": args.discipline,
            "institution": args.institution,
            "doctoral_school": args.doctoral_school,
            "degree_type": args.degree_type,
            "year": args.year,
        },
        "candidate_search": search_meta,
        "score_weights": score_weights_to_json(args),
        "status": status,
        "best_ppn": ranked[0].ppn if status == "accepted" else None,
        "best_candidate": candidate_to_json(ranked[0]) if ranked else None,
        "candidates": [candidate_to_json(candidate) for candidate in ranked],
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
