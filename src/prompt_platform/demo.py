from __future__ import annotations

from pathlib import Path

from prompt_platform.abtesting import ABTestSimulator
from prompt_platform.evaluation import EvaluationEngine
from prompt_platform.experiments import ExperimentRunner
from prompt_platform.model_backends import build_model_client
from prompt_platform.promotion import PromotionManager
from prompt_platform.regression import RegressionDetector
from prompt_platform.registry import PromptRegistry
from prompt_platform.reports import ReportBuilder
from prompt_platform.utils import dump_json, ensure_dir


def seed_demo_registry(registry: PromptRegistry, root: Path) -> None:
    registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v1.yaml", created_by="demo-user")
    registry.create_or_version(root / "configs" / "prompts" / "support_classifier_v2.yaml", created_by="demo-user")
    registry.create_or_version(root / "configs" / "prompts" / "executive_summary_v1.yaml", created_by="demo-user")


def run_demo(
    root: Path,
    registry: PromptRegistry,
    evaluation_engine: EvaluationEngine,
    experiment_runner: ExperimentRunner,
    promotion_manager: PromotionManager,
    backend_configs: dict[str, dict],
    mode: str,
    output_dir: Path,
) -> dict:
    seed_demo_registry(registry, root)
    client = build_model_client("mock", backend_configs["mock"], model="mock-model")
    baseline = evaluation_engine.run(
        "support_classifier:1",
        root / "data" / "golden" / "support_classifier.jsonl",
        backend="mock",
        model_client=client,
        mode=mode,
        metrics=["exact_match", "token_f1"],
    )
    candidate = evaluation_engine.run(
        "support_classifier:2",
        root / "data" / "golden" / "support_classifier.jsonl",
        backend="mock",
        model_client=client,
        mode=mode,
        metrics=["exact_match", "token_f1"],
    )
    experiment = experiment_runner.run(root / "configs" / "experiments" / "support_classifier_tournament.yaml")
    regression = RegressionDetector.from_file(root / "configs" / "thresholds" / "default.yaml").check(baseline, candidate)
    ab_summary = ABTestSimulator().simulate(root / "configs" / "experiments" / "support_classifier_ab.yaml")
    decision = promotion_manager.evaluate_candidate(
        prompt_name="support_classifier",
        baseline=baseline,
        candidate=candidate,
        regression=regression,
        alias="staging",
        requested_by="platform-bot",
        ab_summary=ab_summary,
    )
    if decision.recommendation == "promote":
        promotion_manager.promote("support_classifier", "staging", 2, "platform-bot", "staging")
    ensure_dir(output_dir / "evaluations")
    dump_json(output_dir / "evaluations" / "support_classifier_baseline.json", baseline.model_dump(mode="json"))
    dump_json(output_dir / "evaluations" / "support_classifier_candidate.json", candidate.model_dump(mode="json"))
    dump_json(output_dir / "summary.json", {
        "baseline": baseline.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json"),
        "experiment": experiment,
        "regression": regression.model_dump(mode="json"),
        "ab_summary": ab_summary,
        "decision": decision.model_dump(mode="json"),
    })
    reports = ReportBuilder(output_dir)
    reports.write("experiment_leaderboard", experiment, "json")
    reports.write("experiment_leaderboard", experiment, "html")
    reports.write("abtest_summary", ab_summary, "json")
    reports.write("promotion_decision", decision.model_dump(mode="json"), "md")
    return {
        "baseline": baseline.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json"),
        "experiment": experiment,
        "regression": regression.model_dump(mode="json"),
        "ab_summary": ab_summary,
        "decision": decision.model_dump(mode="json"),
    }
