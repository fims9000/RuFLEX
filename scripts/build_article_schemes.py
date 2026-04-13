from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs/article/generated_figures"

CANVAS_WIDTH = 2500
CANVAS_HEIGHT = 1380
PAGE_MARGIN = 42
FRAME_WIDTH = 3
BOX_BORDER = "#111111"
BOX_FILL = "#FFFFFF"
GROUP_FILL = "#FFFFFF"
HEADER_FILL = "#FFFFFF"
TEXT_COLOR = "#111111"
SUBTEXT_COLOR = "#2A2A2A"
ARROW_COLOR = "#111111"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    generated = build_article_schemes()
    for path in generated:
        print(path)


def build_article_schemes() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        OUTPUT_DIR / "scheme1_ruflex_platform_architecture.png",
        OUTPUT_DIR / "scheme2_model_contour.png",
        OUTPUT_DIR / "scheme3_explainability_pipeline.png",
    ]
    _build_platform_architecture(outputs[0])
    _build_model_contour(outputs[1])
    _build_explainability_pipeline(outputs[2])
    return outputs


def _build_platform_architecture(output_path: Path) -> None:
    image, draw = _canvas()
    title_font = _font(64, bold=True)
    subtitle_font = _font(34)
    section_font = _font(36, bold=True)
    body_font = _font(29)
    footer_font = _font(27)

    _page_title(
        draw,
        "Архитектура платформы RuFLEX",
        "Вычислительное ядро, платформенные модули и исследовательские сервисы",
        title_font,
        subtitle_font,
    )

    backend_box = (85, 220, 700, 1180)
    platform_group = (830, 220, 2370, 1180)

    _group_box(draw, backend_box, "Вычислительное ядро", section_font)
    _group_box(draw, platform_group, "Платформенный слой RuFLEX", section_font)

    _module_box(
        draw,
        (120, 330, 665, 1110),
        "Пакет ruanfis из deep-neuro-fuzzy",
        [
            "дифференцируемые нечеткие слои",
            "вычисление активаций правил",
            "локальные блоки правил",
            "базовые процедуры обучения",
            "исполнение плоского и глубокого",
            "нечеткого модельного контура",
        ],
        body_font,
        fill=BOX_FILL,
    )

    top_row = [
        (
            (900, 330, 1340, 600),
            "Ядро платформы",
            [
                "переменные и их роли",
                "термы и функции принадлежности",
                "правила и базы правил",
                "конфигурации проектов",
            ],
        ),
        (
            (1395, 330, 1845, 600),
            "Модельный слой",
            [
                "плоская нейро-нечеткая модель",
                "глубокое нечеткое",
                "формирование признаков",
            ],
        ),
        (
            (1900, 330, 2295, 600),
            "Подсистема обучения",
            [
                "начальная инициализация",
                "поэтапное обучение",
                "уточнение структуры и параметров",
            ],
        ),
    ]
    bottom_row = [
        (
            (900, 690, 1340, 980),
            "Подсистема интерпретации",
            [
                "графики функций принадлежности",
                "активные правила",
                "скрытые концепты",
                "вклад факторов",
            ],
        ),
        (
            (1395, 690, 1845, 980),
            "Программный интерфейс",
            [
                "объект проекта",
                "сериализация и загрузка",
                "сценарии вычислительных опытов",
            ],
        ),
        (
            (1900, 690, 2295, 980),
            "Пользовательский контур",
            [
                "веб-интерфейс",
                "редактор переменных и правил",
                "экспорт артефактов статьи",
            ],
        ),
    ]

    for box, title, lines in top_row + bottom_row:
        _module_box(draw, box, title, lines, body_font)

    _arrow(draw, (700, 700), (830, 700), width=8)
    _arrow(draw, (1340, 465), (1395, 465), width=6)
    _arrow(draw, (1845, 465), (1900, 465), width=6)
    _arrow(draw, (1340, 835), (1395, 835), width=6)
    _arrow(draw, (1845, 835), (1900, 835), width=6)

    _module_box(
        draw,
        (900, 1035, 2295, 1165),
        "Выходные результаты платформы",
        [
            "обученные модели, прогнозы, метрики, отчеты, рисунки и пакет материалов статьи",
        ],
        footer_font,
        fill=GROUP_FILL,
        header_fill="#DCDCDC",
        header_ratio=0.26,
    )
    image.save(output_path, format="PNG", dpi=(300, 300))


