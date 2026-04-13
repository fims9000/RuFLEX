from __future__ import annotations

from importlib import import_module
from typing import Any

from ruflex.core.enums import MembershipKind
from ruflex.core.rules import RuleBaseSpec
from ruflex.core.variables import VariableSpec
from ruflex.models.specs import DecisionLayerSpec, HierarchicalModelSpec, ShallowModelSpec, TransparentBlockSpec

import torch


def import_ruanfis_backend():
    try:
        return import_module("ruanfis")
    except ImportError as exc:
        raise RuntimeError(
            "The ruanfis backend is not available. Keep the vendored copy under src/ruanfis "
            "or install the optional external backend dependency."
        ) from exc


def to_backend_variable(backend: Any, variable: VariableSpec):
    membership = variable.membership
    if membership.kind is MembershipKind.GAUSSIAN:
        backend_membership = backend.GaussianMembership(
            centers=membership.centers,
            spreads=membership.spreads,
            term_names=membership.term_names,
            min_spread=membership.min_spread,
        )
    elif membership.kind is MembershipKind.GENERALIZED_BELL:
        backend_membership = backend.GeneralizedBellMembership(
            centers=membership.centers,
            widths=membership.widths,
            slopes=membership.slopes,
            term_names=membership.term_names,
            min_width=membership.min_width,
            min_slope=membership.min_slope,
        )
    else:
        raise ValueError(
            "The current differentiable backend supports only Gaussian and generalized bell "
            "memberships. Triangular and trapezoidal terms are available in the RuFLEX core "
            "for serialization and visualization, but are not yet mapped to ruanfis."
        )
    return backend.FuzzyVariable(name=variable.name, membership=backend_membership)


def _gate_weight_to_backend_init(weight: float) -> float:
    value = float(weight)
    if 0.0 < value < 1.0:
        return float(torch.logit(torch.tensor(value, dtype=torch.float32), eps=1e-4).item())
    return value


def to_backend_rule_base(backend: Any, rule_base: RuleBaseSpec, variables: tuple[VariableSpec, ...] | list[VariableSpec]):
    variable_lookup = {variable.name: index for index, variable in enumerate(variables)}
    backend_rules = []
    for rule in rule_base.active_rules:
        antecedents = []
        for antecedent in rule.antecedents:
            if antecedent.variable_name not in variable_lookup:
                raise ValueError(
                    f"Variable {antecedent.variable_name!r} is not available in the current layer variables."
                )
            variable_index = variable_lookup[antecedent.variable_name]
            variable = variables[variable_index]
            if antecedent.term_name not in variable.term_names:
                raise ValueError(
                    f"Term {antecedent.term_name!r} is not available in variable {variable.name!r}."
                )
            antecedents.append(
                backend.Antecedent(
                    variable_index=variable_index,
                    term_index=variable.term_names.index(antecedent.term_name),
                )
            )
        backend_rules.append(
            backend.RuleSpec(
                antecedents=tuple(antecedents),
                name=rule.identifier,
                gate_init=_gate_weight_to_backend_init(rule.weight),
            )
        )
    if not backend_rules:
        raise ValueError("A manual rule base must contain at least one active rule.")
    return backend.RuleBase(tuple(backend_rules))


def to_backend_block_config(backend: Any, spec: TransparentBlockSpec):
    return backend.TransparentBlockConfig(
        name=spec.name,
        input_indices=tuple(spec.input_indices),
        variables=tuple(to_backend_variable(backend, variable) for variable in spec.variables),
        n_concepts=spec.n_concepts,
        concept_names=spec.concept_names,
        max_rule_arity=spec.max_rule_arity,
        max_rules=spec.max_rules,
        gate_init=spec.gate_init,
        rule_generation_mode=spec.rule_generation_mode,
        prototype_term_limit=spec.prototype_term_limit,
        prototype_variable_pool_size=spec.prototype_variable_pool_size,
        prototype_sample_size=spec.prototype_sample_size,
    )


def to_backend_decision_layer_config(backend: Any, spec: DecisionLayerSpec):
    return backend.DecisionLayerConfig(
        name=spec.name,
        variables=tuple(to_backend_variable(backend, variable) for variable in spec.variables),
        output_dim=spec.output_dim,
        output_names=spec.output_names,
        max_rule_arity=spec.max_rule_arity,
        max_rules=spec.max_rules,
        gate_init=spec.gate_init,
        rule_generation_mode=spec.rule_generation_mode,
        prototype_term_limit=spec.prototype_term_limit,
        prototype_variable_pool_size=spec.prototype_variable_pool_size,
        prototype_sample_size=spec.prototype_sample_size,
    )


