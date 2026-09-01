from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MembershipFunction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    kind: Literal["triangular", "trapezoidal", "gaussian", "bell", "sigmoid", "s_shape", "z_shape", "pi_shape"] = "triangular"
    parameters: tuple[float, ...]
    locked: bool = False

    @model_validator(mode="after")
    def validate_parameters(self) -> "MembershipFunction":
        expected = {"triangular": 3, "trapezoidal": 4, "gaussian": 2, "bell": 3, "sigmoid": 2, "s_shape": 2, "z_shape": 2, "pi_shape": 4}[self.kind]
        if len(self.parameters) != expected:
            raise ValueError(f"{self.kind} membership requires {expected} parameters.")
        if self.kind in {"triangular", "trapezoidal", "s_shape", "z_shape", "pi_shape"} and any(a > b for a, b in zip(self.parameters, self.parameters[1:])):
            raise ValueError(f"{self.kind} membership parameters must be ordered.")
        if self.kind == "triangular" and self.parameters[0] == self.parameters[2]:
            raise ValueError("Triangular membership support must have non-zero width.")
        if self.kind in {"gaussian", "bell"} and self.parameters[1] <= 0:
            raise ValueError(f"{self.kind} membership width must be positive.")
        return self


class FuzzyVariable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    minimum: float
    maximum: float
    terms: list[MembershipFunction] = Field(min_length=1)
    role: Literal["input", "output"] = "input"
    dataset_feature: str | None = Field(default=None, min_length=1, max_length=120)
    units: str | None = Field(default=None, max_length=80)
    locked: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> "FuzzyVariable":
        if not self.minimum < self.maximum:
            raise ValueError("Variable minimum must be smaller than maximum.")
        for term in self.terms:
            if term.kind in {"triangular", "trapezoidal", "s_shape", "z_shape", "pi_shape"}:
                a, c = term.parameters[0], term.parameters[-1]
            elif term.kind == "gaussian":
                center, width = term.parameters; a, c = center - 4 * width, center + 4 * width
            elif term.kind == "bell":
                width, _, center = term.parameters; a, c = center - 4 * width, center + 4 * width
            else:
                a, c = self.minimum, self.maximum
            if a < self.minimum or c > self.maximum:
                raise ValueError(f"Term {term.name!r} exceeds variable range for {self.name!r}.")
        if len({term.name for term in self.terms}) != len(self.terms):
            raise ValueError(f"Term names must be unique for variable {self.name!r}.")
        return self


class AntecedentClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str = Field(min_length=1)
    term: str = Field(min_length=1)