def _build_model_contour(output_path: Path) -> None:
    image, draw = _canvas()
    title_font = _font(64, bold=True)
    subtitle_font = _font(34)
    section_font = _font(36, bold=True)
    body_font = _font(28)

    _page_title(
        draw,
        "Модельный контур RuFLEX",
        "Сравнение плоского и глубокого нечеткого режима в единой платформе",
        title_font,
        subtitle_font,
    )

    _group_box(draw, (80, 265, 760, 740), "Общий входной контур", section_font)
    _group_box(draw, (845, 155, 1675, 560), "Плоский интерпретируемый режим", section_font)
    _group_box(draw, (845, 610, 1955, 1145), "Глубокий режим построения нечетких признаков", section_font)
    _group_box(draw, (2000, 155, 2360, 740), "Общий выход", section_font)

    input_box = (120, 370, 395, 665)
    fuzz_box = (445, 370, 725, 665)
    flat_rules = (900, 255, 1265, 520)
    flat_decision = (1310, 255, 1635, 520)
    deep_rules = (900, 720, 1230, 1035)
    hidden_concepts = (1270, 720, 1600, 1035)
    spatial_block = (1640, 720, 1910, 1035)
    output_box = (2035, 355, 2320, 685)

    _module_box(
        draw,
        input_box,
        "Входные признаки",
        ["геопризнаки", "табличные переменные", "целевой контекст"],
        body_font,
    )
    _module_box(
        draw,
        fuzz_box,
        "Фаззификация",
        ["термы", "функции принадлежности", "нормированные признаки"],
        body_font,
    )
    _module_box(
        draw,
        flat_rules,
        "Плоский правиловый блок",
        ["компактная база правил", "локальный интерпретируемый вывод"],
        body_font,
        fill=GROUP_FILL,
    )
    _module_box(
        draw,
        flat_decision,
        "Плоский решающий слой",
        ["регрессия или классификация", "агрегирование правил"],
        body_font,
        fill=GROUP_FILL,
    )
    _module_box(
        draw,
        deep_rules,
        "Локальные блоки правил",
        ["ограниченная арность", "контроль роста числа правил"],
        body_font,
        fill=GROUP_FILL,
    )
    _module_box(
        draw,
        hidden_concepts,
        "Скрытые нечеткие концепты",
        ["новые признаки", "послойное представление"],
        body_font,
        fill=GROUP_FILL,
    )
    _module_box(
        draw,
        spatial_block,
        "Пространственный каркас",
        ["нечеткие свертки", "локальные окна", "дальнейшее расширение"],
        body_font,
        fill=GROUP_FILL,
    )
    _module_box(
        draw,
        output_box,
        "Итоговый вывод и интерпретация",
        ["прогноз", "метрики качества", "правила и факторы"],
        body_font,
    )

    _arrow(draw, (395, 520), (445, 520), width=7)
    _arrow(draw, (725, 470), (900, 385), width=6)
    _arrow(draw, (725, 565), (900, 865), width=6)
    _arrow(draw, (1265, 385), (1310, 385), width=6)
    _arrow(draw, (1635, 385), (2035, 455), width=6)
    _arrow(draw, (1230, 865), (1270, 865), width=6)
    _arrow(draw, (1600, 865), (1640, 865), width=6)
    _arrow(draw, (1910, 865), (2175, 685), width=6)

    image.save(output_path, format="PNG", dpi=(300, 300))


def _build_explainability_pipeline(output_path: Path) -> None:
    image, draw = _canvas()
    title_font = _font(64, bold=True)
    subtitle_font = _font(34)
    section_font = _font(36, bold=True)
    body_font = _font(28)

    _page_title(
        draw,
        "Контур интерпретации RuFLEX",
        "Переход от фаззификации объекта к правилам, концептам и отчетным материалам",
        title_font,
        subtitle_font,
    )

    _group_box(draw, (80, 270, 2360, 735), "Последовательность вычисления объяснения", section_font)
    _group_box(draw, (240, 790, 2295, 1235), "Получаемые аналитические материалы", section_font)

    stages = [
        ((110, 395, 385, 680), "Выбранный объект", ["значения признаков", "роли переменных"]),
        ((455, 395, 765, 680), "Фаззификация", ["степени принадлежности", "активные термы"]),
        ((835, 395, 1165, 680), "Активация правил", ["сырые веса правил", "нормированные веса"]),
        ((1235, 395, 1585, 680), "Скрытые концепты", ["вклад концептов", "промежуточная семантика"]),
        ((1655, 395, 2145, 680), "Итоговый вывод", ["прогноз", "вклад факторов", "вклад правил"]),
    ]
    for box, title, lines in stages:
        _module_box(draw, box, title, lines, body_font)

    for left, right in zip(stages, stages[1:]):
        _arrow(draw, (left[0][2], 540), (right[0][0], 540), width=7)

    analytic_boxes = [
        ((310, 920, 665, 1165), "Графики фаззификации", ["функции принадлежности", "локальная фаззификация"]),
        ((760, 920, 1140, 1165), "Анализ правил", ["активные правила", "цепочка правил", "веса правил"]),
        ((1235, 920, 1675, 1165), "Анализ концептов", ["скрытые концепты", "траектория концептов", "вклад решающего слоя"]),
        ((1770, 920, 2295, 1165), "Отчетные материалы", ["панель интерпретации", "отчет по проекту", "рисунки статьи"]),
    ]
    for box, title, lines in analytic_boxes:
        _module_box(draw, box, title, lines, body_font, fill=GROUP_FILL)

    _arrow(draw, (610, 680), (520, 920), width=5)
    _arrow(draw, (1000, 680), (950, 920), width=5)
    _arrow(draw, (1410, 680), (1455, 920), width=5)
    _arrow(draw, (1900, 680), (2030, 920), width=5)

    image.save(output_path, format="PNG", dpi=(300, 300))


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (PAGE_MARGIN, PAGE_MARGIN, CANVAS_WIDTH - PAGE_MARGIN, CANVAS_HEIGHT - PAGE_MARGIN),
        outline=BOX_BORDER,
        width=FRAME_WIDTH,
        fill="#FFFFFF",
    )
    return image, draw


