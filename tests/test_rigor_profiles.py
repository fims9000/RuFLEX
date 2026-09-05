from ruflex.application.datasets import rigor_profile_contract


def test_rigor_profiles_declare_evidence_and_stop_rules_without_claiming_truth() -> None:
    exploratory = rigor_profile_contract("EXPLORATORY")
    confirmatory = rigor_profile_contract("CONFIRMATORY")
    high_assurance = rigor_profile_contract("HIGH_ASSURANCE_LIKE")
    assert "FinalTestEvaluation" not in exploratory.required_evidence
    assert {"SplitContract", "TransformPipelineContract", "FinalTestEvaluation"} <= set(confirmatory.required_evidence)
    assert "independent human sign-off" in " ".join(high_assurance.stop_rules).lower()
    assert "not a truth" in high_assurance.scientific_note
