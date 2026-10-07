import { EChartsOption } from "echarts";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  FISEvaluation,
  FISSpec,
  DatasetState,
  FISCompatibilityIssue,
  ExpertCorrectionRevision,
  FuzzyRule,
  FuzzyVariable,
  MembershipFunction,
  ProductApiError,
  ProjectSummary,
  ResponseSurface,
  studioApi,
} from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import {
  Button,
  EmptyState,
  StatusBadge,
  TextInput,
} from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";
import { MembershipEditorCanvas } from "./MembershipEditorCanvas";
import { exactFisEvaluationMatchesCurrent } from "./exactFisEvaluation";
import { parseFisRunInputs } from "./fisRunInputs";

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
  return JSON.stringify(value) ?? "undefined";
}

function fisSemanticPayload(fis: FISSpec): FISSpec {
  const payload = cloneFis(fis);
  payload.semantic_hash = null;
  for (const variable of [...payload.inputs, payload.output]) {
    delete (variable as Partial<typeof variable>).locked;
    for (const term of variable.terms) delete (term as Partial<typeof term>).locked;
  }
  return payload;
}

const familyParameters: Record<MembershipFunction["kind"], number> = {
  triangular: 3,
  trapezoidal: 4,
  gaussian: 2,
  bell: 3,
  sigmoid: 2,
  s_shape: 2,
  z_shape: 2,
  pi_shape: 4,
};
const familyLabel: Record<MembershipFunction["kind"], string> = {
  triangular: "Triangle",
  trapezoidal: "Trapezoid",
  gaussian: "Gaussian",
  bell: "Generalized bell",
  sigmoid: "Sigmoid",
  s_shape: "S-shape",
  z_shape: "Z-shape",
  pi_shape: "Pi-shape",
};
function cloneFis(fis: FISSpec): FISSpec {
  return structuredClone(fis);
}
function defaultParameters(
  kind: MembershipFunction["kind"],
  minimum: number,
  maximum: number,
): number[] {
  const mid = (minimum + maximum) / 2;
  const q = (maximum - minimum) / 4;
  if (kind === "triangular") return [minimum, mid, maximum];
  if (kind === "trapezoidal")
    return [minimum, minimum + q, maximum - q, maximum];
  if (kind === "gaussian") return [mid, q / 4];
  if (kind === "bell") return [q / 4, 2, mid];
  if (kind === "sigmoid") return [1 / Math.max(q, 0.001), mid];
  if (kind === "s_shape" || kind === "z_shape")
    return [minimum + q, maximum - q];
  return [minimum, minimum + q, maximum - q, maximum];
}
function degree(x: number, term: MembershipFunction): number {
  const p = term.parameters;
  if (term.kind === "triangular") {
    const [a, b, c] = p;
    return x === b
      ? 1
      : x <= a || x >= c
        ? 0
        : x < b
          ? (x - a) / Math.max(b - a, 1e-12)
          : (c - x) / Math.max(c - b, 1e-12);
  }
  if (term.kind === "trapezoidal") {
    const [a, b, c, d] = p;
    return Math.max(
      0,
      Math.min(
        (x - a) / Math.max(b - a, 1e-12),
        1,
        (d - x) / Math.max(d - c, 1e-12),
      ),
    );
  }
  if (term.kind === "gaussian") {
    const [c, s] = p;
    return Math.exp(-0.5 * ((x - c) / s) ** 2);
  }
  if (term.kind === "bell") {
    const [a, b, c] = p;
    return 1 / (1 + Math.abs((x - c) / a) ** (2 * b));
  }
  if (term.kind === "sigmoid") {
    const [a, c] = p;
    return 1 / (1 + Math.exp(-Math.max(-60, Math.min(60, a * (x - c)))));
  }
  if (term.kind === "s_shape" || term.kind === "z_shape") {
    const [a, b] = p;
    const t = Math.max(0, Math.min(1, (x - a) / Math.max(b - a, 1e-12)));
    const s = t <= 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t);
    return term.kind === "s_shape" ? s : 1 - s;
  }
  const [a, b, c, d] = p;
  return Math.min(
    degree(x, { name: "_", kind: "s_shape", parameters: [a, b] }),
    degree(x, { name: "_", kind: "z_shape", parameters: [c, d] }),
  );
}
function membershipOption(variable: FuzzyVariable): EChartsOption {
  const xs = Array.from(
    { length: 101 },
    (_, i) =>
      variable.minimum + ((variable.maximum - variable.minimum) * i) / 100,
  );
  return {
    tooltip: { trigger: "axis" },
    legend: { data: variable.terms.map((t) => t.name) },
    grid: { left: 44, right: 18, top: 36, bottom: 30 },
    xAxis: { type: "value", min: variable.minimum, max: variable.maximum },
    yAxis: { type: "value", min: 0, max: 1 },
    series: variable.terms.map((term) => ({
      name: term.name,
      type: "line",
      showSymbol: false,
      data: xs.map((x) => [x, degree(x, term)]),
    })),
  };
}
function responseSurfaceOption(surface: ResponseSurface): EChartsOption {
  const outputs = surface.samples.flatMap((sample) =>
    sample.output === null ? [] : [sample.output],
  );
  const xValues = [...new Set(surface.samples.map((sample) => sample.x))];
  const yValues = [...new Set(surface.samples.map((sample) => sample.y))];
  return {
    tooltip: { position: "top" },
    grid: { left: 58, right: 30, top: 24, bottom: 52 },
    xAxis: { type: "category", name: surface.x_variable, data: xValues.map((value) => value.toFixed(4)) },
    yAxis: { type: "category", name: surface.y_variable, data: yValues.map((value) => value.toFixed(4)) },
    visualMap: {
      min: Math.min(...outputs),
      max: Math.max(...outputs),
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
    },
    series: [
      {
        type: "heatmap",
        data: surface.samples
          .filter((sample) => sample.output !== null)
          .map((sample) => [xValues.indexOf(sample.x), yValues.indexOf(sample.y), sample.output]),
      },
    ],
  };
}
function ruleText(rule: FuzzyRule, output: FuzzyVariable): string {
  return `IF ${rule.clauses.map((c) => `${c.variable} IS ${c.term}`).join(` ${rule.connector.toUpperCase()} `)} THEN ${output.name} IS ${rule.output_term} WITH ${rule.weight}`;
}
function outputCenter(output: FuzzyVariable, termName: string): number {
  const term = output.terms.find((item) => item.name === termName);
  if (!term) return (output.minimum + output.maximum) / 2;
  const p = term.parameters;
  return term.kind === "gaussian"
    ? p[0]
    : term.kind === "bell"
      ? p[2]
      : term.kind === "sigmoid"
        ? p[1]
        : (p[0] + p[p.length - 1]) / 2;
}


type FisSemanticChange = { path: string; before: string; after: string };