def _page_title(
    draw: ImageDraw.ImageDraw,
    title: str,
    subtitle: str,
    title_font: ImageFont.ImageFont,
    subtitle_font: ImageFont.ImageFont,
) -> None:
    draw.text((90, 48), title, fill=TEXT_COLOR, font=title_font)
    draw.text((90, 122), subtitle, fill=SUBTEXT_COLOR, font=subtitle_font)


def _group_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    font: ImageFont.ImageFont,
) -> None:
    draw.rounded_rectangle(box, radius=12, fill=GROUP_FILL, outline=BOX_BORDER, width=3)
    header_height = 92
    title_box = (box[0], box[1], box[2], box[1] + header_height)
    draw.rounded_rectangle(title_box, radius=12, fill=HEADER_FILL, outline=BOX_BORDER, width=3)
    draw.rectangle((box[0], box[1] + header_height - 16, box[2], box[1] + header_height), fill=HEADER_FILL, outline=None)
    _center_text(draw, title_box, title, font, fill=TEXT_COLOR)


def _module_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    lines: list[str],
    font: ImageFont.ImageFont,
    *,
    fill: str = BOX_FILL,
    header_fill: str = HEADER_FILL,
    header_ratio: float = 0.27,
) -> None:
    draw.rounded_rectangle(box, radius=10, fill=fill, outline=BOX_BORDER, width=3)
    header_height = max(62, int((box[3] - box[1]) * header_ratio))
    header_box = (box[0], box[1], box[2], box[1] + header_height)
    draw.rounded_rectangle(header_box, radius=10, fill=header_fill, outline=BOX_BORDER, width=3)
    draw.rectangle((box[0], box[1] + header_height - 16, box[2], box[1] + header_height), fill=header_fill, outline=None)

    title_font = _font(font.size + 2, bold=True)
    _wrapped_text(
        draw,
        (box[0] + 20, box[1] + 16, box[2] - 20, box[1] + header_height - 12),
        title,
        title_font,
        line_gap=8,
        fill=TEXT_COLOR,
        align="center",
        vertical="center",
    )
    _wrapped_lines(
        draw,
        (box[0] + 22, box[1] + header_height + 18, box[2] - 22, box[3] - 18),
        lines,
        font,
        line_gap=12,
        fill=SUBTEXT_COLOR,
    )


def _wrapped_lines(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    lines: list[str],
    font: ImageFont.ImageFont,
    *,
    line_gap: int,
    fill: str,
) -> None:
    y = box[1]
    for line in lines:
        parts = _wrap_text(draw, line, font, box[2] - box[0])
        for part in parts:
            draw.text((box[0], y), part, fill=fill, font=font)
            y += _line_height(font) + line_gap


def _wrapped_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    *,
    line_gap: int,
    fill: str,
    align: str,
    vertical: str,
) -> None:
    lines = _wrap_text(draw, text, font, box[2] - box[0])
    total_height = len(lines) * _line_height(font) + max(0, len(lines) - 1) * line_gap
    if vertical == "center":
        y = box[1] + max(0, (box[3] - box[1] - total_height) // 2)
    else:
        y = box[1]

    for line in lines:
        width = _text_width(draw, line, font)
        if align == "center":
            x = box[0] + max(0, (box[2] - box[0] - width) // 2)
        else:
            x = box[0]
        draw.text((x, y), line, fill=fill, font=font)
        y += _line_height(font) + line_gap


def _center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    *,
    fill: str,
) -> None:
    _wrapped_text(draw, box, text, font, line_gap=6, fill=fill, align="center", vertical="center")


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _line_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Аг")
    return bbox[3] - bbox[1]


def _arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    width: int,
) -> None:
    draw.line((start, end), fill=ARROW_COLOR, width=width)
    ex, ey = end
    sx, sy = start
    dx = ex - sx
    dy = ey - sy
    if abs(dx) >= abs(dy):
        direction = 1 if dx >= 0 else -1
        points = [(ex, ey), (ex - 28 * direction, ey - 16), (ex - 28 * direction, ey + 16)]
    else:
        direction = 1 if dy >= 0 else -1
        points = [(ex, ey), (ex - 16, ey - 28 * direction), (ex + 16, ey - 28 * direction)]
    draw.polygon(points, fill=ARROW_COLOR)


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/noto/NotoSerif-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf",
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/noto/NotoSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/TTF/DejaVuSerif.ttf",
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