class SugenoConsequent(BaseModel):
    """A declarative Type-1 Sugeno consequent executed by the canonical FIS."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["constant", "linear"] = "constant"
    constant: float | None = None
    coefficients: dict[str, float] = Field(default_factory=dict)
    intercept: float = 0.0

    @model_validator(mode="after")
    def validate_shape(self) -> "SugenoConsequent":
        if self.kind == "constant":
            if self.constant is None:
                raise ValueError("A constant Sugeno consequent requires constant.")
            if self.coefficients:
                raise ValueError("A constant Sugeno consequent cannot contain coefficients.")
        elif self.constant is not None:
            raise ValueError("A linear Sugeno consequent uses intercept, not constant.")
        return self


class FuzzyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    clauses: list[AntecedentClause] = Field(min_length=1)
    connector: Literal["and", "or"] = "and"
    output_term: str = Field(min_length=1)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    enabled: bool = True
    sugeno_consequent: SugenoConsequent | None = None


class CentroidSampling(str, Enum):
    """Declared numerical quadrature convention for Mamdani centroids."""

    INCLUSIVE_NODES = "inclusive_nodes"
    MIDPOINT_CELLS = "midpoint_cells"


class OperatorSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    and_operator: Literal["min", "product", "lukasiewicz", "hamacher", "einstein"] = "min"
    or_operator: Literal["max", "probabilistic_sum", "bounded_sum", "hamacher", "einstein"] = "max"
    implication: Literal["min", "product"] = "min"
    aggregation: Literal["max", "probabilistic_sum", "bounded_sum", "hamacher", "einstein"] = "max"
    defuzzification: Literal["centroid"] = "centroid"
    centroid_resolution: int = Field(default=401, ge=1, le=100_000)
    centroid_sampling: CentroidSampling = CentroidSampling.MIDPOINT_CELLS

    @model_validator(mode="after")
    def validate_centroid_configuration(self) -> "OperatorSet":
        if self.centroid_sampling is CentroidSampling.INCLUSIVE_NODES and self.centroid_resolution < 2:
            raise ValueError("Inclusive-node centroid sampling requires a resolution of at least 2.")
        return self


class FISSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    fis_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    system_type: Literal["mamdani", "sugeno"] = "mamdani"
    inputs: list[FuzzyVariable] = Field(min_length=1)
    output: FuzzyVariable
    rules: list[FuzzyRule] = Field(min_length=1)
    operators: OperatorSet = Field(default_factory=OperatorSet)
    semantic_hash: str | None = None

    @model_validator(mode="after")
    def validate_references(self) -> "FISSpec":
        input_map = {variable.name: variable for variable in self.inputs}
        if len(input_map) != len(self.inputs):
            raise ValueError("FIS input names must be unique.")
        if self.output.name in input_map:
            raise ValueError("FIS output name must differ from every input name.")
        if any(variable.role != "input" for variable in self.inputs) or self.output.role != "output":
            raise ValueError("FIS variables must have input roles and the output must have output role.")
        output_terms = {term.name for term in self.output.terms}
        for rule in self.rules:
            for clause in rule.clauses:
                variable = input_map.get(clause.variable)
                if variable is None:
                    raise ValueError(f"Rule {rule.name!r} references unknown input {clause.variable!r}.")
                if clause.term not in {term.name for term in variable.terms}:
                    raise ValueError(
                        f"Rule {rule.name!r} references unknown term {clause.term!r} on {clause.variable!r}."
                    )
            if rule.output_term not in output_terms:
                raise ValueError(f"Rule {rule.name!r} references unknown output term {rule.output_term!r}.")
            if self.system_type == "sugeno":
                if rule.sugeno_consequent is None:
                    raise ValueError(f"Sugeno rule {rule.name!r} requires a Sugeno consequent.")
                unknown = set(rule.sugeno_consequent.coefficients) - set(input_map)
                if unknown:
                    raise ValueError(f"Sugeno rule {rule.name!r} references unknown input(s): {sorted(unknown)}.")
            elif rule.sugeno_consequent is not None:
                raise ValueError("Mamdani rules cannot contain a Sugeno consequent.")
        return self


class MembershipTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str
    value: float
    memberships: dict[str, float]


class RuleTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: UUID
    name: str
    enabled: bool
    connector: str
    clause_values: dict[str, float]
    firing_strength: float
    weight: float
    weighted_firing_strength: float
    output_term: str
    consequent_value: float | None = None


class FISTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_schema_version: int = 2
    fis_id: UUID
    semantic_hash: str
    input_values: dict[str, float]
    memberships: list[MembershipTrace]
    rules: list[RuleTrace]
    output_grid: list[float]
    aggregated_membership: list[float]
    defuzzification: Literal["centroid"] = "centroid"
    output_domain: tuple[float, float] | None = None
    centroid_resolution: int | None = None
    centroid_sampling: CentroidSampling | None = None
    centroid_dx: float | None = None
    centroid_sample_count: int | None = None
    final_output: float
    reconstruction_output: float
    reconstruction_error: float
    inference_kind: Literal["mamdani", "sugeno"] = "mamdani"


class FISEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_name: str
    output: float
    trace: FISTrace


class ResponseSurfaceSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    output: float | None = None


class ResponseSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fis_id: UUID
    semantic_hash: str
    x_variable: str
    y_variable: str
    fixed_inputs: dict[str, float]
    resolution: int
    samples: list[ResponseSurfaceSample]
