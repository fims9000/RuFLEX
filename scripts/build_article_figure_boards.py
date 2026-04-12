from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser(description="Build article-ready figure boards from one asset directory.")
    parser.add_argument("--asset-dir", required=True, help="Directory with generated article asset PNGs.")
    parser.add_argument("--title", required=True, help="Board title.")
    parser.add_argument(
        "--output-name",
        default="article_figure_board.png",
        help="Output filename inside the asset directory.",
    )
    args = parser.parse_args()

    asset_dir = Path(args.asset_dir).expanduser().resolve()
    output_path = asset_dir / args.output_name
    build_figure_board(asset_dir=asset_dir, title=args.title, output_path=output_path)
    print(output_path)


def build_figure_board(*, asset_dir: Path, title: str, output_path: Path) -> None:
    panels = [
        ("Results Overview", asset_dir / "results_overview.png"),
        ("Training History", asset_dir / "best_training_history.png"),
        ("Top Rules", asset_dir / "best_sample_top_rules.png"),
        ("Hidden Concepts", asset_dir / "best_sample_hidden_concepts.png"),
    ]
    available_panels = [(label, path) for label, path in panels if path.exists()]
    if not available_panels:
        raise FileNotFoundError(f"No figure panels were found in {asset_dir}")

    canvas_width = 1800
    margin = 40
    gap = 24
    title_height = 120
    panel_width = (canvas_width - margin * 2 - gap) // 2
    panel_height = 520
    rows = (len(available_panels) + 1) // 2
    canvas_height = title_height + margin + rows * panel_height + max(0, rows - 1) * gap + margin

    board = Image.new("RGB", (canvas_width, canvas_height), color="#F6F4EF")
    draw = ImageDraw.Draw(board)
    title_font = _font(42)
    label_font = _font(24)
    draw.text((margin, 28), title, fill="#1F2933", font=title_font)
    draw.text((margin, 76), str(asset_dir.name), fill="#52606D", font=_font(20))

    for index, (label, path) in enumerate(available_panels):
        row = index // 2
        column = index % 2
        x0 = margin + column * (panel_width + gap)
        y0 = title_height + row * (panel_height + gap)
        _paste_panel(
            board=board,
            draw=draw,
            image_path=path,
            panel_label=label,
            panel_box=(x0, y0, panel_width, panel_height),
            label_font=label_font,
        )

    board.save(output_path, format="PNG")


def _paste_panel(
    *,
    board: Image.Image,
    draw: ImageDraw.ImageDraw,
    image_path: Path,
    panel_label: str,
    panel_box: tuple[int, int, int, int],
    label_font: ImageFont.ImageFont,
) -> None:
    x0, y0, width, height = panel_box
    outer_box = (x0, y0, x0 + width, y0 + height)
    draw.rounded_rectangle(outer_box, radius=18, fill="#FFFFFF", outline="#D9E2EC", width=2)
    draw.text((x0 + 18, y0 + 14), panel_label, fill="#102A43", font=label_font)

    image = Image.open(image_path).convert("RGB")
    image.thumbnail((width - 36, height - 68))
    image_x = x0 + (width - image.width) // 2
    image_y = y0 + 54 + (height - 68 - image.height) // 2
    board.paste(image, (image_x, image_y))


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ):
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