def _apply_hidden_rule_consequents(layer: Any, spec: TransparentBlockSpec) -> None:
    if spec.rule_base is None:
        return
    with torch.no_grad():
        for rule_index, rule in enumerate(spec.rule_base.active_rules):
            if not rule.consequent:
                continue
            row = []
            for concept_name in layer.output_names:
                row.append(float(rule.consequent.get(concept_name, 0.5)))
            tensor = torch.tensor(row, dtype=layer.raw_consequents.dtype, device=layer.raw_consequents.device)
            tensor = tensor.clamp(1e-4, 1.0 - 1e-4)
            layer.raw_consequents[rule_index].copy_(torch.logit(tensor, eps=1e-4))


def _resolve_decision_key(
    key: str,
    *,
    variable_lookup: dict[str, int],
    output_lookup: dict[str, int],
    output_dim: int,
) -> tuple[str, int | None, int]:
    if ":" in key:
        left, right = key.split(":", 1)
        if left == "bias":
            if right not in output_lookup:
                raise ValueError(f"Unknown output name in decision consequent key: {key!r}.")
            return ("bias", None, output_lookup[right])
        if left not in variable_lookup or right not in output_lookup:
            raise ValueError(f"Unknown decision consequent key: {key!r}.")
        return ("weight", variable_lookup[left], output_lookup[right])

    if key == "bias":
        if output_dim != 1:
            raise ValueError("Plain 'bias' key is only supported for single-output decision layers.")
        return ("bias", None, 0)
    if key in variable_lookup:
        if output_dim != 1:
            raise ValueError(
                f"Plain variable key {key!r} is only supported for single-output decision layers."
            )
        return ("weight", variable_lookup[key], 0)
    if key in output_lookup:
        return ("bias", None, output_lookup[key])
    raise ValueError(f"Unsupported decision consequent key: {key!r}.")


def _apply_decision_rule_consequents(layer: Any, spec: DecisionLayerSpec) -> None:
    if spec.rule_base is None:
        return
    variable_lookup = {variable.name: index for index, variable in enumerate(spec.variables)}
    output_lookup = {name: index for index, name in enumerate(layer.output_names)}
    with torch.no_grad():
        for rule_index, rule in enumerate(spec.rule_base.active_rules):
            if not rule.consequent:
                continue
            for key, value in rule.consequent.items():
                kind, variable_index, output_index = _resolve_decision_key(
                    key,
                    variable_lookup=variable_lookup,
                    output_lookup=output_lookup,
                    output_dim=layer.output_dim,
                )
                if kind == "bias":
                    layer.rule_bias[rule_index, output_index] = float(value)
                else:
                    layer.rule_weights[rule_index, variable_index, output_index] = float(value)


def build_connected_block(
    backend: Any,
    spec: TransparentBlockSpec,
    sample_inputs: torch.Tensor | None = None,
):
    if spec.rule_base is None:
        return backend.build_transparent_block(
            to_backend_block_config(backend, spec),
            sample_inputs=sample_inputs,
        )

    layer = backend.TransparentFuzzyBlock(
        name=spec.name,
        variables=tuple(to_backend_variable(backend, variable) for variable in spec.variables),
        rule_base=to_backend_rule_base(backend, spec.rule_base, spec.variables),
        n_concepts=spec.n_concepts,
        concept_names=spec.concept_names,
    )
    _apply_hidden_rule_consequents(layer, spec)
    return backend.ConnectedFuzzyBlock(block=layer, input_indices=spec.input_indices)


def build_decision_layer(
    backend: Any,
    spec: DecisionLayerSpec,
    sample_inputs: torch.Tensor | None = None,
):
    if spec.rule_base is None:
        return backend.build_decision_layer(
            to_backend_decision_layer_config(backend, spec),
            sample_inputs=sample_inputs,
        )

    layer = backend.SugenoDecisionLayer(
        name=spec.name,
        variables=tuple(to_backend_variable(backend, variable) for variable in spec.variables),
        rule_base=to_backend_rule_base(backend, spec.rule_base, spec.variables),
        output_dim=spec.output_dim,
        output_names=spec.output_names,
    )
    _apply_decision_rule_consequents(layer, spec)
    return layer


