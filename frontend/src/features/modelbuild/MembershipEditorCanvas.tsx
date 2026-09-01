import { PointerEvent, useMemo, useRef } from "react";
import { FuzzyVariable, MembershipFunction } from "../../api";

type Props = {
  variable: FuzzyVariable;
  readOnly: boolean;
  onParameterChange: (
    termIndex: number,
    parameterIndex: number,
    value: number,
  ) => void;
};

const colours = [
  "#4d5fc7",
  "#ce7b2e",
  "#2f8f6f",
  "#b64d68",
  "#7a5bbd",
  "#268a9c",
];

function curve(term: MembershipFunction, value: number): number {
  const p = term.parameters;
  if (term.kind === "triangular") {
    const [a, b, c] = p;
    return value === b
      ? 1
      : value <= a || value >= c
        ? 0
        : value < b
          ? (value - a) / Math.max(b - a, 1e-12)
          : (c - value) / Math.max(c - b, 1e-12);
  }
  if (term.kind === "trapezoidal") {
    const [a, b, c, d] = p;
    return Math.max(
      0,
      Math.min(
        (value - a) / Math.max(b - a, 1e-12),
        1,
        (d - value) / Math.max(d - c, 1e-12),
      ),
    );
  }
  if (term.kind === "gaussian") {
    const [center, width] = p;
    return Math.exp(-0.5 * ((value - center) / width) ** 2);
  }
  if (term.kind === "bell") {
    const [width, shape, center] = p;
    return 1 / (1 + Math.abs((value - center) / width) ** (2 * shape));
  }
  if (term.kind === "sigmoid") {
    const [slope, center] = p;
    return (
      1 / (1 + Math.exp(-Math.max(-60, Math.min(60, slope * (value - center)))))
    );
  }
  if (term.kind === "s_shape" || term.kind === "z_shape") {
    const [a, b] = p;
    const t = Math.max(0, Math.min(1, (value - a) / Math.max(b - a, 1e-12)));
    const s = t <= 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t);
    return term.kind === "s_shape" ? s : 1 - s;
  }
  const [a, b, c, d] = p;
  return Math.min(
    curve({ name: "s", kind: "s_shape", parameters: [a, b], locked: false }, value),
    curve({ name: "z", kind: "z_shape", parameters: [c, d], locked: false }, value),
  );
}

function xParameters(
  term: MembershipFunction,
): Array<{ parameterIndex: number; x: number }> {
  const p = term.parameters;
  if (term.kind === "gaussian")
    return [
      { parameterIndex: 0, x: p[0] },
      { parameterIndex: 1, x: p[0] + p[1] },
    ];
  if (term.kind === "bell")
    return [
      { parameterIndex: 2, x: p[2] },
      { parameterIndex: 0, x: p[2] + p[0] },
    ];
  if (term.kind === "sigmoid") return [{ parameterIndex: 1, x: p[1] }];
  return p.map((value, parameterIndex) => ({ parameterIndex, x: value }));
}

export function MembershipEditorCanvas({
  variable,
  readOnly,
  onParameterChange,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const width = 720;
  const height = 250;
  const pad = 30;
  const span = variable.maximum - variable.minimum;
  const toX = (value: number) =>
    pad + ((value - variable.minimum) / span) * (width - pad * 2);
  const toY = (degree: number) => height - pad - degree * (height - pad * 2);
  const paths = useMemo(
    () =>
      variable.terms.map((term, index) => {
        const points = Array.from({ length: 121 }, (_, i) => {
          const x = variable.minimum + (span * i) / 120;
          return `${toX(x)},${toY(curve(term, x))}`;
        }).join(" ");
        return { points, colour: colours[index % colours.length] };
      }),
    [variable],
  );
  const update = (
    event: PointerEvent<SVGCircleElement>,
    termIndex: number,
    parameterIndex: number,
  ) => {
    if (readOnly || variable.terms[termIndex].locked) return;
    const svg = svgRef.current;
    if (!svg) return;
    const bounds = svg.getBoundingClientRect();
    const ratio = Math.max(
      0,
      Math.min(1, (event.clientX - bounds.left) / bounds.width),
    );
    let value = variable.minimum + ratio * span;
    const term = variable.terms[termIndex];
    if (term.kind === "gaussian" && parameterIndex === 1)
      value = Math.max(span / 400, Math.abs(value - term.parameters[0]));
    if (term.kind === "bell" && parameterIndex === 0)
      value = Math.max(span / 400, Math.abs(value - term.parameters[2]));
    onParameterChange(termIndex, parameterIndex, value);
  };
  return (
    <div className="mf-canvas-wrap">
      <div className="mf-canvas-caption">
        Drag handles directly on the membership graph. Every drag edits the
        canonical executable parameter.
      </div>
      <svg
        ref={svgRef}
        className="mf-canvas"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${variable.name} draggable membership editor`}
      >
        <line
          x1={pad}
          x2={pad}
          y1={pad}
          y2={height - pad}
          className="mf-axis"
        />
        <line
          x1={pad}
          x2={width - pad}
          y1={height - pad}
          y2={height - pad}
          className="mf-axis"
        />
        {paths.map((item, index) => (
          <polyline
            key={index}
            fill="none"
            stroke={item.colour}
            strokeWidth="2.5"
            points={item.points}
          />
        ))}
        {variable.terms.flatMap((term, termIndex) =>
          xParameters(term).map((handle) => {
            const x = Math.max(
              variable.minimum,
              Math.min(variable.maximum, handle.x),
            );
            const y = curve(term, x);
            return (
              <circle
                key={`${termIndex}-${handle.parameterIndex}`}
                className="mf-drag-handle"
                cx={toX(x)}
                cy={toY(y)}
                r="7"
                fill={colours[termIndex % colours.length]}
                tabIndex={readOnly || term.locked ? -1 : 0}
                aria-label={`${term.name} parameter ${handle.parameterIndex + 1}`}
                onPointerDown={(event) => {
                  event.currentTarget.setPointerCapture(event.pointerId);
                  update(event, termIndex, handle.parameterIndex);
                }}
                onPointerMove={(event) => {
                  if (event.currentTarget.hasPointerCapture(event.pointerId))
                    update(event, termIndex, handle.parameterIndex);
                }}
                onKeyDown={(event) => {
                  if (readOnly || term.locked) return;
                  const delta = span / 100;
                  if (event.key === "ArrowLeft")
                    onParameterChange(
                      termIndex,
                      handle.parameterIndex,
                      x - delta,
                    );
                  if (event.key === "ArrowRight")
                    onParameterChange(
                      termIndex,
                      handle.parameterIndex,
                      x + delta,
                    );
                }}
              />
            );
          }),
        )}
      </svg>
    </div>
  );
}