function stableValue(value: unknown): string {
  if (value === null || value === undefined) return "∅";
  if (typeof value === "number") return Number.isFinite(value) ? Number(value.toFixed(8)).toString() : String(value);
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function fisSemanticDiff(before: FISSpec, after: FISSpec): FisSemanticChange[] {
  const changes: FisSemanticChange[] = [];
  const push = (path: string, left: unknown, right: unknown) => {
    if (JSON.stringify(left) !== JSON.stringify(right)) {
      changes.push({ path, before: stableValue(left), after: stableValue(right) });
    }
  };

  push("FIS family", before.system_type, after.system_type);
  push("Model name", before.name, after.name);
  for (const key of Object.keys(before.operators) as Array<keyof FISSpec["operators"]>) {
    push(`Operator · ${key.replaceAll("_", " ")}`, before.operators[key], after.operators[key]);
  }

  const maxInputs = Math.max(before.inputs.length, after.inputs.length);
  for (let index = 0; index < maxInputs; index += 1) {
    const left = before.inputs[index];
    const right = after.inputs[index];
    if (!left || !right) {
      push(`Input ${index + 1}`, left?.name ?? null, right?.name ?? null);
      continue;
    }
    const label = right.name || left.name || `Input ${index + 1}`;
    push(`Input · ${label} · name`, left.name, right.name);
    push(`Input · ${label} · range`, [left.minimum, left.maximum], [right.minimum, right.maximum]);
    push(`Input · ${label} · dataset feature`, left.dataset_feature ?? null, right.dataset_feature ?? null);
    push(`Input · ${label} · locked`, left.locked ?? false, right.locked ?? false);
    const maxTerms = Math.max(left.terms.length, right.terms.length);
    for (let termIndex = 0; termIndex < maxTerms; termIndex += 1) {
      const leftTerm = left.terms[termIndex];
      const rightTerm = right.terms[termIndex];
      const termLabel = rightTerm?.name ?? leftTerm?.name ?? `term ${termIndex + 1}`;
      if (!leftTerm || !rightTerm) {
        push(`MF · ${label}.${termLabel}`, leftTerm ?? null, rightTerm ?? null);
        continue;
      }
      push(`MF · ${label}.${termLabel} · name`, leftTerm.name, rightTerm.name);
      push(`MF · ${label}.${termLabel} · family`, leftTerm.kind, rightTerm.kind);
      push(`MF · ${label}.${termLabel} · parameters`, leftTerm.parameters, rightTerm.parameters);
      push(`MF · ${label}.${termLabel} · locked`, leftTerm.locked ?? false, rightTerm.locked ?? false);
    }
  }

  push("Output · name", before.output.name, after.output.name);
  push("Output · range", [before.output.minimum, before.output.maximum], [after.output.minimum, after.output.maximum]);
  const maxOutputTerms = Math.max(before.output.terms.length, after.output.terms.length);
  for (let index = 0; index < maxOutputTerms; index += 1) {
    const left = before.output.terms[index];
    const right = after.output.terms[index];
    const label = right?.name ?? left?.name ?? `term ${index + 1}`;
    if (!left || !right) {
      push(`Output MF · ${label}`, left ?? null, right ?? null);
      continue;
    }
    push(`Output MF · ${label} · name`, left.name, right.name);
    push(`Output MF · ${label} · family`, left.kind, right.kind);
    push(`Output MF · ${label} · parameters`, left.parameters, right.parameters);
  }

  const beforeRules = new Map(before.rules.map((rule) => [rule.rule_id, rule]));
  const afterRules = new Map(after.rules.map((rule) => [rule.rule_id, rule]));
  const ruleIds = new Set([...beforeRules.keys(), ...afterRules.keys()]);
  for (const ruleId of ruleIds) {
    const left = beforeRules.get(ruleId);
    const right = afterRules.get(ruleId);
    const label = right?.name ?? left?.name ?? ruleId.slice(0, 8);
    if (!left || !right) {
      push(`Rule · ${label}`, left ?? null, right ?? null);
      continue;
    }
    push(`Rule · ${label} · enabled`, left.enabled, right.enabled);
    push(`Rule · ${label} · connector`, left.connector, right.connector);
    push(`Rule · ${label} · antecedent`, left.clauses, right.clauses);
    push(`Rule · ${label} · consequent term`, left.output_term, right.output_term);
    push(`Rule · ${label} · weight`, left.weight, right.weight);
    push(`Rule · ${label} · Sugeno consequent`, left.sugeno_consequent, right.sugeno_consequent);
  }
  return changes;
}
function parameterBounds(
  variable: FuzzyVariable,
  term: MembershipFunction,
  index: number,
): [number, number] {
  const span = variable.maximum - variable.minimum;
  if (
    (term.kind === "gaussian" && index === 1) ||
    (term.kind === "bell" && index === 0)
  )
    return [span / 400, span / 2];
  if (term.kind === "bell" && index === 1) return [0.1, 10];
  if (term.kind === "sigmoid" && index === 0)
    return [-20 / Math.max(span, 0.001), 20 / Math.max(span, 0.001)];
  return [variable.minimum, variable.maximum];
}
function rescaleTerm(
  term: MembershipFunction,
  oldMinimum: number,
  oldMaximum: number,
  minimum: number,
  maximum: number,
): number[] {
  const oldSpan = oldMaximum - oldMinimum;
  const newSpan = maximum - minimum;
  const mapPosition = (value: number) =>
    minimum + ((value - oldMinimum) / oldSpan) * newSpan;
  if (term.kind === "gaussian")
    return [mapPosition(term.parameters[0]), (term.parameters[1] / oldSpan) * newSpan];
  if (term.kind === "bell")
    return [
      (term.parameters[0] / oldSpan) * newSpan,
      term.parameters[1],
      mapPosition(term.parameters[2]),
    ];
  if (term.kind === "sigmoid")
    return [term.parameters[0] * (oldSpan / newSpan), mapPosition(term.parameters[1])];
  return term.parameters.map(mapPosition);
}

export function BuildWorkspace({
  project,
  dataset,
  evaluation,
  evaluationStatus = "available",
  evaluationError = null,
  onRetryEvaluation = () => undefined,
  theme,
  fis,
  sourceExplanationId,
  selectedExpertCorrectionId,
  onExpertCorrection,
  onFisChange,
  onEvaluation,
  onOpenTrace,
}: {
  project: ProjectSummary;
  dataset: DatasetState | null;
  evaluation: FISEvaluation | null;
  evaluationStatus?: "idle" | "loading" | "none" | "available" | "error";
  evaluationError?: string | null;
  onRetryEvaluation?: () => void;
  theme: StudioTheme;
  fis: FISSpec | null;
  sourceExplanationId?: string | null;
  selectedExpertCorrectionId?: string | null;
  onExpertCorrection?: (correction: ExpertCorrectionRevision | null) => void;
  onFisChange: (fis: FISSpec) => void;
  onEvaluation: (evaluation: FISEvaluation) => void;
  onOpenTrace: () => void;
}) {
  const [working, setWorking] = useState<FISSpec | null>(fis);
  const workingRef = useRef<FISSpec | null>(working);
  const hydratedProjectIdRef = useRef(project.session_id);
  const hydratedFisIdentityRef = useRef(fis ? `${fis.fis_id}:${fis.semantic_hash ?? ""}` : null);
  const preserveDraftOnHydrationHashRef = useRef<string | null>(null);
  const [editorHistory, setEditorHistory] = useState<FISSpec[]>(
    fis ? [cloneFis(fis)] : [],
  );
  const [historyIndex, setHistoryIndex] = useState(0);
  const [revisions, setRevisions] = useState<FISSpec[]>([]);
  const [selected, setSelected] = useState(0);
  const [runInputs, setRunInputs] = useState<Record<string, string>>({});
  const [lastOutput, setLastOutput] = useState<FISEvaluation | null>(evaluation);
  const [evaluatingFis, setEvaluatingFis] = useState(false);
  const fisEvaluationInFlightRef = useRef(false);
  const [fisEvaluationRecovery, setFisEvaluationRecovery] = useState<{ fisId: string; semanticHash: string; inputs: Record<string, number>; error: string; notFound: boolean } | null>(null);
  const [recoveringFisEvaluation, setRecoveringFisEvaluation] = useState(false);
  const [fisImportRecovery, setFisImportRecovery] = useState<{ source: string; submittedWorking: FISSpec | null; error: string } | null>(null);
  const [retryingFisImport, setRetryingFisImport] = useState(false);
  const [importingMatlabFis, setImportingMatlabFis] = useState(false);
  const importMatlabFisInFlightRef = useRef(false);
  const [fisSaveRecovery, setFisSaveRecovery] = useState<{ spec: FISSpec; error: string; notFound: boolean } | null>(null);
  const [recoveringFisSave, setRecoveringFisSave] = useState(false);
  const [expertRefitRecovery, setExpertRefitRecovery] = useState<{ fisId: string; sourceHash: string; sourceSpec: FISSpec; lockedRuleIds: string[]; sourceExplanationId: string | null; requestedAt: number; error: string; notFound: boolean } | null>(null);
  const [recoveringExpertRefit, setRecoveringExpertRefit] = useState(false);
  const expertCorrectionActionInFlightRef = useRef(false);
  const [surface, setSurface] = useState<ResponseSurface | null>(null);
  const [surfaceAxes, setSurfaceAxes] = useState<[string, string] | null>(null);
  const [surfaceLoading, setSurfaceLoading] = useState(false);
  const [surfaceError, setSurfaceError] = useState<string | null>(null);
  const responseSurfaceRequestRef = useRef(0);
  const [creatingDefaultFis, setCreatingDefaultFis] = useState(false);
  const createDefaultFisInFlightRef = useRef(false);
  const [savingFis, setSavingFis] = useState(false);
  const saveFisInFlightRef = useRef(false);
  const [fisActionBusy, setFisActionBusy] = useState(false);
  const fisActionInFlightRef = useRef(false);
  const [diagnostics, setDiagnostics] = useState<
    Array<{ code: string; severity: string; message: string }>
  >([]);
  const diagnosticsRequestRef = useRef(0);
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    workingRef.current = working;
  }, [working]);
  useEffect(() => {
    diagnosticsRequestRef.current += 1;
    setDiagnostics([]);
  }, [working]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setLastOutput(evaluation); }, [evaluation]);
  const [textRule, setTextRule] = useState("");
  const [ruleFilter, setRuleFilter] = useState("");
  const [compatibilityIssues, setCompatibilityIssues] = useState<
    FISCompatibilityIssue[]
  >([]);
  const [expertLockedRules, setExpertLockedRules] = useState<string[]>([]);
  const [expertCorrection, setExpertCorrection] = useState<ExpertCorrectionRevision | null>(null);
  const [expertCorrectionLoadStatus, setExpertCorrectionLoadStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [expertCorrectionLoadError, setExpertCorrectionLoadError] = useState<string | null>(null);
  const [expertCorrectionReload, setExpertCorrectionReload] = useState(0);
  const [linkSourceExplanation, setLinkSourceExplanation] = useState(false);
  const [canonicalYaml, setCanonicalYaml] = useState<string | null>(null);
  const [historyBaseHash, setHistoryBaseHash] = useState<string | null>(null);
  const [revisionHistoryStatus, setRevisionHistoryStatus] = useState<"idle" | "loading" | "empty" | "available" | "error">("idle");
  const [revisionHistoryError, setRevisionHistoryError] = useState<string | null>(null);
  const [revisionHistoryReload, setRevisionHistoryReload] = useState(0);
  const importInputRef = useRef<HTMLInputElement>(null);
  const preserveDraftOnHydrationFisIdRef = useRef<string | null>(null);
  const publishFisChange = onFisChange;
  const publishEvaluation = onEvaluation;
  const publishExpertCorrection = onExpertCorrection ?? (() => undefined);
  function beginFisAction(): boolean {
    if (fisActionInFlightRef.current) return false;
    fisActionInFlightRef.current = true;
    setFisActionBusy(true);
    return true;
  }
  function endFisAction(): void {
    fisActionInFlightRef.current = false;
    setFisActionBusy(false);
  }
  useEffect(() => {
    setLinkSourceExplanation(false);
  }, [sourceExplanationId]);
  useEffect(() => {
    let active = true;
    const nextFisIdentity = fis ? `${fis.fis_id}:${fis.semantic_hash ?? ""}` : null;
    const persistedModelChanged = hydratedProjectIdRef.current !== project.session_id ||
      hydratedFisIdentityRef.current !== nextFisIdentity;
    const currentWorking = workingRef.current;
    const preserveNewerDraft = Boolean(
      persistedModelChanged &&
      fis?.semantic_hash &&
      preserveDraftOnHydrationHashRef.current === fis.semantic_hash &&
      currentWorking &&
      !currentWorking.semantic_hash &&
      (currentWorking.fis_id === fis.fis_id || preserveDraftOnHydrationFisIdRef.current === currentWorking.fis_id),
    );
    if (persistedModelChanged) {
      hydratedProjectIdRef.current = project.session_id;
      hydratedFisIdentityRef.current = nextFisIdentity;
      if (preserveNewerDraft) {
        preserveDraftOnHydrationHashRef.current = null;
        preserveDraftOnHydrationFisIdRef.current = null;
      } else {
        setWorking(fis);
        setEditorHistory(fis ? [cloneFis(fis)] : []);
        setHistoryIndex(0);
      }
    }
    if (fis) {
      setRevisions([]);
      setRevisionHistoryError(null);
      setRevisionHistoryStatus("loading");
      studioApi.getFisRevisions(project.session_id).then((items) => {
        if (!active) return;
        setRevisions(items);
        setRevisionHistoryStatus(items.length ? "available" : "empty");
      }).catch((reason: unknown) => {
        if (!active) return;
        setRevisions([]);
        setRevisionHistoryError(reason instanceof Error ? reason.message : "Saved FIS revisions could not be verified.");
        setRevisionHistoryStatus("error");
      });
      if (fis.system_type === "sugeno") {
        setExpertCorrection(null);
        setExpertCorrectionLoadError(null);
        setExpertCorrectionLoadStatus("loading");
        const request = selectedExpertCorrectionId
          ? studioApi.getExpertCorrection(project.session_id, selectedExpertCorrectionId)
          : studioApi.getLatestExpertCorrection(project.session_id);
        request
          .then((correction) => {
            if (!active) return;
            setExpertCorrection(correction);
            setExpertCorrectionLoadStatus("available");
            publishExpertCorrection(correction);
          }).catch((reason: unknown) => {
            if (!active) return;
            setExpertCorrection(null);
            publishExpertCorrection(null);
            if (reason instanceof ProductApiError && reason.status === 404 && !selectedExpertCorrectionId) {
              setExpertCorrectionLoadStatus("none");
              return;
            }
            setExpertCorrectionLoadError(reason instanceof Error ? reason.message : "Saved expert correction could not be loaded.");
            setExpertCorrectionLoadStatus("error");
          });
      } else {
        setExpertCorrection(null);
        setExpertCorrectionLoadError(null);
        setExpertCorrectionLoadStatus("none");
        publishExpertCorrection(null);
      }
      setExpertLockedRules((current) => current.filter((id) => fis.rules.some((rule) => rule.rule_id === id)));
    } else {
      setRevisions([]);
      setRevisionHistoryError(null);
      setRevisionHistoryStatus("idle");
      setExpertCorrection(null);
      setExpertCorrectionLoadError(null);
      setExpertCorrectionLoadStatus("idle");
      publishExpertCorrection(null);
      setExpertLockedRules([]);
    }
    return () => { active = false; };
  }, [project.session_id, fis, selectedExpertCorrectionId, expertCorrectionReload, revisionHistoryReload]);
  useEffect(() => {
    if (!fis) {
      setRunInputs({});
      return;
    }
    setSelected(0);
    setRunInputs(
      Object.fromEntries(
        fis.inputs.map((v) => [v.name, String((v.minimum + v.maximum) / 2)]),
      ),
    );
  }, [fis?.fis_id]);
  useEffect(() => {
    if (!working || working.inputs.length < 2) {
      setSurfaceAxes(null);
      return;
    }
    setSurfaceAxes((current) =>
      current &&
      working.inputs.some((item) => item.name === current[0]) &&
      working.inputs.some((item) => item.name === current[1])
        ? current
        : [working.inputs[0].name, working.inputs[1].name],
    );
  }, [working?.fis_id, working?.inputs.map((item) => item.name).join("|")]);
  const selectedVariable = working?.inputs[selected] ?? null;
  const lastOutputMatchesCurrent = working
    ? exactFisEvaluationMatchesCurrent(working, lastOutput, runInputs)
    : false;
  const chart = useMemo(
    () => (selectedVariable ? membershipOption(selectedVariable) : null),
    [selectedVariable],
  );
  const historyBase = useMemo(
    () => revisions.find((revision) => revision.semantic_hash === historyBaseHash) ?? null,
    [revisions, historyBaseHash],
  );
  const historyChanges = useMemo(
    () => (historyBase && working ? fisSemanticDiff(historyBase, working) : []),
    [historyBase, working],
  );
  const correctionSource = useMemo(
    () => expertCorrection ? revisions.find((revision) => revision.semantic_hash === expertCorrection.source_semantic_hash) ?? null : null,
    [expertCorrection, revisions],
  );
  const correctionResult = useMemo(
    () => expertCorrection ? revisions.find((revision) => revision.semantic_hash === expertCorrection.result_semantic_hash) ?? null : null,
    [expertCorrection, revisions],
  );
  const correctionChanges = useMemo(
    () => correctionSource && correctionResult ? fisSemanticDiff(correctionSource, correctionResult) : [],
    [correctionSource, correctionResult],
  );
  const mutate = (edit: (next: FISSpec) => void) => {
    if (!working) return;
    const next = cloneFis(working);
    edit(next);
    next.semantic_hash = null;
    workingRef.current = next;
    setWorking(next);
    const nextHistory = [
      ...editorHistory.slice(0, historyIndex + 1),
      cloneFis(next),
    ];
    setEditorHistory(nextHistory);
    setHistoryIndex(nextHistory.length - 1);
  };
  function adoptPersistedFisUnlessDraftChanged(result: FISSpec, baseline: FISSpec): boolean {
    const latestWorking = workingRef.current;
    const newerDraftExists = Boolean(latestWorking && (
      latestWorking.fis_id !== baseline.fis_id ||
      canonicalJson(fisSemanticPayload(latestWorking)) !== canonicalJson(fisSemanticPayload(baseline))
    ));
    if (newerDraftExists) {
      if (result.semantic_hash) {
        preserveDraftOnHydrationHashRef.current = result.semantic_hash;
        preserveDraftOnHydrationFisIdRef.current = latestWorking?.fis_id ?? null;
      }
      return true;
    }
    workingRef.current = result;
    setWorking(result);
    return false;
  }
  function undo() {
    if (historyIndex <= 0) return;
    const prior = cloneFis(editorHistory[historyIndex - 1]);
    setHistoryIndex(historyIndex - 1);
    setWorking(prior);
  }
  function redo() {
    if (historyIndex >= editorHistory.length - 1) return;
    const next = cloneFis(editorHistory[historyIndex + 1]);
    setHistoryIndex(historyIndex + 1);
    setWorking(next);
  }
  async function createDefault() {
    if (fisImportRecovery || createDefaultFisInFlightRef.current || !beginFisAction()) return;
    setError(null);
    createDefaultFisInFlightRef.current = true;
    setCreatingDefaultFis(true);
    try {
      const created = await studioApi.createDefaultFis(project.session_id);
      setWorking(created);
      publishFisChange(created);
      setMessage("Canonical FIS created from the confirmed dataset.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "FIS creation failed",
      );
    } finally {
      createDefaultFisInFlightRef.current = false;
      setCreatingDefaultFis(false);
      endFisAction();
    }
  }
  async function importMatlabFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || fisImportRecovery) return;
    const submittedWorking = workingRef.current ? cloneFis(workingRef.current) : null;
    await submitMatlabImport(await file.text(), submittedWorking);
  }
  async function submitMatlabImport(source: string, submittedWorking: FISSpec | null) {
    if (importMatlabFisInFlightRef.current || !beginFisAction()) return;
    importMatlabFisInFlightRef.current = true;
    setImportingMatlabFis(true);
    setError(null);
    try {
      const result = await studioApi.importMatlabFis(project.session_id, source);
      setCompatibilityIssues(result.issues);
      if (!result.spec) {
        setMessage("Import blocked: inspect the compatibility report.");
        setFisImportRecovery(null);
        return;
      }
      const latestWorking = workingRef.current;
      const newerDraftExists = canonicalJson(latestWorking) !== canonicalJson(submittedWorking);
      if (newerDraftExists) {
        const importedIdentityWillHydrate = fis?.fis_id !== result.spec.fis_id || fis?.semantic_hash !== result.spec.semantic_hash;
        if (result.spec.semantic_hash && importedIdentityWillHydrate) {
          preserveDraftOnHydrationHashRef.current = result.spec.semantic_hash;
          preserveDraftOnHydrationFisIdRef.current = latestWorking?.fis_id ?? null;
        }
      } else {
        setWorking(result.spec);
      }
      publishFisChange(result.spec);
      setMessage(newerDraftExists
        ? `MATLAB FIS import was persisted; newer editor changes remain unsaved. Save again to activate your draft${result.source_artifact_sha256 ? ` · source artifact ${result.source_artifact_sha256.slice(0, 12)}` : ""}.`
        : `MATLAB FIS imported as a canonical executable model${result.source_artifact_sha256 ? ` · source artifact ${result.source_artifact_sha256.slice(0, 12)}` : ""}.`);
      setFisImportRecovery(null);
    } catch (reason) {
      setFisImportRecovery({ source, submittedWorking, error: reason instanceof Error ? reason.message : "Import response was uncertain." });
      setError(
        reason instanceof Error ? reason.message : "MATLAB FIS import failed",
      );
    } finally {
      importMatlabFisInFlightRef.current = false;
      setImportingMatlabFis(false);
      endFisAction();
    }
  }
  async function retrySameMatlabImport() {
    if (!fisImportRecovery) return;
    setRetryingFisImport(true);
    try { await submitMatlabImport(fisImportRecovery.source, fisImportRecovery.submittedWorking); }
    finally { setRetryingFisImport(false); }
  }
  async function exportMatlabFile() {
    setError(null);
    if (!working?.semantic_hash) {
      setError("Save this FIS revision before exporting; MATLAB export uses the active persisted model. No export was created.");
      return;
    }
    try {
      const source = await studioApi.exportMatlabFis(project.session_id);
      const url = URL.createObjectURL(new Blob([source], { type: "text/plain" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${working?.name ?? "ruflex"}.fis`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("MATLAB-compatible FIS export downloaded.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "MATLAB FIS export failed");
    }
  }
  function addVariable() {
    if (!working) return;
    const n = working.inputs.length + 1;
    mutate((next) => {
      next.inputs.push({
        name: `Input ${n}`,
        minimum: 0,
        maximum: 1,
        terms: [
          { name: "Low", kind: "triangular", parameters: [0, 0, 0.5] },
          { name: "High", kind: "triangular", parameters: [0.5, 1, 1] },
        ],
        role: "input",
        dataset_feature: null,
        units: null,
        locked: false,
      });
    });
    setSelected(working.inputs.length);
  }
  function duplicateVariable() {
    if (!working || !selectedVariable) return;
    mutate((next) => {
      const original = next.inputs[selected];
      const copyName = `${original.name} copy`;
      next.inputs.splice(selected + 1, 0, {
        ...structuredClone(original),
        name: copyName,
        dataset_feature: null,
      });
    });
    setSelected(selected + 1);
  }
  function moveVariable(direction: -1 | 1) {
    if (!working) return;
    const target = selected + direction;
    if (target < 0 || target >= working.inputs.length) return;
    mutate((next) => {
      [next.inputs[selected], next.inputs[target]] = [
        next.inputs[target],
        next.inputs[selected],
      ];
    });
    setSelected(target);
  }
  async function resetSelectedRangeFromDataset() {
    if (!working || !selectedVariable?.dataset_feature) {
      setError("Map this input to a numeric DatasetContract feature first.");
      return;
    }
    const requestedSpec = cloneFis(working);
    const requestedInputIndex = selected;
    const requestedFeature = selectedVariable.dataset_feature;
    setError(null);
    try {
      const range = await studioApi.getDatasetFeatureRange(
        project.session_id,
        requestedFeature,
      );
      const latestWorking = workingRef.current;
      const requestedVariable = latestWorking?.inputs[requestedInputIndex];
      if (!latestWorking ||
        latestWorking.fis_id !== requestedSpec.fis_id ||
        canonicalJson(fisSemanticPayload(latestWorking)) !== canonicalJson(fisSemanticPayload(requestedSpec)) ||
        requestedVariable?.dataset_feature !== requestedFeature) {
        setError("The FIS or feature mapping changed while the DatasetContract range was loading. No range was applied; retry against the current draft.");
        return;
      }
      mutate((next) => {
        const variable = next.inputs[requestedInputIndex];
        const oldMinimum = variable.minimum;
        const oldMaximum = variable.maximum;
        variable.minimum = range.minimum;
        variable.maximum = range.maximum;
        variable.terms.forEach((term) => {
          term.parameters = rescaleTerm(
            term,
            oldMinimum,
            oldMaximum,
            range.minimum,
            range.maximum,
          );
        });
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Range reset failed");
    }
  }
  function removeVariable() {
    if (!working || !selectedVariable) return;
    const used = working.rules.filter((r) =>
      r.clauses.some((c) => c.variable === selectedVariable.name),
    ).length;
    if (
      used &&
      !window.confirm(
        `${selectedVariable.name} is used by ${used} rule(s). Remove and repair those rules?`,
      )
    )
      return;
    mutate((next) => {
      const removed = next.inputs[selected].name;
      next.inputs.splice(selected, 1);
      next.rules = next.rules.filter(
        (r) => !r.clauses.some((c) => c.variable === removed),
      );
      if (!next.rules.length) {
        const fallback = next.inputs[0];
        if (fallback) {
          const outputTerm = next.output.terms[0].name;
          next.rules.push({
            rule_id: crypto.randomUUID(),
            name: "Default rule",
            clauses: [
              { variable: fallback.name, term: fallback.terms[0].name },
            ],
            connector: "and",
            output_term: outputTerm,
            weight: 1,
            enabled: true,
            sugeno_consequent:
              next.system_type === "sugeno"
                ? {
                    kind: "constant",
                    constant: outputCenter(next.output, outputTerm),
                    coefficients: {},
                    intercept: 0,
                  }
                : null,
          });
        }
      }
    });
    setSelected(Math.max(0, selected - 1));
  }
  function addTerm() {
    if (!selectedVariable) return;
    mutate((next) => {
      const variable = next.inputs[selected];
      variable.terms.push({
        name: `Term ${variable.terms.length + 1}`,
        kind: "triangular",
        parameters: defaultParameters(
          "triangular",
          variable.minimum,
          variable.maximum,
        ),
      });
    });
  }
  function duplicateTerm(index: number) {
    mutate((next) => {
      const variable = next.inputs[selected];
      const original = variable.terms[index];
      variable.terms.splice(index + 1, 0, {
        ...structuredClone(original),
        name: `${original.name} copy`,
      });
    });
  }
  function moveTerm(index: number, direction: -1 | 1) {
    mutate((next) => {
      const terms = next.inputs[selected].terms;
      const target = index + direction;
      if (target < 0 || target >= terms.length) return;
      [terms[index], terms[target]] = [terms[target], terms[index]];
    });
  }
  function addOutputTerm() {
    if (!working) return;
    mutate((next) => {
      const output = next.output;
      output.terms.push({ name: `Term ${output.terms.length + 1}`, kind: "triangular", parameters: defaultParameters("triangular", output.minimum, output.maximum) });
    });
  }
  function duplicateOutputTerm(index: number) {
    mutate((next) => {
      const original = next.output.terms[index];
      next.output.terms.splice(index + 1, 0, { ...structuredClone(original), name: `${original.name} copy` });
    });
  }
  function duplicateRule(index: number) {
    mutate((next) => {
      const original = next.rules[index];
      next.rules.splice(index + 1, 0, {
        ...structuredClone(original),
        rule_id: crypto.randomUUID(),
        name: `${original.name} copy`,
      });
    });
  }
  function moveRule(index: number, direction: -1 | 1) {
    mutate((next) => {
      const target = index + direction;
      if (target < 0 || target >= next.rules.length) return;
      [next.rules[index], next.rules[target]] = [
        next.rules[target],
        next.rules[index],
      ];
    });
  }
  function addRule() {
    if (!working) return;
    mutate((next) => {
      const outputTerm = next.output.terms[0].name;
      next.rules.push({
        rule_id: crypto.randomUUID(),
        name: `Rule ${next.rules.length + 1}`,
        clauses: next.inputs.map((v) => ({
          variable: v.name,
          term: v.terms[0].name,
        })),
        connector: "and",
        output_term: outputTerm,
        weight: 1,
        enabled: true,
        sugeno_consequent:
          next.system_type === "sugeno"
            ? {
                kind: "constant",
                constant: outputCenter(next.output, outputTerm),
                coefficients: {},
                intercept: 0,
              }
            : null,
      });
    });
  }
  function setSystemType(systemType: FISSpec["system_type"]) {
    if (!working) return;
    mutate((next) => {
      next.system_type = systemType;
      next.rules.forEach((rule) => {
        rule.sugeno_consequent =
          systemType === "sugeno"
            ? {
                kind: "constant",
                constant: outputCenter(next.output, rule.output_term),
                coefficients: {},
                intercept: 0,
              }
            : null;
      });
    });
  }
  function addTextRule() {
    if (!working) return;
    const match =
      /^IF\s+(.+)\s+THEN\s+(.+)\s+IS\s+(.+?)(?:\s+WITH\s+([\d.]+))?$/i.exec(
        textRule.trim(),
      );
    if (!match) {
      setError(
        "Use: IF Temperature IS High AND Torque IS Low THEN target_score IS High WITH 0.95",
      );
      return;
    }
    const antecedent = match[1];
    const connector = /\s+OR\s+/i.test(antecedent) ? "or" : "and";
    const parts = antecedent.split(/\s+(?:AND|OR)\s+/i);
    const clauses = parts.map((part) => {
      const m = /^(.+?)\s+IS\s+(.+)$/i.exec(part.trim());
      return m ? { variable: m[1].trim(), term: m[2].trim() } : null;
    });
    const validClauses = clauses.every((clause) => {
      if (!clause) return false;
      const variable = working.inputs.find(
        (item) => item.name === clause.variable,
      );
      return Boolean(variable?.terms.some((term) => term.name === clause.term));
    });
    if (
      !validClauses ||
      !working.output.terms.some((t) => t.name === match[3].trim())
    ) {
      setError(
        "The rule must reference existing input variables, terms, and an output term.",
      );
      return;
    }
    mutate((next) => {
      const outputTerm = match[3].trim();
      next.rules.push({
        rule_id: crypto.randomUUID(),
        name: `Rule ${next.rules.length + 1}`,
        clauses: clauses as FuzzyRule["clauses"],
        connector,
        output_term: outputTerm,
        weight: Math.max(0, Math.min(1, Number(match[4] ?? 1))),
        enabled: true,
        sugeno_consequent:
          next.system_type === "sugeno"
            ? {
                kind: "constant",
                constant: outputCenter(next.output, outputTerm),
                coefficients: {},
                intercept: 0,
              }
            : null,
      });
    });
    setTextRule("");
  }
  function openHistoricalRevision(revision: FISSpec) {
    const historical = cloneFis(revision);
    setWorking(historical);
    setEditorHistory([cloneFis(historical)]);
    setHistoryIndex(0);
    setHistoryBaseHash(revision.semantic_hash);
    setMessage(`Historical revision ${revision.semantic_hash?.slice(0, 16) ?? revision.fis_id.slice(0, 8)} opened as an editable working copy. Save FIS to make it active again.`);
    setError(null);
  }

  async function loadCanonicalYaml() {
    setError(null);
    try {
      setCanonicalYaml(await studioApi.getCanonicalFisYaml(project.session_id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Canonical YAML could not be loaded");
    }
  }

  async function save() {
    if (!working || fisSaveRecovery || fisImportRecovery || saveFisInFlightRef.current || !beginFisAction()) return;
    setError(null);
    const requestedSpec = cloneFis(working);
    saveFisInFlightRef.current = true;
    setSavingFis(true);
    try {
      const saved = await studioApi.saveFis(project.session_id, requestedSpec);
      const latestWorking = workingRef.current;
      const newerDraftExists = Boolean(
        latestWorking &&
        canonicalJson(latestWorking) !== canonicalJson(requestedSpec),
      );
      if (!newerDraftExists) {
        setWorking(saved);
        setEditorHistory((history) => [
          ...history.slice(0, historyIndex + 1),
          cloneFis(saved),
        ]);
        setHistoryIndex((index) => index + 1);
      } else if (saved.semantic_hash) {
        preserveDraftOnHydrationHashRef.current = saved.semantic_hash;
      }
      setRevisions(await studioApi.getFisRevisions(project.session_id));
      publishFisChange(saved);
      setMessage(newerDraftExists
        ? "The submitted FIS revision was saved; newer editor changes remain unsaved. Save again to make them active."
        : "Canonical executable FIS saved with a semantic hash.");
      setFisSaveRecovery(null);
    } catch (reason) {
      setFisSaveRecovery({ spec: requestedSpec, error: reason instanceof Error ? reason.message : "FIS save response was uncertain.", notFound: false });
      setError(reason instanceof Error ? reason.message : "FIS save failed");
    } finally {
      saveFisInFlightRef.current = false;
      setSavingFis(false);
      endFisAction();
    }
  }
  async function recoverFisSave() {
    if (saveFisInFlightRef.current) return;
    const pending = fisSaveRecovery;
    if (!pending || !beginFisAction()) return;
    saveFisInFlightRef.current = true;
    setRecoveringFisSave(true); setError(null);
    try {
      const active = await studioApi.getActiveFis(project.session_id);
      if (active.fis_id === pending.spec.fis_id && canonicalJson(fisSemanticPayload(active)) === canonicalJson(fisSemanticPayload(pending.spec))) {
        setRevisions(await studioApi.getFisRevisions(project.session_id));
        if (working && canonicalJson(fisSemanticPayload(working)) === canonicalJson(fisSemanticPayload(pending.spec))) setWorking(active);
        publishFisChange(active); setMessage("Recovered the exact saved FIS revision after the response was lost."); setFisSaveRecovery(null);
      } else {
        setFisSaveRecovery({ ...pending, notFound: true, error: "The active FIS is not the exact saved revision. You may retry only if the working copy is still unchanged." });
      }
    } catch (reason) {
      setFisSaveRecovery({ ...pending, notFound: false, error: reason instanceof Error ? reason.message : "The saved FIS revision could not be verified." });
    } finally { saveFisInFlightRef.current = false; setRecoveringFisSave(false); endFisAction(); }
  }
  async function explicitlyRepeatFisSave() {
    if (saveFisInFlightRef.current) return;
    const pending = fisSaveRecovery;
    if (!pending?.notFound || !working || project.read_only || canonicalJson(fisSemanticPayload(working)) !== canonicalJson(fisSemanticPayload(pending.spec)) || !beginFisAction()) return;
    saveFisInFlightRef.current = true;
    setRecoveringFisSave(true); setError(null);
    try {
      const saved = await studioApi.saveFis(project.session_id, pending.spec);
      const latestWorking = workingRef.current;
      const newerDraftExists = Boolean(latestWorking && canonicalJson(fisSemanticPayload(latestWorking)) !== canonicalJson(fisSemanticPayload(pending.spec)));
      if (!newerDraftExists) setWorking(saved);
      else if (saved.semantic_hash) preserveDraftOnHydrationHashRef.current = saved.semantic_hash;
      setRevisions(await studioApi.getFisRevisions(project.session_id)); publishFisChange(saved);
      setMessage(newerDraftExists
        ? "The exact FIS snapshot was safely repeated; newer editor changes remain unsaved. Save again to make them active."
        : "The exact FIS save was safely repeated and resolved to its persisted semantic revision.");
      setFisSaveRecovery(null);
    } catch (reason) {
      setFisSaveRecovery({ ...pending, notFound: false, error: reason instanceof Error ? reason.message : "The explicitly repeated FIS save response was uncertain." });
    } finally { saveFisInFlightRef.current = false; setRecoveringFisSave(false); endFisAction(); }
  }
  function restorePendingFisSaveSnapshot() {
    if (fisActionInFlightRef.current || saveFisInFlightRef.current || !fisSaveRecovery) return;
    const restored = cloneFis(fisSaveRecovery.spec);
    setWorking(restored); setEditorHistory([cloneFis(restored)]); setHistoryIndex(0);
    setMessage("Restored the exact FIS snapshot from the uncertain save; verify its persisted identity before retrying.");
  }
  async function refitExpertConsequents() {
    if (expertCorrectionActionInFlightRef.current || !working || working.system_type !== "sugeno" || expertRefitRecovery || !beginFisAction()) return;
    expertCorrectionActionInFlightRef.current = true;
    setRecoveringExpertRefit(true);
    setError(null);
    setMessage(null);
    try {
      const source = cloneFis(working);
      const lockedRuleIds = [...expertLockedRules].sort();
      const sourceExplanation = linkSourceExplanation ? sourceExplanationId ?? null : null;
      let saved: FISSpec;
      try {
        // Persist the user's current expert edits first so the correction is fitted
        // from exactly the visible canonical FIS revision.
        saved = await studioApi.saveFis(project.session_id, source);
        adoptPersistedFisUnlessDraftChanged(saved, source);
      } catch (reason) {
        setFisSaveRecovery({ spec: source, error: reason instanceof Error ? reason.message : "Source FIS save response was uncertain.", notFound: false });
        setError(reason instanceof Error ? reason.message : "Source FIS save failed");
        return;
      }
      const requestedAt = Date.now();
      try {
        const result = await studioApi.refitSugenoConsequents(
          project.session_id,
          lockedRuleIds,
          sourceExplanation,
        );
        const newerDraftExists = adoptPersistedFisUnlessDraftChanged(result.fis, saved);
        if (!newerDraftExists) {
          setEditorHistory((history) => [...history.slice(0, historyIndex + 1), cloneFis(result.fis)]);
          setHistoryIndex((index) => index + 1);
        }
        setExpertCorrection(result.correction);
        setExpertCorrectionLoadStatus("available");
        setExpertCorrectionLoadError(null);
        publishExpertCorrection(result.correction);
        setRevisions(await studioApi.getFisRevisions(project.session_id));
        publishFisChange(result.fis);
        setExpertRefitRecovery(null);
        setMessage(newerDraftExists
          ? `TRAIN-only expert correction was persisted for its frozen source; newer editor changes remain unsaved. Save again to activate your draft. Final test stayed locked.`
          : `TRAIN-only expert correction fitted ${result.correction.fitted_rule_ids.length} rule consequent(s): RMSE ${result.correction.train_rmse_before.toFixed(4)} → ${result.correction.train_rmse_after.toFixed(4)}. Final test stayed locked.`);
      } catch (reason) {
        if (saved.semantic_hash) setExpertRefitRecovery({ fisId: saved.fis_id, sourceHash: saved.semantic_hash, sourceSpec: saved, lockedRuleIds, sourceExplanationId: sourceExplanation, requestedAt, error: reason instanceof Error ? reason.message : "Expert correction response was uncertain.", notFound: false });
        setError(reason instanceof Error ? reason.message : "Expert correction failed");
      }
    } finally {
      expertCorrectionActionInFlightRef.current = false;
      setRecoveringExpertRefit(false);
      endFisAction();
    }
  }
  async function recoverExpertRefit() {
    if (expertCorrectionActionInFlightRef.current) return;
    const pending = expertRefitRecovery;
    if (!pending || !beginFisAction()) return;
    expertCorrectionActionInFlightRef.current = true;
    setRecoveringExpertRefit(true);
    try {
      const [correction, active] = await Promise.all([studioApi.getLatestExpertCorrection(project.session_id), studioApi.getActiveFis(project.session_id)]);
      const locked = [...correction.locked_rule_ids].sort();
      const createdAt = Date.parse(correction.created_at);
      const exact = correction.fis_id === pending.fisId && correction.source_semantic_hash === pending.sourceHash && correction.source_explanation_id === pending.sourceExplanationId && canonicalJson(locked) === canonicalJson(pending.lockedRuleIds) && Number.isFinite(createdAt) && createdAt >= pending.requestedAt - 10_000 && active.fis_id === pending.fisId && active.semantic_hash === correction.result_semantic_hash;
      if (exact) {
        const newerDraftExists = adoptPersistedFisUnlessDraftChanged(active, pending.sourceSpec);
        if (!newerDraftExists) {
          setWorking(active); setEditorHistory((history) => [...history.slice(0, historyIndex + 1), cloneFis(active)]); setHistoryIndex((index) => index + 1);
        }
        setExpertCorrection(correction); setExpertCorrectionLoadStatus("available"); setExpertCorrectionLoadError(null); publishExpertCorrection(correction);
        setRevisions(await studioApi.getFisRevisions(project.session_id)); publishFisChange(active); setMessage(newerDraftExists ? "Recovered the exact TRAIN-only expert correction; newer editor changes remain unsaved. Save again to activate your draft." : "Recovered the exact TRAIN-only expert correction after the response was lost."); setExpertRefitRecovery(null);
      } else {
        const safeToRetry = active.fis_id === pending.fisId && active.semantic_hash === pending.sourceHash;
        setExpertRefitRecovery({ ...pending, notFound: safeToRetry, error: safeToRetry ? "No matching correction is persisted and the original FIS is still active; an explicit exact retry is safe." : "Persisted FIS state changed, but no matching correction receipt was found. Refusing to fit again." });
      }
    } catch (reason) {
      const noPriorCorrection = reason instanceof ProductApiError && reason.status === 404;
      try {
        const active = await studioApi.getActiveFis(project.session_id);
        const safeToRetry = noPriorCorrection && active.fis_id === pending.fisId && active.semantic_hash === pending.sourceHash;
        setExpertRefitRecovery({ ...pending, notFound: safeToRetry, error: safeToRetry ? "No correction receipt exists and the original FIS is still active; an explicit exact retry is safe." : reason instanceof Error ? reason.message : "Could not verify the persisted expert correction." });
      } catch (activeError) {
        setExpertRefitRecovery({ ...pending, notFound: false, error: activeError instanceof Error ? activeError.message : "Could not verify the active FIS after the uncertain correction." });
      }
    } finally { expertCorrectionActionInFlightRef.current = false; setRecoveringExpertRefit(false); endFisAction(); }
  }
  async function retryExpertRefit() {
    if (expertCorrectionActionInFlightRef.current) return;
    const pending = expertRefitRecovery;
    if (!pending?.notFound || project.read_only || !beginFisAction()) return;
    expertCorrectionActionInFlightRef.current = true;
    setRecoveringExpertRefit(true);
    try {
      const active = await studioApi.getActiveFis(project.session_id);
      if (active.fis_id !== pending.fisId || active.semantic_hash !== pending.sourceHash) {
        setExpertRefitRecovery({ ...pending, notFound: false, error: "The original source FIS is no longer active; refusing to run the correction against a different revision." });
        return;
      }
      const result = await studioApi.refitSugenoConsequents(project.session_id, pending.lockedRuleIds, pending.sourceExplanationId);
      const newerDraftExists = adoptPersistedFisUnlessDraftChanged(result.fis, pending.sourceSpec);
      if (!newerDraftExists) {
        setWorking(result.fis); setEditorHistory((history) => [...history.slice(0, historyIndex + 1), cloneFis(result.fis)]); setHistoryIndex((index) => index + 1);
      }
      setExpertCorrection(result.correction); setExpertCorrectionLoadStatus("available"); setExpertCorrectionLoadError(null); publishExpertCorrection(result.correction);
      setRevisions(await studioApi.getFisRevisions(project.session_id)); publishFisChange(result.fis); setMessage(newerDraftExists ? "The exact TRAIN-only expert correction retry completed; newer editor changes remain unsaved. Save again to activate your draft." : "The exact TRAIN-only expert correction retry completed."); setExpertRefitRecovery(null);
    } catch (reason) {
      setExpertRefitRecovery({ ...pending, notFound: false, error: reason instanceof Error ? reason.message : "The explicit exact correction retry was uncertain." });
    } finally { expertCorrectionActionInFlightRef.current = false; setRecoveringExpertRefit(false); endFisAction(); }
  }

  async function run() {
    if (!working || fisEvaluationRecovery || fisEvaluationInFlightRef.current || fisActionInFlightRef.current) return;
    setError(null);
    if (!working.semantic_hash) {
      setError("Save this FIS revision before evaluating; inference uses the active persisted model. No inference was submitted.");
      return;
    }
    const parsed = parseFisRunInputs(working.inputs.map((variable) => variable.name), runInputs);
    if (!parsed.ok) {
      setError(`Enter a finite number for each model input. Invalid: ${parsed.invalidInputs.join(", ")}. No inference was submitted.`);
      return;
    }
    const inputs = parsed.values;
    if (!beginFisAction()) return;
    fisEvaluationInFlightRef.current = true;
    setEvaluatingFis(true);
    try {
      const evaluation = await studioApi.evaluateFis(project.session_id, inputs, !project.read_only);
      setLastOutput(evaluation);
      publishEvaluation(evaluation);
      setMessage("Exact fuzzy computation trace generated.");
      setFisEvaluationRecovery(null);
    } catch (reason) {
      if (!project.read_only) setFisEvaluationRecovery({ fisId: working.fis_id, semanticHash: working.semantic_hash ?? "", inputs, error: reason instanceof Error ? reason.message : "FIS evaluation response was uncertain.", notFound: false });
      setError(
        reason instanceof Error ? reason.message : "FIS evaluation failed",
      );
    } finally {
      fisEvaluationInFlightRef.current = false;
      setEvaluatingFis(false);
      endFisAction();
    }
  }
  async function recoverFisEvaluation() {
    if (fisEvaluationInFlightRef.current) return;
    const pending = fisEvaluationRecovery;
    if (!pending || !beginFisAction()) return;
    fisEvaluationInFlightRef.current = true;
    setRecoveringFisEvaluation(true); setError(null);
    try {
      const latest = await studioApi.getLatestFisTrace(project.session_id);
      const trace = latest.evaluation.trace;
      if (trace.fis_id !== pending.fisId || trace.semantic_hash !== pending.semanticHash || canonicalJson(trace.input_values) !== canonicalJson(pending.inputs)) {
        setFisEvaluationRecovery({ ...pending, notFound: true, error: "The latest persisted FIS trace belongs to another model revision or input sample; no replacement was created." });
        return;
      }
      setLastOutput(latest); publishEvaluation(latest); setFisEvaluationRecovery(null); setMessage("Exact fuzzy computation trace restored from persisted evidence.");
    } catch (reason) {
      if (reason instanceof ProductApiError && reason.status === 404) {
        setFisEvaluationRecovery({ ...pending, notFound: true, error: "No matching persisted FIS trace is visible yet. Retry lookup later, or explicitly repeat this exact inference if the original did not finish." });
      } else {
        const message = reason instanceof Error ? reason.message : "Could not recover the exact FIS trace.";
        setFisEvaluationRecovery({ ...pending, notFound: false, error: message }); setError(message);
      }
    } finally { fisEvaluationInFlightRef.current = false; setRecoveringFisEvaluation(false); endFisAction(); }
  }
  async function explicitlyRepeatFisEvaluation() {
    if (fisEvaluationInFlightRef.current) return;
    const pending = fisEvaluationRecovery;
    if (!pending?.notFound || working?.fis_id !== pending.fisId || working.semantic_hash !== pending.semanticHash || !beginFisAction()) return;
    fisEvaluationInFlightRef.current = true;
    setRecoveringFisEvaluation(true); setError(null);
    try {
      const evaluation = await studioApi.evaluateFis(project.session_id, pending.inputs, true);
      setLastOutput(evaluation); publishEvaluation(evaluation); setFisEvaluationRecovery(null); setMessage("Exact fuzzy computation trace generated.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The explicitly repeated FIS inference could not be confirmed.";
      setFisEvaluationRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { fisEvaluationInFlightRef.current = false; setRecoveringFisEvaluation(false); endFisAction(); }
  }
  async function refreshSurface() {
    if (!working || !surfaceAxes) return;
    const requestId = ++responseSurfaceRequestRef.current;
    const requestedSpec = working;
    const requestedAxes = surfaceAxes;
    setSurface(null);
    setSurfaceLoading(true);
    setSurfaceError(null);
    try {
      const fixedVariables = requestedSpec.inputs.filter(
        (variable) => !requestedAxes.includes(variable.name),
      );
      const fixedInputDraft = Object.fromEntries(fixedVariables.map((variable) => [
        variable.name,
        runInputs[variable.name] ?? String((variable.minimum + variable.maximum) / 2),
      ]));
      const parsedFixedInputs = parseFisRunInputs(fixedVariables.map((variable) => variable.name), fixedInputDraft);
      if (!parsedFixedInputs.ok) {
        setSurfaceError(`Enter a finite number for each fixed surface input. Invalid: ${parsedFixedInputs.invalidInputs.join(", ")}. No surface request was submitted.`);
        return;
      }
      const result = await studioApi.previewResponseSurface(
        project.session_id,
        requestedSpec,
        requestedAxes[0],
        requestedAxes[1],
        parsedFixedInputs.values,
      );
      if (requestId !== responseSurfaceRequestRef.current) return;
      setSurface(result);
    } catch (reason) {
      if (requestId !== responseSurfaceRequestRef.current) return;
      setSurfaceError(reason instanceof Error ? reason.message : "Response surface evaluation failed");
    } finally {
      if (requestId === responseSurfaceRequestRef.current) setSurfaceLoading(false);
    }
  }
  async function refreshDiagnostics() {
    if (!working) return;
    const requestId = ++diagnosticsRequestRef.current;
    const requestedSpec = working;
    setError(null);
    try {
      const result = await studioApi.diagnoseFis(project.session_id, requestedSpec);
      if (requestId !== diagnosticsRequestRef.current) return;
      setDiagnostics(result);
    } catch (reason) {
      if (requestId !== diagnosticsRequestRef.current) return;
      setError(reason instanceof Error ? reason.message : "FIS diagnostics failed");
    }
  }
  useEffect(() => {
    if (!working || !surfaceAxes || working.inputs.length < 2) {
      responseSurfaceRequestRef.current += 1;
      setSurface(null);
      setSurfaceLoading(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshSurface();
    }, 250);
    return () => {
      window.clearTimeout(timer);
      responseSurfaceRequestRef.current += 1;
    };
  }, [working, surfaceAxes, runInputs]);
  if (!working)
    return (
      <section className="feature-workspace">
        <EmptyState title="No FIS model">
          Confirm a dataset, then create the first editable fuzzy model.
        </EmptyState>
        <div className="form-actions">
          <Button
            view="action"
            disabled={project.read_only || !!fisImportRecovery || creatingDefaultFis || fisActionBusy}
            onClick={createDefault}
            data-ruflex-action="fis.create"
          >
            {creatingDefaultFis ? "Creating FIS…" : "Create FIS from dataset"}
          </Button>
          <input
            ref={importInputRef}
            aria-label="MATLAB FIS file"
            type="file"
            accept=".fis,text/plain"
            hidden
            onChange={importMatlabFile}
          />
          <Button
            view="outlined"
            disabled={project.read_only || !!fisImportRecovery || importingMatlabFis || fisActionBusy}
            onClick={() => importInputRef.current?.click()}
            data-ruflex-action="fis.import"
          >
            {importingMatlabFis ? "Importing MATLAB FIS…" : "Import MATLAB .fis"}
          </Button>
        </div>
        {fisImportRecovery && <div className="error" role="alert" data-testid="fis-import-recovery"><strong>MATLAB FIS import response is uncertain.</strong><p>{fisImportRecovery.error} The exact source is retained; retrying it will not create a duplicate imported revision.</p><Button view="outlined" disabled={retryingFisImport || importingMatlabFis || fisActionBusy} onClick={retrySameMatlabImport}>Retry exact MATLAB FIS import</Button></div>}
        {compatibilityIssues.length > 0 && (
          <section className="compatibility-report">
            <span className="eyebrow">MATLAB FIS COMPATIBILITY</span>
            {compatibilityIssues.map((issue, index) => (
              <p key={`${issue.source_construct}-${index}`}>
                <strong>{issue.status}</strong> {issue.source_construct}: {issue.semantic_consequence}
              </p>
            ))}
          </section>
        )}
        {message && <div className="info-message">{message}</div>}
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </section>
    );
  const duplicateRules = working.rules.filter(
    (rule, index) =>
      working.rules.findIndex(
        (other) =>
          ruleText(other, working.output) === ruleText(rule, working.output),
      ) !== index,
  ).length;
  const visibleRules = working.rules
    .map((rule, index) => ({ rule, index }))
    .filter(({ rule }) =>
      ruleText(rule, working.output)
        .toLowerCase()
        .includes(ruleFilter.trim().toLowerCase()),
    );
  return (
    <section className="feature-workspace fis-workspace">
      <div className="feature-toolbar">
        <div>
          <span className="eyebrow">CANONICAL FUZZY DESIGNER</span>
          <h2>{working.name}</h2>
          <p className="mono">
            {working.semantic_hash?.slice(0, 16)} · {working.system_type} ·
            executable model
          </p>
        </div>
        <div className="form-actions">
          <Button
            view="outlined"
            disabled={project.read_only || historyIndex === 0}
            onClick={undo}
          >
            Undo
          </Button>
          <Button
            view="outlined"
            disabled={
              project.read_only || historyIndex >= editorHistory.length - 1
            }
            onClick={redo}
          >
            Redo
          </Button>
          <label>
            FIS family{" "}
            <select
              aria-label="FIS family"
              value={working.system_type}
              disabled={project.read_only}
              onChange={(event) =>
                setSystemType(event.target.value as FISSpec["system_type"])
              }
            >
              <option value="mamdani">Mamdani</option>
              <option value="sugeno">Type-1 Sugeno</option>
            </select>
          </label>
          <Button view="outlined" disabled={project.read_only || !!fisImportRecovery || !!fisSaveRecovery || savingFis || recoveringFisSave || fisActionBusy} onClick={save} data-ruflex-action="fis.save_revision">
            {savingFis ? "Saving FIS…" : recoveringFisSave ? "Resolving FIS save…" : "Save FIS"}
          </Button>
          <input
            ref={importInputRef}
            aria-label="MATLAB FIS file"
            type="file"
            accept=".fis,text/plain"
            hidden
            onChange={importMatlabFile}
          />
          <Button
            view="outlined"
            disabled={project.read_only || !!fisImportRecovery || !!fisSaveRecovery || importingMatlabFis || fisActionBusy}
            onClick={() => importInputRef.current?.click()}
            data-ruflex-action="fis.import"
          >
            {importingMatlabFis ? "Importing MATLAB FIS…" : "Import MATLAB .fis"}
          </Button>
          <Button view="outlined" disabled={!working.semantic_hash || savingFis} onClick={exportMatlabFile} data-ruflex-action="fis.export">
            Export MATLAB .fis
          </Button>
          <Button view="action" disabled={evaluatingFis || !working.semantic_hash || !!fisEvaluationRecovery || fisActionBusy} onClick={run} data-ruflex-action="fis.evaluate">
            Run exact inference
          </Button>
        </div>
        {fisSaveRecovery && <div className="error" role="alert" data-testid="fis-save-recovery"><strong>FIS save response is uncertain; the exact revision has not been resubmitted.</strong><p>{fisSaveRecovery.error}</p><Button view="outlined" disabled={recoveringFisSave || fisActionBusy} onClick={recoverFisSave}>Retry exact FIS revision lookup</Button>{fisSaveRecovery.notFound && working && canonicalJson(fisSemanticPayload(working)) !== canonicalJson(fisSemanticPayload(fisSaveRecovery.spec)) && <Button view="outlined" disabled={recoveringFisSave || fisActionBusy} onClick={restorePendingFisSaveSnapshot}>Restore exact pending FIS copy</Button>}{fisSaveRecovery.notFound && <Button view="outlined" disabled={recoveringFisSave || project.read_only || !working || fisActionBusy || canonicalJson(fisSemanticPayload(working)) !== canonicalJson(fisSemanticPayload(fisSaveRecovery.spec))} onClick={explicitlyRepeatFisSave}>Explicitly repeat unchanged FIS save</Button>}</div>}
        {fisImportRecovery && <div className="error" role="alert" data-testid="fis-import-recovery"><strong>MATLAB FIS import response is uncertain.</strong><p>{fisImportRecovery.error} The exact source is retained; retrying it will not create a duplicate imported revision.</p><Button view="outlined" disabled={retryingFisImport || importingMatlabFis || fisActionBusy} onClick={retrySameMatlabImport}>Retry exact MATLAB FIS import</Button></div>}
      </div>
      <div className="designer-grid">
        <aside className="variable-list">
          <h3>Variables</h3>
          {working.inputs.map((variable, index) => (
            <button
              className={index === selected ? "selected" : ""}
              key={variable.name}
              onClick={() => setSelected(index)}
            >
              {variable.name}
              <small>{variable.terms.length} terms</small>
            </button>
          ))}
          <div className="form-actions">
            <Button
              view="outlined"
              disabled={project.read_only}
              onClick={addVariable}
            >
              Add input
            </Button>
            <Button
              view="outlined"
              disabled={project.read_only || working.inputs.length <= 1}
              onClick={removeVariable}
            >
              Remove
            </Button>
            <Button
              view="outlined"
              disabled={project.read_only}
              onClick={duplicateVariable}
            >
              Duplicate
            </Button>
            <Button
              view="outlined"
              disabled={project.read_only || selected === 0}
              onClick={() => moveVariable(-1)}
            >
              Move up
            </Button>
            <Button
              view="outlined"
              disabled={
                project.read_only || selected === working.inputs.length - 1
              }
              onClick={() => moveVariable(1)}
            >
              Move down
            </Button>
          </div>
          <strong>Output</strong>
          <label>
            Name
            <TextInput
              value={working.output.name}
              disabled={project.read_only || working.output.locked}
              onUpdate={(value) =>
                mutate((next) => {
                  next.output.name = value;
                })
              }
            />
          </label>
          <label>
            Range
            <span className="output-range-fields">
              <input
                aria-label="Output minimum"
                type="number"
                value={working.output.minimum}
                disabled={project.read_only || working.output.locked}
                onChange={(event) =>
                  mutate((next) => {
                    next.output.minimum = event.target.valueAsNumber;
                  })
                }
              />
              <input
                aria-label="Output maximum"
                type="number"
                value={working.output.maximum}
                disabled={project.read_only || working.output.locked}
                onChange={(event) =>
                  mutate((next) => {
                    next.output.maximum = event.target.valueAsNumber;
                  })
                }
              />
            </span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={working.output.locked}
              disabled={project.read_only}
              onChange={(event) =>
                mutate((next) => {
                  next.output.locked = event.target.checked;
                })
              }
            />{" "}
            Lock output
          </label>
          <div className="output-term-summary">
            <strong>Output terms</strong>
            {working.output.terms.map((term, index) => (
              <div key={`${term.name}-${index}`}>
                <TextInput
                  aria-label={`Output term ${index + 1} name`}
                  value={term.name}
                  disabled={project.read_only || working.output.locked}
                  onUpdate={(value) =>
                    mutate((next) => {
                      next.output.terms[index].name = value;
                      next.rules.forEach((rule) => {
                        if (rule.output_term === term.name) rule.output_term = value;
                      });
                    })
                  }
                />
                <select
                  aria-label={`Output term ${index + 1} family`}
                  value={term.kind}
                  disabled={project.read_only || working.output.locked}
                  onChange={(event) =>
                    mutate((next) => {
                      const kind = event.target.value as MembershipFunction["kind"];
                      next.output.terms[index].kind = kind;
                      next.output.terms[index].parameters = defaultParameters(
                        kind,
                        next.output.minimum,
                        next.output.maximum,
                      );
                    })
                  }
                >
                  {Object.entries(familyLabel).map(([kind, label]) => (
                    <option value={kind} key={kind}>
                      {label}
                    </option>
                  ))}
                </select>
                {term.parameters.map((parameter, parameterIndex) => (
                  <label key={parameterIndex}>
                    p{parameterIndex + 1}
                    <input
                      aria-label={`Output ${term.name} p${parameterIndex + 1}`}
                      type="number"
                      step="any"
                      value={parameter}
                      disabled={project.read_only || working.output.locked}
                      onChange={(event) =>
                        mutate((next) => {
                          next.output.terms[index].parameters[parameterIndex] =
                            event.target.valueAsNumber;
                        })
                      }
                    />
                  </label>
                ))}
                <Button
                  view="outlined"
                  disabled={project.read_only || working.output.locked}
                  onClick={() => duplicateOutputTerm(index)}
                >
                  Duplicate
                </Button>
                <Button
                  view="outlined"
                  disabled={
                    project.read_only ||
                    working.output.locked ||
                    working.output.terms.length <= 1
                  }
                  onClick={() =>
                    mutate((next) => {
                      const removed = next.output.terms[index].name;
                      const replacement = next.output.terms.find(
                        (_, itemIndex) => itemIndex !== index,
                      )?.name;
                      next.output.terms.splice(index, 1);
                      if (replacement)
                        next.rules.forEach((rule) => {
                          if (rule.output_term === removed)
                            rule.output_term = replacement;
                        });
                    })
                  }
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              view="outlined"
              disabled={project.read_only || working.output.locked}
              onClick={addOutputTerm}
            >
              Add output term
            </Button>
          </div>
        </aside>
        <section className="fis-main">
          {selectedVariable && chart && (
            <>
              <div className="inspector-heading">
                <h3>{selectedVariable.name} inspector</h3>
                <label>
                  Locked{" "}
                  <input
                    type="checkbox"
                    checked={selectedVariable.locked}
                    disabled={project.read_only}
                    onChange={(e) =>
                      mutate((next) => {
                        next.inputs[selected].locked = e.target.checked;
                      })
                    }
                  />
                </label>
              </div>
              <div className="variable-fields">
                <label>
                  Name{" "}
                  <TextInput
                    value={selectedVariable.name}
                    disabled={project.read_only || selectedVariable.locked}
                    onUpdate={(value) =>
                      mutate((next) => {
                        next.inputs[selected].name = value;
                        next.inputs[selected].dataset_feature = value;
                        next.rules.forEach((r) =>
                          r.clauses.forEach((c) => {
                            if (c.variable === selectedVariable.name)
                              c.variable = value;
                          }),
                        );
                      })
                    }
                  />
                </label>
                <label>
                  Min{" "}
                  <input
                    type="number"
                    value={selectedVariable.minimum}
                    disabled={project.read_only || selectedVariable.locked}
                    onChange={(e) =>
                      mutate(
                        (next) =>
                          (next.inputs[selected].minimum =
                            e.target.valueAsNumber),
                      )
                    }
                  />
                </label>
                <label>
                  Max{" "}
                  <input
                    type="number"
                    value={selectedVariable.maximum}
                    disabled={project.read_only || selectedVariable.locked}
                    onChange={(e) =>
                      mutate(
                        (next) =>
                          (next.inputs[selected].maximum =
                            e.target.valueAsNumber),
                      )
                    }
                  />
                </label>
                <label>
                  Units{" "}
                  <TextInput
                    value={selectedVariable.units ?? ""}
                    disabled={project.read_only || selectedVariable.locked}
                    onUpdate={(value) =>
                      mutate(
                        (next) => (next.inputs[selected].units = value || null),
                      )
                    }
                  />
                </label>
                <label>
                  Dataset feature
                  <select
                    aria-label="Dataset feature mapping"
                    value={selectedVariable.dataset_feature ?? ""}
                    disabled={project.read_only || selectedVariable.locked}
                    onChange={(event) =>
                      mutate((next) => {
                        next.inputs[selected].dataset_feature =
                          event.target.value || null;
                      })
                    }
                  >
                    <option value="">Not mapped</option>
                    {(dataset?.contract.feature_columns ?? []).map((feature) => (
                      <option key={feature} value={feature}>
                        {feature}
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  view="outlined"
                  disabled={
                    project.read_only ||
                    selectedVariable.locked ||
                    !selectedVariable.dataset_feature
                  }
                  onClick={resetSelectedRangeFromDataset}
                >
                  Reset range from dataset
                </Button>
              </div>
              <ChartSurface
                title="Membership overview"
                option={chart}
                theme={theme}
              />
              <MembershipEditorCanvas
                variable={selectedVariable}
                readOnly={project.read_only || selectedVariable.locked}
                onParameterChange={(termIndex, parameterIndex, value) =>
                  mutate(
                    (next) =>
                      (next.inputs[selected].terms[termIndex].parameters[
                        parameterIndex
                      ] = value),
                  )
                }
              />
              <div className="mf-editor-grid">
                {selectedVariable.terms.map((term, termIndex) => (
                  <div className="mf-editor rich" key={termIndex}>
                    <label>
                      <input
                        type="checkbox"
                        checked={term.locked}
                        disabled={project.read_only || selectedVariable.locked}
                        onChange={(event) =>
                          mutate((next) => {
                            next.inputs[selected].terms[termIndex].locked =
                              event.target.checked;
                          })
                        }
                      />{" "}
                      Lock term
                    </label>
                    <TextInput
                      aria-label={`${selectedVariable.name} term ${termIndex + 1} name`}
                      value={term.name}
                      disabled={
                        project.read_only || selectedVariable.locked || term.locked
                      }
                      onUpdate={(value) =>
                        mutate(
                          (next) =>
                            (next.inputs[selected].terms[termIndex].name =
                              value),
                        )
                      }
                    />
                    <select
                      aria-label={`${term.name} family`}
                      value={term.kind}
                      disabled={
                        project.read_only || selectedVariable.locked || term.locked
                      }
                      onChange={(e) =>
                        mutate((next) => {
                          const kind = e.target
                            .value as MembershipFunction["kind"];
                          next.inputs[selected].terms[termIndex].kind = kind;
                          next.inputs[selected].terms[termIndex].parameters =
                            defaultParameters(
                              kind,
                              next.inputs[selected].minimum,
                              next.inputs[selected].maximum,
                            );
                        })
                      }
                    >
                      {Object.entries(familyLabel).map(([kind, label]) => (
                        <option value={kind} key={kind}>
                          {label}
                        </option>
                      ))}
                    </select>
                    {term.parameters.map((p, paramIndex) => (
                      <label key={paramIndex}>
                        p{paramIndex + 1}
                        <input
                          aria-label={`${selectedVariable.name} ${term.name} p${paramIndex + 1}`}
                          type="range"
                          min={
                            parameterBounds(
                              selectedVariable,
                              term,
                              paramIndex,
                            )[0]
                          }
                          max={
                            parameterBounds(
                              selectedVariable,
                              term,
                              paramIndex,
                            )[1]
                          }
                          step={
                            (parameterBounds(
                              selectedVariable,
                              term,
                              paramIndex,
                            )[1] -
                              parameterBounds(
                                selectedVariable,
                                term,
                                paramIndex,
                              )[0]) /
                            200
                          }
                          value={p}
                          disabled={
                            project.read_only || selectedVariable.locked || term.locked
                          }
                          onChange={(e) =>
                            mutate(
                              (next) =>
                                (next.inputs[selected].terms[
                                  termIndex
                                ].parameters[paramIndex] =
                                  e.target.valueAsNumber),
                            )
                          }
                        />
                        <input
                          type="number"
                          step="any"
                          value={p}
                          disabled={
                            project.read_only || selectedVariable.locked || term.locked
                          }
                          onChange={(e) =>
                            mutate(
                              (next) =>
                                (next.inputs[selected].terms[
                                  termIndex
                                ].parameters[paramIndex] =
                                  e.target.valueAsNumber),
                            )
                          }
                        />
                      </label>
                    ))}
                    <Button
                      view="outlined"
                      disabled={
                        project.read_only || selectedVariable.locked || term.locked
                      }
                      onClick={() =>
                        mutate((next) =>
                          next.inputs[selected].terms.splice(termIndex, 1),
                        )
                      }
                    >
                      Remove term
                    </Button>
                    <Button
                      view="outlined"
                      disabled={
                        project.read_only || selectedVariable.locked || term.locked
                      }
                      onClick={() => duplicateTerm(termIndex)}
                    >
                      Duplicate term
                    </Button>
                    <Button
                      view="outlined"
                      disabled={
                        project.read_only ||
                        selectedVariable.locked || term.locked ||
                        termIndex === 0
                      }
                      onClick={() => moveTerm(termIndex, -1)}
                    >
                      Move up
                    </Button>
                    <Button
                      view="outlined"
                      disabled={
                        project.read_only ||
                        selectedVariable.locked || term.locked ||
                        termIndex === selectedVariable.terms.length - 1
                      }
                      onClick={() => moveTerm(termIndex, 1)}
                    >
                      Move down
                    </Button>
                  </div>
                ))}
              </div>
              <Button
                view="outlined"
                disabled={project.read_only || selectedVariable.locked}
                onClick={addTerm}
              >
                Add term
              </Button>
            </>
          )}
        </section>
        <aside className="fis-run-panel">
          <h3>Operators</h3>
          <label>
            T-norm
            <select
              value={working.operators.and_operator}
              disabled={project.read_only}
              onChange={(e) =>
                mutate(
                  (next) =>
                    (next.operators.and_operator = e.target
                      .value as FISSpec["operators"]["and_operator"]),
                )
              }
            >
              {["min", "product", "lukasiewicz", "hamacher", "einstein"].map(
                (x) => (
                  <option key={x}>{x}</option>
                ),
              )}
            </select>
          </label>
          <label>
            S-norm
            <select
              value={working.operators.or_operator}
              disabled={project.read_only}
              onChange={(e) =>
                mutate(
                  (next) =>
                    (next.operators.or_operator = e.target
                      .value as FISSpec["operators"]["or_operator"]),
                )
              }
            >
              {[
                "max",
                "probabilistic_sum",
                "bounded_sum",
                "hamacher",
                "einstein",
              ].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          <label>
            Implication
            <select
              value={working.operators.implication}
              disabled={project.read_only || working.system_type === "sugeno"}
              onChange={(e) =>
                mutate(
                  (next) =>
                    (next.operators.implication = e.target
                      .value as FISSpec["operators"]["implication"]),
                )
              }
            >
              <option>min</option>
              <option>product</option>
            </select>
          </label>
          <label>
            Aggregation
            <select
              value={working.operators.aggregation}
              disabled={project.read_only || working.system_type === "sugeno"}
              onChange={(e) =>
                mutate(
                  (next) =>
                    (next.operators.aggregation = e.target
                      .value as FISSpec["operators"]["aggregation"]),
                )
              }
            >
              {[
                "max",
                "probabilistic_sum",
                "bounded_sum",
                "hamacher",
                "einstein",
              ].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          {working.system_type === "mamdani" && <>
            <label>
              Defuzzification
              <select value={working.operators.defuzzification} disabled>
                <option value="centroid">Centroid</option>
              </select>
            </label>
            <label>
              Resolution
              <TextInput
                value={String(working.operators.centroid_resolution)}
                disabled={project.read_only}
                onUpdate={(value) => {
                  const parsed = Number(value);
                  if (Number.isInteger(parsed) && parsed > 0) mutate((next) => { next.operators.centroid_resolution = parsed; });
                }}
              />
            </label>
            <label>
              Sampling
              <select
                aria-label="Centroid sampling"
                value={working.operators.centroid_sampling}
                disabled={project.read_only}
                onChange={(event) => mutate((next) => { next.operators.centroid_sampling = event.target.value as FISSpec["operators"]["centroid_sampling"]; })}
              >
                <option value="midpoint_cells">Midpoint cells</option>
                <option value="inclusive_nodes">Inclusive nodes (legacy RuFLEX)</option>
              </select>
            </label>
            <p className="field-help">Midpoint cells samples the center of each discretization interval. Inclusive nodes preserves legacy RuFLEX behavior.</p>
          </>}
          <h3>Run model</h3>
          {working.inputs.map((variable) => (
            <label className="field-label" key={variable.name}>
              {variable.name}
              <TextInput
                value={runInputs[variable.name] ?? ""}
                onUpdate={(value) =>
                  setRunInputs((current) => ({
                    ...current,
                    [variable.name]: value,
                  }))
                }
              />
            </label>
          ))}
          <Button view="action" disabled={evaluatingFis || recoveringFisEvaluation || !working.semantic_hash || !!fisEvaluationRecovery || fisActionBusy} onClick={run}>
            {evaluatingFis ? "Evaluating…" : "Evaluate"}
          </Button>
          {!working.semantic_hash && <p role="status">Save this FIS revision before evaluating or exporting; both operations use the active persisted model.</p>}
          {evaluatingFis && <p role="status">Running the current FIS input sample…</p>}
          {evaluationStatus === "loading" && <p role="status">Checking the saved exact FIS trace…</p>}
          {evaluationStatus === "none" && !lastOutput && <p>No saved exact FIS trace is available yet.</p>}
          {evaluationStatus === "error" && <div className="error" role="alert"><strong>Could not load saved FIS evaluation evidence.</strong> {evaluationError} <Button view="outlined" size="s" onClick={onRetryEvaluation}>Retry FIS trace check</Button></div>}
          {lastOutput && !lastOutputMatchesCurrent && <p role="status">The displayed FIS result belongs to another model revision or input sample. Evaluate to produce a trace for the current values.</p>}
          {lastOutput && lastOutputMatchesCurrent && (
            <div className="result-card">
              <span className="eyebrow">OUTPUT</span>
              <strong>{lastOutput.evaluation.output.toFixed(5)}</strong>
              <StatusBadge tone="success">
                trace error{" "}
                {lastOutput.evaluation.trace.reconstruction_error.toExponential(
                  2,
                )}
              </StatusBadge>
              <Button view="outlined" onClick={onOpenTrace}>
                Open exact trace
              </Button>
            </div>
          )}
        </aside>
      </div>
      {working.inputs.length >= 2 && surfaceAxes && (
        <section className="response-surface-panel">
          <div className="feature-toolbar">
            <div>
              <span className="eyebrow">RESPONSE SURFACE</span>
              <h3>Canonical control surface</h3>
            </div>
            <Button view="outlined" disabled={surfaceLoading} onClick={refreshSurface}>
              {surfaceLoading ? "Refreshing surface…" : "Refresh surface"}
            </Button>
          </div>
          <div className="surface-controls">
            <label>
              X axis
              <select
                aria-label="Surface X axis"
                value={surfaceAxes[0]}
                onChange={(event) =>
                  setSurfaceAxes([
                    event.target.value,
                    surfaceAxes[1] === event.target.value
                      ? (working.inputs.find(
                          (variable) => variable.name !== event.target.value,
                        )?.name ?? surfaceAxes[1])
                      : surfaceAxes[1],
                  ])
                }
              >
                {working.inputs.map((variable) => (
                  <option key={variable.name}>{variable.name}</option>
                ))}
              </select>
            </label>
            <label>
              Y axis
              <select
                aria-label="Surface Y axis"
                value={surfaceAxes[1]}
                onChange={(event) =>
                  setSurfaceAxes([
                    surfaceAxes[0] === event.target.value
                      ? (working.inputs.find(
                          (variable) => variable.name !== event.target.value,
                        )?.name ?? surfaceAxes[0])
                      : surfaceAxes[0],
                    event.target.value,
                  ])
                }
              >
                {working.inputs.map((variable) => (
                  <option key={variable.name}>{variable.name}</option>
                ))}
              </select>
            </label>
            <span>
              {working.inputs.length > 2
                ? "Other variables use the Run panel values."
                : "Every cell uses the current canonical FIS."}
            </span>
          </div>
          {surfaceError && <p className="error" role="alert">Response surface could not be refreshed. {surfaceError}</p>}
          {surfaceLoading && <p role="status">Evaluating the current FIS and fixed input values…</p>}
          {surface ? (
            <ChartSurface
              title={`${surface.x_variable} × ${surface.y_variable} → ${working.output.name}`}
              option={responseSurfaceOption(surface)}
              theme={theme}
            />
          ) : !surfaceLoading && !surfaceError ? (
            <p className="surface-placeholder">
              Choose axes and refresh to evaluate the real current FIS over the
              control grid.
            </p>
          ) : null}
        </section>
      )}
      <section className="rule-engineering">
        <div className="feature-toolbar">
          <div>
            <span className="eyebrow">RULE ENGINEERING</span>
            <h3>Table and text represent the same canonical rule base</h3>
          </div>
          <Button
            view="outlined"
            disabled={project.read_only}
            onClick={addRule}
          >
            Add rule
          </Button>
          <TextInput
            aria-label="Filter rules"
            value={ruleFilter}
            onUpdate={setRuleFilter}
            placeholder="Filter rules"
          />
        </div>
        {visibleRules.map(({ rule, index }) => (
          <div className="rule-row editable" key={rule.rule_id}>
            <label>
              <input
                type="checkbox"
                checked={rule.enabled}
                disabled={project.read_only}
                onChange={(e) =>
                  mutate(
                    (next) => (next.rules[index].enabled = e.target.checked),
                  )
                }
              />{" "}
              Rule {index + 1}
            </label>
            <select
              value={rule.connector}
              disabled={project.read_only}
              onChange={(e) =>
                mutate(
                  (next) =>
                    (next.rules[index].connector = e.target.value as
                      "and" | "or"),
                )
              }
            >
              <option value="and">AND</option>
              <option value="or">OR</option>
            </select>
            <span>
              {rule.clauses.map((clause, clauseIndex) => (
                <label key={`${clause.variable}-${clauseIndex}`}>
                  {clause.variable} IS{" "}
                  <select
                    value={clause.term}
                    disabled={project.read_only}
                    onChange={(event) =>
                      mutate(
                        (next) =>
                          (next.rules[index].clauses[clauseIndex].term =
                            event.target.value),
                      )
                    }
                  >
                    {working.inputs
                      .find((variable) => variable.name === clause.variable)
                      ?.terms.map((term) => (
                        <option key={term.name}>{term.name}</option>
                      ))}
                  </select>
                </label>
              ))}{" "}
              →{" "}
              {working.system_type === "mamdani" ? (
                <>
                  {working.output.name} IS{" "}
                  <select
                    value={rule.output_term}
                    disabled={project.read_only}
                    onChange={(e) =>
                      mutate(
                        (next) =>
                          (next.rules[index].output_term = e.target.value),
                      )
                    }
                  >
                    {working.output.terms.map((term) => (
                      <option key={term.name}>{term.name}</option>
                    ))}
                  </select>
                </>
              ) : (
                <label>
                  Sugeno{" "}
                  <select
                    value={rule.sugeno_consequent?.kind ?? "constant"}
                    disabled={project.read_only}
                    onChange={(event) =>
                      mutate((next) => {
                        const current = next.rules[index].sugeno_consequent;
                        next.rules[index].sugeno_consequent =
                          event.target.value === "linear"
                            ? {
                                kind: "linear",
                                constant: null,
                                coefficients: {},
                                intercept: current?.constant ?? 0,
                              }
                            : {
                                kind: "constant",
                                constant:
                                  current?.intercept ??
                                  outputCenter(
                                    next.output,
                                    next.rules[index].output_term,
                                  ),
                                coefficients: {},
                                intercept: 0,
                              };
                      })
                    }
                  >
                    <option value="constant">constant</option>
                    <option value="linear">linear</option>
                  </select>
                  <input
                    aria-label={`Rule ${index + 1} Sugeno value`}
                    type="number"
                    step="any"
                    value={
                      rule.sugeno_consequent?.kind === "linear"
                        ? rule.sugeno_consequent.intercept
                        : (rule.sugeno_consequent?.constant ?? 0)
                    }
                    disabled={project.read_only}
                    onChange={(event) =>
                      mutate((next) => {
                        const consequent = next.rules[index].sugeno_consequent;
                        if (!consequent) return;
                        if (consequent.kind === "linear")
                          consequent.intercept = event.target.valueAsNumber;
                        else consequent.constant = event.target.valueAsNumber;
                      })
                    }
                  />
                </label>
              )}
            </span>
            {working.system_type === "sugeno" && (
              <label className="expert-rule-lock">
                <input
                  type="checkbox"
                  checked={expertLockedRules.includes(rule.rule_id)}
                  disabled={project.read_only}
                  onChange={(event) =>
                    setExpertLockedRules((current) =>
                      event.target.checked
                        ? [...new Set([...current, rule.rule_id])]
                        : current.filter((id) => id !== rule.rule_id),
                    )
                  }
                />{" "}
                Preserve consequent
              </label>
            )}
            <label>
              Weight{" "}
              <input
                aria-label={`Rule ${index + 1} weight`}
                type="number"
                min="0"
                max="1"
                step=".05"
                value={rule.weight}
                disabled={project.read_only}
                onChange={(e) =>
                  mutate(
                    (next) =>
                      (next.rules[index].weight = e.target.valueAsNumber),
                  )
                }
              />
            </label>
            <Button
              view="outlined"
              disabled={project.read_only}
              onClick={() => mutate((next) => next.rules.splice(index, 1))}
            >
              Remove
            </Button>
            <Button
              view="outlined"
              disabled={project.read_only}
              onClick={() => duplicateRule(index)}
            >
              Duplicate
            </Button>
            <Button
              view="outlined"
              disabled={project.read_only || index === 0}
              onClick={() => moveRule(index, -1)}
            >
              Move up
            </Button>
            <Button
              view="outlined"
              disabled={project.read_only || index === working.rules.length - 1}
              onClick={() => moveRule(index, 1)}
            >
              Move down
            </Button>
          </div>
        ))}
        <div className="rule-text-editor">
          <label>
            Add rule as text
            <textarea
              aria-label="Rule text"
              value={textRule}
              onChange={(e) => setTextRule(e.target.value)}
              placeholder="IF Temperature IS High AND Torque IS Low THEN target_score IS High WITH 0.95"
            />
          </label>
          <Button
            view="outlined"
            disabled={project.read_only}
            onClick={addTextRule}
          >
            Parse and add rule
          </Button>
        </div>
        <div className="diagnostics">
          <div className="feature-toolbar">
            <strong>FIS diagnostics</strong>
            <Button view="outlined" onClick={refreshDiagnostics}>
              Refresh diagnostics
            </Button>
          </div>
          <span>
            {duplicateRules
              ? `${duplicateRules} duplicate rule(s) detected.`
              : "No duplicate rule text detected."}
          </span>
          <span>
            {working.rules.filter((rule) => !rule.enabled).length} disabled
            rule(s); firing statistics appear after an exact run in Trace.
          </span>
          {diagnostics.map((finding, index) => (
            <span key={`${finding.code}-${index}`}>
              {finding.code}: {finding.message}
            </span>
          ))}
        </div>
      </section>
      {working.system_type === "sugeno" && (
        <section className="expert-correction-panel">
          <div className="feature-toolbar">
            <div>
              <span className="eyebrow">EXPERT CORRECTION</span>
              <h3>Preserve expert structure, refit unlocked consequents</h3>
              <p>
                Membership functions, antecedents, operators and rule weights stay fixed. Only unlocked Sugeno consequents are fitted by least squares on the TRAIN partition; validation and final test are not used for this fit.
              </p>
            </div>
            <Button
              view="action"
              disabled={project.read_only || recoveringExpertRefit || !!expertRefitRecovery || expertLockedRules.length >= working.rules.filter((rule) => rule.enabled).length || fisActionBusy}
              onClick={refitExpertConsequents}
            >
              {recoveringExpertRefit && !expertRefitRecovery ? "Fitting unlocked consequents…" : "Refit unlocked consequents on TRAIN"}
            </Button>
          </div>
          <div className="expert-correction-summary">
            <span>{expertLockedRules.length} consequent(s) preserved by expert lock.</span>
            {expertRefitRecovery && <div className="error" role="alert" data-testid="expert-refit-recovery"><strong>Expert correction response is uncertain; no second TRAIN fit was started.</strong><p>{expertRefitRecovery.error}</p><Button view="outlined" disabled={recoveringExpertRefit || fisActionBusy} onClick={recoverExpertRefit}>Retry exact correction lookup</Button>{expertRefitRecovery.notFound && <Button view="outlined" disabled={recoveringExpertRefit || project.read_only || fisActionBusy} onClick={retryExpertRefit}>Explicitly retry exact correction on unchanged source FIS</Button>}</div>}
            {expertCorrectionLoadStatus === "loading" && <span role="status">Loading saved expert correction…</span>}
            {expertCorrectionLoadStatus === "none" && <span data-testid="expert-correction-empty">No saved expert correction is available for this FIS revision.</span>}
            {expertCorrectionLoadStatus === "error" && <div className="error" role="alert" data-testid="expert-correction-load-error"><strong>Saved expert correction could not be verified.</strong><p>{expertCorrectionLoadError}</p><Button view="outlined" onClick={() => setExpertCorrectionReload((current) => current + 1)}>Retry expert correction</Button></div>}
            {sourceExplanationId && (
              <label className="comparison-choice">
                <input
                  type="checkbox"
                  checked={linkSourceExplanation}
                  onChange={(event) => setLinkSourceExplanation(event.target.checked)}
                />
                Link evidence {sourceExplanationId.slice(0, 12)} as the explicit motivation for this correction
              </label>
            )}
            {expertCorrection && (
              <>
                <span>Last correction: {expertCorrection.fitted_rule_ids.length} fitted · {expertCorrection.train_row_count} TRAIN rows.</span>
                <span>TRAIN RMSE {expertCorrection.train_rmse_before.toFixed(5)} → {expertCorrection.train_rmse_after.toFixed(5)}</span>
                {expertCorrection.validation_rmse_before !== null && expertCorrection.validation_rmse_after !== null && <span>VALIDATION RMSE {expertCorrection.validation_rmse_before.toFixed(5)} → {expertCorrection.validation_rmse_after.toFixed(5)} · {expertCorrection.validation_row_count} rows · evaluation only</span>}
                {expertCorrection.source_explanation_id && <span>Motivated by evidence {expertCorrection.source_explanation_id.slice(0, 12)}</span>}
                <StatusBadge tone="success">{expertCorrection.test_status}</StatusBadge>
                {correctionChanges.length > 0 && (
                  <details className="semantic-diff-details">
                    <summary>Semantic before/after · {correctionChanges.length} changed field(s)</summary>
                    <div className="semantic-diff-list">
                      {correctionChanges.map((change) => (
                        <div className="semantic-diff-row" key={`${change.path}-${change.before}-${change.after}`}>
                          <strong>{change.path}</strong>
                          <code>{change.before}</code>
                          <span>→</span>
                          <code>{change.after}</code>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </>
            )}
          </div>
        </section>
      )}
      <section className="model-history-panel">
        <div>
          <span className="eyebrow">MODEL REVISION HISTORY</span>
          <h3>Saved canonical revisions</h3>
        </div>
        {revisionHistoryStatus === "loading" && <p role="status">Loading saved FIS revisions…</p>}
        {revisionHistoryStatus === "error" && <div className="error" role="alert" data-testid="fis-revision-history-error"><p>Saved FIS revision history could not be verified. {revisionHistoryError}</p><Button view="outlined" onClick={() => setRevisionHistoryReload((current) => current + 1)}>Retry revision history</Button></div>}
        {revisionHistoryStatus === "available" && revisions.length ? (
          <>
            <ol>
              {revisions.map((revision, index) => (
                <li key={revision.semantic_hash ?? revision.fis_id}>
                  <code>{revision.semantic_hash?.slice(0, 16)}</code>
                  <span>
                    {index === revisions.length - 1
                      ? "current saved revision"
                      : `revision ${index + 1}`}
                  </span>
                  <div className="form-actions revision-actions">
                    <Button view="outlined" onClick={() => setHistoryBaseHash(revision.semantic_hash)}>Compare</Button>
                    <Button view="outlined" disabled={project.read_only} onClick={() => openHistoricalRevision(revision)}>Open as working copy</Button>
                  </div>
                </li>
              ))}
            </ol>
            {historyBase && working && (
              <section className="semantic-diff-panel">
                <div>
                  <span className="eyebrow">SEMANTIC DIFF</span>
                  <h4>{historyBase.semantic_hash?.slice(0, 12)} → working copy</h4>
                </div>
                {historyChanges.length ? (
                  <div className="semantic-diff-list">
                    {historyChanges.map((change) => (
                      <div className="semantic-diff-row" key={`${change.path}-${change.before}-${change.after}`}>
                        <strong>{change.path}</strong>
                        <code>{change.before}</code>
                        <span>→</span>
                        <code>{change.after}</code>
                      </div>
                    ))}
                  </div>
                ) : <p>No semantic differences from the selected saved revision.</p>}
              </section>
            )}
          </>
        ) : revisionHistoryStatus === "empty" ? (
          <p>Save this model to create an immutable semantic revision.</p>
        ) : null}
      </section>
      <section className="canonical-source-panel">
        <div>
          <span className="eyebrow">PYTHON ESCAPE HATCH · CANONICAL MODEL</span>
          <h3>Inspect the exact model representation</h3>
          <p>The editor and Python SDK share this canonical FIS structure. Current JSON reflects unsaved editor state; YAML is loaded from the saved project revision.</p>
        </div>
        <details>
          <summary>Current canonical JSON</summary>
          <pre>{JSON.stringify(working, null, 2)}</pre>
        </details>
        <div className="form-actions">
          <Button view="outlined" onClick={loadCanonicalYaml}>Load saved canonical YAML</Button>
        </div>
        {canonicalYaml && <details open><summary>Saved canonical YAML</summary><pre>{canonicalYaml}</pre></details>}
      </section>
      {compatibilityIssues.length > 0 && (
        <section
          className="compatibility-report"
          aria-label="MATLAB FIS compatibility report"
        >
          <span className="eyebrow">MATLAB FIS COMPATIBILITY</span>
          {compatibilityIssues.map((issue, index) => (
            <p key={`${issue.source_construct}-${index}`}>
              <StatusBadge
                tone={issue.status === "UNSUPPORTED" ? "danger" : "success"}
              >
                {issue.status}
              </StatusBadge>{" "}
              {issue.source_construct} → {issue.ruflex_construct ?? "not imported"}: {issue.semantic_consequence}
            </p>
          ))}
        </section>
      )}
      {message && <div className="info-message">{message}</div>}
        {fisEvaluationRecovery && <div className="error" role="alert" data-testid="fis-evaluation-recovery"><strong>FIS inference outcome is uncertain; no duplicate trace was submitted.</strong><p>{fisEvaluationRecovery.error}</p><Button view="outlined" disabled={recoveringFisEvaluation || fisActionBusy} onClick={recoverFisEvaluation}>Retry exact FIS trace lookup</Button>{fisEvaluationRecovery.notFound && <Button view="outlined" disabled={recoveringFisEvaluation || project.read_only || working.fis_id !== fisEvaluationRecovery.fisId || working.semantic_hash !== fisEvaluationRecovery.semanticHash || fisActionBusy} onClick={explicitlyRepeatFisEvaluation}>Explicitly repeat this exact inference</Button>}</div>}
        {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}
