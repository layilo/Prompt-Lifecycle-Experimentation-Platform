from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from prompt_platform.model_backends import ModelClient
from prompt_platform.runtime import PromptResolver
from prompt_platform.schemas import EvaluationCase, EvaluationCaseResult, EvaluationDataset, EvaluationResult
from prompt_platform.utils import stable_hash


def exact_match(prediction: Any, expected: Any) -> float:
    return 1.0 if str(prediction).strip() == str(expected).strip() else 0.0


def token_f1(prediction: Any, expected: Any) -> float:
    pred_tokens = str(prediction).lower().split()
    exp_tokens = str(expected).lower().split()
    common = len(set(pred_tokens) & set(exp_tokens))
    if not pred_tokens or not exp_tokens or common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(exp_tokens)
    return 2 * precision * recall / (precision + recall)


def bleu_like(prediction: Any, expected: Any) -> float:
    pred_tokens = str(prediction).lower().split()
    exp_tokens = str(expected).lower().split()
    if not pred_tokens:
        return 0.0
    overlap = sum(1 for token in pred_tokens if token in exp_tokens)
    return overlap / len(pred_tokens)


def rouge_l_like(prediction: Any, expected: Any) -> float:
    a = str(prediction)
    b = str(expected)
    if not a or not b:
        return 0.0
    lengths = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, char_a in enumerate(a, start=1):
        for j, char_b in enumerate(b, start=1):
            lengths[i][j] = lengths[i - 1][j - 1] + 1 if char_a == char_b else max(lengths[i - 1][j], lengths[i][j - 1])
    return lengths[-1][-1] / max(len(b), 1)


def rubric_score(prediction: Any, expected: Any) -> float:
    return (exact_match(prediction, expected) + token_f1(prediction, expected)) / 2


class EvaluationEngine:
    def __init__(self, resolver: PromptResolver, evaluator_hooks: Optional[dict[str, Callable[[Any, Any], float]]] = None) -> None:
        self.resolver = resolver
        self.evaluators = {
            "exact_match": exact_match,
            "token_f1": token_f1,
            "bleu": bleu_like,
            "rouge_l": rouge_l_like,
            "rubric": rubric_score,
        }
        if evaluator_hooks:
            self.evaluators.update(evaluator_hooks)

    @staticmethod
    def load_dataset(path: Path) -> EvaluationDataset:
        cases: list[EvaluationCase] = []
        if path.suffix == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    cases.append(EvaluationCase.model_validate(json.loads(line)))
        elif path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    cases.append(
                        EvaluationCase(
                            id=row["id"],
                            task_type=row["task_type"],
                            inputs=json.loads(row["inputs"]),
                            expected=row["expected"],
                        )
                    )
        elif path.suffix in {".yaml", ".yml"}:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            cases = [EvaluationCase.model_validate(item) for item in payload["cases"]]
        else:
            raise ValueError(f"Unsupported dataset format: {path}")
        return EvaluationDataset(name=path.stem, path=str(path), cases=cases)

    def run(
        self,
        prompt_reference: str,
        dataset_path: Path,
        backend: str,
        model_client: ModelClient,
        mode: str = "mock",
        metrics: Optional[list[str]] = None,
    ) -> EvaluationResult:
        prompt = self.resolver.fetch(prompt_reference)
        dataset = self.load_dataset(dataset_path)
        selected_metrics = metrics or ["exact_match"]
        case_results: list[EvaluationCaseResult] = []
        for case in dataset.cases:
            rendered = self.resolver.render(prompt, case.inputs)
            response = model_client.generate(rendered, case.task_type, case.inputs)
            score_map = {metric: self.evaluators[metric](response.output, case.expected) for metric in selected_metrics if metric in self.evaluators}
            score = score_map.get("exact_match") or max(score_map.values(), default=0.0)
            case_results.append(
                EvaluationCaseResult(
                    case_id=case.id,
                    output=response.output,
                    expected=case.expected,
                    score=score,
                    passed=score >= 0.5,
                    metrics=score_map,
                    latency_ms=response.latency_ms,
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                    cost=response.cost,
                    structured_valid=response.structured_valid,
                )
            )
        total = len(case_results) or 1
        aggregate_metrics = {
            "pass_rate": sum(1 for item in case_results if item.passed) / total,
            "accuracy": sum(item.metrics.get("exact_match", item.score) for item in case_results) / total,
            "token_f1": sum(item.metrics.get("token_f1", 0.0) for item in case_results) / total,
            "bleu": sum(item.metrics.get("bleu", 0.0) for item in case_results) / total,
            "rouge_l": sum(item.metrics.get("rouge_l", 0.0) for item in case_results) / total,
            "latency_ms": sum(item.latency_ms for item in case_results) / total,
            "tokens_in": sum(item.tokens_in for item in case_results) / total,
            "tokens_out": sum(item.tokens_out for item in case_results) / total,
            "total_cost": sum(item.cost for item in case_results),
            "structured_validity": sum(1 for item in case_results if item.structured_valid) / total,
        }
        run_id = stable_hash({"prompt": prompt_reference, "dataset": dataset.path, "backend": backend, "metrics": selected_metrics})
        return EvaluationResult(
            run_id=run_id,
            prompt_name=prompt.name,
            version=prompt.version,
            dataset_name=dataset.name,
            backend=backend,
            mode=mode,
            aggregate_metrics=aggregate_metrics,
            case_results=case_results,
            metadata={"dataset_path": str(dataset_path), "metrics": selected_metrics},
        )
