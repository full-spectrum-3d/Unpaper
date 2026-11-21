"""Pomiar etapu LLM na przypadkach z `llm_eval/cases`.

Uruchom z backend/ (Ollama pod LLM_BASE_URL, domyślnie http://localhost:11434):

    uv run python -m llm_eval.run --model rules --model qwen3:4b --model qwen3:8b
    uv run python -m llm_eval.run --model qwen3:8b --case swietlica --case nadplata

`rules` to szkic z reguł bez LLM (`rule_draft`). Wynik: tabela w terminalu i JSON
w `llm_eval/results/<data>.json` (ten katalog nie trafia do repozytorium).
"""

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models.document import DocumentModel
from app.models.draft import FormDraft
from app.models.warning import ConversionWarning
from app.pipeline.analyze import analyze, prompt_messages
from app.pipeline.build import build_form
from app.pipeline.draft_normalize import normalize_draft
from app.pipeline.llm_client import OllamaClient
from app.pipeline.rule_draft import rule_draft
from app.pipeline.verify import verify_form
from llm_eval.metrics import score_draft

HERE = Path(__file__).parent
RULES = "rules"


def load_cases(names: list[str] | None = None) -> list[dict[str, Any]]:
    cases = []
    for path in sorted((HERE / "cases").glob("*.json")):
        if names and path.stem not in names:
            continue
        case = json.loads(path.read_text(encoding="utf-8"))
        case["slug"] = path.stem
        case["doc"] = DocumentModel.model_validate(case["document"])
        cases.append(case)
    return cases


async def run_case(
    case: dict[str, Any],
    model: str,
    client: OllamaClient | None,
    settings: Settings,
    budget_s: float,
) -> dict[str, Any]:
    doc: DocumentModel = case["doc"]
    started = time.monotonic()
    row: dict[str, Any] = {"case": case["slug"], "model": model}
    if model == RULES:
        draft = rule_draft(doc)
        warnings: list[ConversionWarning] = []
        if draft is not None:
            draft, warnings = normalize_draft(draft, doc)
        row.update(fallback=False, retries=0, prompt_tokens=0, output_tokens=0)
    else:
        if client is None:
            raise ValueError("model LLM wymaga klienta Ollamy")
        result = await analyze(
            doc,
            settings.model_copy(update={"llm_model": model}),
            client,
            deadline=time.monotonic() + budget_s,
        )
        draft, warnings = result.draft, result.warnings
        row.update(
            fallback=result.fallback,
            fallback_reason=result.fallback_reason,
            retries=result.retries,
            prompt_tokens=result.prompt_tokens,
            output_tokens=result.output_tokens,
        )
    row["duration_s"] = round(time.monotonic() - started, 1)
    codes = [w.code for w in warnings]
    row.update(
        applicant_removed=codes.count("W20_APPLICANT_FIELD_REMOVED"),
        conditions_removed=codes.count("W21_CONDITION_REMOVED"),
        rule_based="W24_RULE_BASED_DRAFT" in codes,
        statements=len(draft.statements) if draft else 0,
    )
    score = score_draft(draft, case["expected"])
    row.update(asdict(score), recall=round(score.recall, 2), precision=round(score.precision, 2))
    if draft is not None:
        check = verify_form(build_form(draft).form.to_import_json(), autofix=False)
        row["form_valid"] = check.valid
    row["fields"] = [(f.label, f.kind) for _, f in draft.iter_fields()] if draft else []
    return row


