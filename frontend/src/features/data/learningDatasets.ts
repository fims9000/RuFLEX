export type LearningDataset = {
  id: string; title: string; description: string; csv: string;
  target: string; task: "regression" | "binary_classification";
  rows: number; features: number; idColumns: string[];
};

// Small deterministic teaching fixtures, not field measurements or benchmarks.
function build(id: string, title: string, description: string, features: string[], target: string,
  task: LearningDataset["task"], count: number, make: (i: number) => (number | string)[]): LearningDataset {
  return { id, title, description, target, task, rows: count, features: features.length, idColumns: ["sample_id"],
    csv: [ ["sample_id", ...features, target].join(","), ...Array.from({ length: count }, (_, i) =>
      [`demo-${id}-${i + 1}`, ...make(i)].join(",")) ].join("\n") + "\n" };
}

export const learningDatasets: LearningDataset[] = [
  build("soil", "Просадка грунта · учебная имитация", "Оценка условной осадки по нагрузке, влажности и свойствам грунта. Не геотехнический расчёт и не измерения.",
    ["Влажность_проц", "Нагрузка_кПа", "Пористость", "Плотность_т_м3", "Глубина_м", "Глина_проц", "Песок_проц", "Уровень_воды_м", "Тип_грунта"], "Осадка_мм", "regression", 144, (i) => {
      const moisture = 8 + (i * 7) % 35, load = 40 + (i * 13) % 210, porosity = .28 + ((i * 11) % 31) / 100;
      const density = 1.3 + ((i * 3) % 65) / 100, depth = 1 + (i % 12), clay = 10 + ((i * 17) % 50), sand = 90 - clay;
      const water = .5 + ((i * 19) % 45) / 10, type = ["суглинок", "песок", "глина"][i % 3];
      const settlement = load * porosity * .1 + moisture * .12 + clay * .035 - density * 1.2 + depth * .15 + ((i * 23) % 13) * .07;
      return [moisture, load, porosity.toFixed(2), density.toFixed(2), depth, clay, sand, water.toFixed(1), type, settlement.toFixed(3)];
    }),
  build("equipment", "Состояние оборудования · учебный", "Классификация условного состояния оборудования по десяти параметрам. Синтетические данные.",
    ["Температура", "Вибрация", "Давление", "Обороты", "Нагрузка", "Износ", "Часы_работы", "Охлаждение", "Влажность", "Режим"], "Неисправность", "binary_classification", 160, (i) => {
      const temp = 35 + (i * 11) % 65, vibration = .3 + ((i * 7) % 65) / 10, pressure = 2 + ((i * 3) % 45) / 10;
      const rpm = 700 + (i * 43) % 1700, load = 20 + (i * 17) % 80, wear = (i * 13) % 100;
      return [temp, vibration.toFixed(1), pressure.toFixed(1), rpm, load, wear, 100 + i * 37, 10 + (i * 9) % 60, 25 + (i * 5) % 65, i % 2 ? "рабочий" : "экономичный", Number(temp + vibration * 8 + wear * .35 + load * .2 > 130)];
    }),
  build("energy", "Энергопотребление здания · учебный", "Прогноз условного расхода энергии по восьми параметрам. Синтетические данные, не энергетический аудит.",
    ["Площадь_м2", "Этажи", "Температура_снаружи", "Люди", "Часы_работы", "Остекление_проц", "Утепление", "Тип_здания"], "Расход_кВтч", "regression", 128, (i) => {
      const area = 80 + (i * 37) % 920, floors = 1 + i % 8, temp = -15 + (i * 7) % 46, people = 5 + (i * 11) % 100;
      const hours = 4 + i % 16, glass = 10 + (i * 13) % 60, insulation = 1 + i % 5;
      return [area, floors, temp, people, hours, glass, insulation, i % 2 ? "офис" : "склад", (area * .11 + Math.max(0, 20 - temp) * 3 + people * .4 + hours * 2 + glass * .5 - insulation * 4).toFixed(2)];
    }),
];

// Exact UTF-8 bytes identify these teaching fixtures after save/reopen.
export const learningDatasetHashes: Record<string, string> = {
  soil: "5347075f42ed85ba90c5d809ade1f1942a2f90dd62d6396e67e8640299a10721",
  equipment: "a15e343a7decfe2353ea6cafee804d289fa6bc78d7d4d183456d81f73c3d4878",
  energy: "fb195510c7cfe381643d339a27c8574e82680f398621a3d1cd627ea16986cdb9",
};
export function learningDatasetForHash(hash: string | undefined) {
  return learningDatasets.find((item) => learningDatasetHashes[item.id] === hash);
}
