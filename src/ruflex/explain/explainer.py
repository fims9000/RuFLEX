from __future__ import annotations

from ruflex.explain.payloads import ExplainabilityReportPayload, SampleDashboardPayload


class Explainer:
    def explain(self, model, features, top_k_rules: int = 2):
        return model.explain(features, top_k_rules=top_k_rules)

    def format_text(self, model, features, top_k_rules: int = 2) -> str:
        return model.format_explanations(features, top_k_rules=top_k_rules)

    def dashboard(self, model, features, top_k_rules: int = 2) -> tuple[SampleDashboardPayload, ...]:
        return model.explain_dashboard(features, top_k_rules=top_k_rules)

    def model_report(self, model, decimals: int = 3) -> str:
        return model.export_model_report(decimals=decimals)

    def report_payload(self, model, decimals: int = 3) -> ExplainabilityReportPayload:
        return model.explainability_report(decimals=decimals)

    def concept_flow(self, model, features, top_k_rules: int = 2):
        return model.concept_flow(features, top_k_rules=top_k_rules)

    def concept_flow_text(self, model, features, top_k_rules: int = 2, decimals: int = 4) -> str:
        return model.format_concept_flow(features, top_k_rules=top_k_rules, decimals=decimals)

    def path_flow(self, model, features, top_k_rules: int = 2):
        return model.path_concept_flow(features, top_k_rules=top_k_rules)

    def path_flow_text(self, model, features, top_k_rules: int = 2, decimals: int = 4) -> str:
        return model.format_path_concept_flow(features, top_k_rules=top_k_rules, decimals=decimals)

    def rule_chain_flow(self, model, features, top_k_rules: int = 2):
        return model.rule_chain_flow(features, top_k_rules=top_k_rules)

    def rule_chain_flow_text(self, model, features, top_k_rules: int = 2, decimals: int = 4) -> str:
        return model.format_rule_chain_flow(features, top_k_rules=top_k_rules, decimals=decimals)
