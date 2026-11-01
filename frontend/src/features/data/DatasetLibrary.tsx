import { useState } from "react";
import { Button } from "../../components/StudioPrimitives";
import { learningDatasets, type LearningDataset } from "./learningDatasets";

export function DatasetLibrary({ disabled, onLoad }: { disabled: boolean; onLoad: (dataset: LearningDataset) => void }) {
  const [selected, setSelected] = useState(learningDatasets[0].id);
  const dataset = learningDatasets.find((item) => item.id === selected)!;
  return <details className="data-library" data-testid="dataset-library">
    <summary>Выбрать учебный набор данных</summary>
    <label className="field-label">Набор<select aria-label="Учебный набор" value={selected} disabled={disabled} onChange={(e) => setSelected(e.target.value)}>{learningDatasets.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
    <p>{dataset.description}</p>
    <p>{dataset.rows} строк · {dataset.features} признаков · {dataset.task === "regression" ? "прогноз числового значения" : "классификация"} · цель: {dataset.target}</p>
    <Button view="outlined" disabled={disabled} onClick={() => onLoad(dataset)}>Подставить набор</Button>
    <small>Заменится только черновик. Проверьте столбцы и нажмите «Далее». Все наборы здесь синтетические; они не являются исследовательскими результатами.</small>
  </details>;
}