def rescore(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Metryki pól od nowa z zapisanych etykiet i typów (po zmianie oczekiwań lub metryk)."""
    cases = {c["slug"]: c for c in load_cases()}
    for row in rows:
        fields = [
            {"id": f"f{i}", "label": label, "kind": kind, "required": True}
            for i, (label, kind) in enumerate(row["fields"], 1)
        ]
        draft = FormDraft.model_validate(
            {
                "title": "x",
                "authority_kind": "URZAD",
                "authority_name": "x",
                "applicant_kinds": ["SELF"],
                "subject_pages": [
                    {
                        "title": "x",
                        "sections": [{"title": "x", "repeating": False, "fields": fields}],
                    }
                ]
                if fields
                else [],
            }
        )
        score = score_draft(draft, cases[row["case"]]["expected"])
        keep = {"title_ok": row["title_ok"], "authority_ok": row["authority_ok"]}
        row.update(asdict(score), **keep)
        row.update(recall=round(score.recall, 2), precision=round(score.precision, 2))
    return rows


def table(rows: list[dict[str, Any]]) -> str:
    head = (
        "| przypadek | model | czas s | wyj. tok | pola ok | trafność | precyzja | typy ok "
        "| tytuł | adresat | usunięte wnioskodawcy | fallback |"
    )
    lines = [head, "|" + "---|" * 12]
    for r in rows:
        mark = {True: "✓", False: "✗", None: "-"}
        fb = "reguły" if r["rule_based"] else ("tak" if r["fallback"] else "")
        lines.append(
            f"| {r['case']} | {r['model']} | {r['duration_s']} | {r['output_tokens']} "
            f"| {r['matched']}/{r['expected']} | {r['recall']:.0%} | {r['precision']:.0%} "
            f"| {r['kind_ok']}/{r['matched']} | {mark[r['title_ok']]} | {mark[r['authority_ok']]} "
            f"| {r['applicant_removed']} | {fb} |"
        )
    return "\n".join(lines)


def summary(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| model | trafność | precyzja | typy ok | śr. czas s | fallback |",
        "|---|---|---|---|---|---|",
    ]
    for model in dict.fromkeys(r["model"] for r in rows):
        rs = [r for r in rows if r["model"] == model]
        exp = sum(r["expected"] for r in rs)
        got = sum(r["matched"] for r in rs)
        draft = sum(r["draft_fields"] for r in rs)
        extra = sum(r["extra"] for r in rs)
        kinds = sum(r["kind_ok"] for r in rs)
        lines.append(
            f"| {model} | {got}/{exp} ({got / exp:.0%}) | {(draft - extra) / max(draft, 1):.0%} "
            f"| {kinds}/{got} | {sum(r['duration_s'] for r in rs) / len(rs):.0f} "
            f"| {sum(r['fallback'] for r in rs)}/{len(rs)} |"
        )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", action="append", help="rules lub nazwa modelu")
    parser.add_argument("--rescore", type=Path, help="przelicz metryki zapisanego wyniku")
    parser.add_argument("--case", action="append", help="slug przypadku (domyślnie wszystkie)")
    parser.add_argument("--budget", type=float, default=900, help="budżet sekund na przypadek")
    args = parser.parse_args()
    if args.rescore:
        rescored = rescore(json.loads(args.rescore.read_text(encoding="utf-8")))
        print(table(rescored) + "\n\n" + summary(rescored))
        return
    if not args.model:
        parser.error("podaj --model albo --rescore")

    settings = Settings(
        app_env="development",
        auth_enabled=False,
        llm_base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434"),
        llm_timeout_s=int(args.budget),
    )
    cases = load_cases(args.case)
    client = OllamaClient(settings) if any(m != RULES for m in args.model) else None
    rows: list[dict[str, Any]] = []
    out = HERE / "results" / f"{datetime.now():%Y-%m-%d_%H%M}.json"
    out.parent.mkdir(exist_ok=True)
    try:
        for model in args.model:
            if client is not None and model != RULES:
                # Jak w produkcji: jeden model w RAM, rozgrzany razem z prefiksem promptu.
                for loaded in await client.loaded_models() - {model}:
                    await client.unload(loaded)
                started = time.monotonic()
                await client.warm_up(model, prompt_messages(""))
                print(f"{model}: rozgrzanie {time.monotonic() - started:.0f} s", flush=True)
            for case in cases:
                row = await run_case(case, model, client, settings, args.budget)
                rows.append(row)
                print(table([row]).split("\n")[-1], flush=True)
                out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        if client is not None:
            await client.aclose()
    print("\n" + table(rows) + "\n\n" + summary(rows) + f"\n\nwyniki: {out}")


if __name__ == "__main__":
    asyncio.run(main())