def to_backend_hierarchical_config(backend: Any, spec: HierarchicalModelSpec):
    return backend.HierarchicalModelConfig(
        input_dim=spec.input_dim,
        stages=tuple(
            backend.StageConfig(
                name=stage.name,
                blocks=tuple(to_backend_block_config(backend, block) for block in stage.blocks),
            )
            for stage in spec.stages
        ),
        decision_layer=to_backend_decision_layer_config(backend, spec.decision_layer),
        decision_input_mode=spec.decision_input_mode,
    )


def to_backend_shallow_config(backend: Any, spec: ShallowModelSpec):
    return backend.ShallowFuzzyModelConfig(
        input_dim=spec.input_dim,
        feature_block=to_backend_block_config(backend, spec.feature_block),
        decision_layer=to_backend_decision_layer_config(backend, spec.decision_layer),
        stage_name=spec.stage_name,
    )


def spec_has_manual_rule_bases(spec: HierarchicalModelSpec | ShallowModelSpec) -> bool:
    if isinstance(spec, ShallowModelSpec):
        return spec.feature_block.rule_base is not None or spec.decision_layer.rule_base is not None
    return any(block.rule_base is not None for stage in spec.stages for block in stage.blocks) or (
        spec.decision_layer.rule_base is not None
    )


def build_backend_hierarchical_model(
    backend: Any,
    spec: HierarchicalModelSpec,
    sample_inputs: torch.Tensor | None = None,
):
    if sample_inputs is not None:
        sample_inputs = sample_inputs.detach().cpu()
    stages = []
    current_samples = sample_inputs
    stage_outputs = []
    for stage_spec in spec.stages:
        blocks = []
        for block_spec in stage_spec.blocks:
            local_samples = None
            if current_samples is not None:
                local_samples = current_samples.index_select(
                    dim=1,
                    index=torch.tensor(block_spec.input_indices, dtype=torch.long, device=current_samples.device),
                )
            blocks.append(build_connected_block(backend, block_spec, sample_inputs=local_samples))
        stage = backend.FuzzyStage(name=stage_spec.name, blocks=blocks)
        stages.append(stage)
        if current_samples is not None:
            with torch.no_grad():
                current_samples = stage(current_samples)
                stage_outputs.append(current_samples)

    decision_samples = current_samples
    if sample_inputs is not None and spec.decision_input_mode == "all_stages" and stage_outputs:
        decision_samples = torch.cat(tuple(stage_outputs), dim=1)
    decision_layer = build_decision_layer(backend, spec.decision_layer, sample_inputs=decision_samples)
    return backend.DeepFuzzyFeatureModel(
        stages=stages,
        decision_layer=decision_layer,
        input_dim=spec.input_dim,
        decision_input_mode=spec.decision_input_mode,
    )


def build_backend_shallow_model(
    backend: Any,
    spec: ShallowModelSpec,
    sample_inputs: torch.Tensor | None = None,
):
    hierarchical = HierarchicalModelSpec(
        input_dim=spec.input_dim,
        stages=(
            type("StageSpecProxy", (), {"name": spec.stage_name, "blocks": (spec.feature_block,)})(),
        ),
        decision_layer=spec.decision_layer,
    )
    return build_backend_hierarchical_model(backend, hierarchical, sample_inputs=sample_inputs)


def build_backend_model_from_spec(
    backend: Any,
    spec: HierarchicalModelSpec | ShallowModelSpec,
    sample_inputs: torch.Tensor | None = None,
):
    if isinstance(spec, ShallowModelSpec):
        return build_backend_shallow_model(backend, spec, sample_inputs=sample_inputs)
    return build_backend_hierarchical_model(backend, spec, sample_inputs=sample_inputs)


def bootstrap_initialize_model_from_samples(
    backend: Any,
    model: Any,
    sample_inputs: torch.Tensor,
    sample_targets: torch.Tensor | None,
    bootstrap_config: Any,
) -> None:
    current_samples = sample_inputs.detach().cpu().to(dtype=torch.float32)
    targets = None if sample_targets is None else sample_targets.detach().cpu().to(dtype=torch.float32)
    for stage in model.stages:
        for connected_block in stage.blocks:
            local_inputs = current_samples.index_select(dim=1, index=connected_block.input_indices.cpu())
            backend.initialize_transparent_block_from_samples(
                connected_block.block,
                local_inputs,
                config=bootstrap_config,
            )
        with torch.no_grad():
            current_samples = stage(current_samples)
    backend.initialize_decision_layer_from_samples(
        model.decision_layer,
        current_samples,
        sample_targets=targets,
        config=bootstrap_config,
    )
