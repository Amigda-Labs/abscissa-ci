from pathlib import Path
from math import floor, ceil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
CANVAS_W = 1600
CANVAS_H = 1200

PAGE_BG = "#f8f7f2"
GRID_MINOR = "#ece7db"
GRID_MAJOR = "#ddd5c6"
INK = "#252729"
DIM = "#51545a"
FLOOR = "#f2eee5"
WALL = "#2b2d30"
PARTITION = "#70757c"
WINDOW = "#4c8fb7"
WHITE = "#ffffff"


def load_font(size, bold=False):
    if bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


FONT_TITLE = load_font(36, bold=True)
FONT_SUBTITLE = load_font(20)
FONT_LABEL = load_font(23, bold=True)
FONT_SMALL = load_font(16)
FONT_TINY = load_font(13)


PLANS = [
    {
        "slug": "l_shape",
        "title": "L SHAPE FLOOR PLAN",
        "polygon": [(0, 0), (12, 0), (12, 5), (7, 5), (7, 9), (0, 9)],
        "dims": [
            {"kind": "h", "x1": 0, "x2": 12, "y": -1.25, "ref_y1": 0, "ref_y2": 0, "label": "12.00 m"},
            {"kind": "v", "x": -1.25, "y1": 0, "y2": 9, "ref_x1": 0, "ref_x2": 0, "label": "9.00 m"},
            {"kind": "v", "x": 13.00, "y1": 0, "y2": 5, "ref_x1": 12, "ref_x2": 12, "label": "5.00 m"},
            {"kind": "v", "x": 13.72, "y1": 5, "y2": 9, "ref_x1": 12, "ref_x2": 7, "label": "4.00 m"},
            {"kind": "h", "x1": 0, "x2": 7, "y": 10.15, "ref_y1": 9, "ref_y2": 9, "label": "7.00 m"},
            {"kind": "h", "x1": 7, "x2": 12, "y": 10.15, "ref_y1": 9, "ref_y2": 5, "label": "5.00 m"},
        ],
        "windows": [
            ((1.2, 0), (4.6, 0)),
            ((8.2, 0), (10.8, 0)),
            ((0, 2.0), (0, 4.8)),
            ((0, 6.0), (0, 8.0)),
            ((12, 1.4), (12, 3.8)),
        ],
    },
    {
        "slug": "rectangular",
        "title": "RECTANGULAR FLOOR PLAN",
        "polygon": [(0, 0), (14, 0), (14, 8), (0, 8)],
        "dims": [
            {"kind": "h", "x1": 0, "x2": 14, "y": -1.20, "ref_y1": 0, "ref_y2": 0, "label": "14.00 m"},
            {"kind": "v", "x": -1.20, "y1": 0, "y2": 8, "ref_x1": 0, "ref_x2": 0, "label": "8.00 m"},
            {"kind": "h", "x1": 0, "x2": 14, "y": 9.20, "ref_y1": 8, "ref_y2": 8, "label": "14.00 m"},
            {"kind": "v", "x": 15.20, "y1": 0, "y2": 8, "ref_x1": 14, "ref_x2": 14, "label": "8.00 m"},
        ],
        "windows": [
            ((2.0, 0), (5.6, 0)),
            ((8.2, 0), (12.0, 0)),
            ((0, 2.0), (0, 5.8)),
            ((14, 2.0), (14, 5.8)),
            ((4.4, 8), (9.6, 8)),
        ],
    },
    {
        "slug": "rectangular_with_hole",
        "title": "RECTANGULAR FLOOR PLAN WITH VOID",
        "polygon": [(0, 0), (16, 0), (16, 10), (0, 10)],
        "holes": [
            [(5.5, 3.5), (10.5, 3.5), (10.5, 6.5), (5.5, 6.5)],
        ],
        "dims": [
            {"kind": "h", "x1": 0, "x2": 16, "y": -1.20, "ref_y1": 0, "ref_y2": 0, "label": "16.00 m"},
            {"kind": "v", "x": -1.20, "y1": 0, "y2": 10, "ref_x1": 0, "ref_x2": 0, "label": "10.00 m"},
            {"kind": "h", "x1": 0, "x2": 5.5, "y": 11.20, "ref_y1": 10, "ref_y2": 6.5, "label": "5.50 m"},
            {"kind": "h", "x1": 5.5, "x2": 10.5, "y": 11.20, "ref_y1": 6.5, "ref_y2": 6.5, "label": "5.00 m"},
            {"kind": "h", "x1": 10.5, "x2": 16, "y": 11.20, "ref_y1": 6.5, "ref_y2": 10, "label": "5.50 m"},
            {"kind": "v", "x": 17.20, "y1": 0, "y2": 3.5, "ref_x1": 16, "ref_x2": 10.5, "label": "3.50 m"},
            {"kind": "v", "x": 17.20, "y1": 3.5, "y2": 6.5, "ref_x1": 10.5, "ref_x2": 10.5, "label": "3.00 m"},
            {"kind": "v", "x": 17.20, "y1": 6.5, "y2": 10, "ref_x1": 10.5, "ref_x2": 16, "label": "3.50 m"},
        ],
        "windows": [
            ((2.0, 0), (5.6, 0)),
            ((10.4, 0), (14.0, 0)),
            ((0, 2.4), (0, 5.2)),
            ((0, 6.3), (0, 8.3)),
            ((16, 2.4), (16, 5.2)),
            ((16, 6.3), (16, 8.3)),
            ((4.2, 10), (7.2, 10)),
            ((8.8, 10), (11.8, 10)),
        ],
    },
    {
        "slug": "t_shape",
        "title": "T SHAPE FLOOR PLAN",
        "polygon": [(2, 0), (6, 0), (6, 5), (9, 5), (9, 8), (-1, 8), (-1, 5), (2, 5)],
        "dims": [
            {"kind": "h", "x1": -1, "x2": 9, "y": 9.35, "ref_y1": 8, "ref_y2": 8, "label": "10.00 m"},
            {"kind": "h", "x1": -1, "x2": 2, "y": 8.65, "ref_y1": 8, "ref_y2": 5, "label": "3.00 m"},
            {"kind": "h", "x1": 2, "x2": 6, "y": 8.65, "ref_y1": 5, "ref_y2": 5, "label": "4.00 m"},
            {"kind": "h", "x1": 6, "x2": 9, "y": 8.65, "ref_y1": 5, "ref_y2": 8, "label": "3.00 m"},
            {"kind": "h", "x1": 2, "x2": 6, "y": -0.95, "ref_y1": 0, "ref_y2": 0, "label": "4.00 m"},
            {"kind": "v", "x": 10.15, "y1": 0, "y2": 8, "ref_x1": 6, "ref_x2": 9, "label": "8.00 m"},
            {"kind": "v", "x": 1.20, "y1": 0, "y2": 5, "ref_x1": 2, "ref_x2": 2, "label": "5.00 m"},
            {"kind": "v", "x": -1.85, "y1": 5, "y2": 8, "ref_x1": -1, "ref_x2": -1, "label": "3.00 m"},
        ],
        "windows": [
            ((2.6, 0), (5.4, 0)),
            ((-0.4, 8), (2.2, 8)),
            ((3.8, 8), (6.2, 8)),
            ((6.8, 8), (8.4, 8)),
            ((9, 5.6), (9, 7.4)),
        ],
    },
    {
        "slug": "plus_shape",
        "title": "PLUS SHAPE FLOOR PLAN",
        "polygon": [(3, 0), (7, 0), (7, 3), (10, 3), (10, 7), (7, 7), (7, 10), (3, 10), (3, 7), (0, 7), (0, 3), (3, 3)],
        "dims": [
            {"kind": "h", "x1": 0, "x2": 10, "y": 11.35, "ref_y1": 7, "ref_y2": 7, "label": "10.00 m"},
            {"kind": "h", "x1": 0, "x2": 3, "y": 10.62, "ref_y1": 7, "ref_y2": 10, "label": "3.00 m"},
            {"kind": "h", "x1": 3, "x2": 7, "y": 10.62, "ref_y1": 10, "ref_y2": 10, "label": "4.00 m"},
            {"kind": "h", "x1": 7, "x2": 10, "y": 10.62, "ref_y1": 10, "ref_y2": 7, "label": "3.00 m"},
            {"kind": "h", "x1": 3, "x2": 7, "y": -0.90, "ref_y1": 0, "ref_y2": 0, "label": "4.00 m"},
            {"kind": "v", "x": 11.35, "y1": 0, "y2": 10, "ref_x1": 7, "ref_x2": 7, "label": "10.00 m"},
            {"kind": "v", "x": 10.62, "y1": 0, "y2": 3, "ref_x1": 7, "ref_x2": 10, "label": "3.00 m"},
            {"kind": "v", "x": 10.62, "y1": 3, "y2": 7, "ref_x1": 10, "ref_x2": 10, "label": "4.00 m"},
            {"kind": "v", "x": 10.62, "y1": 7, "y2": 10, "ref_x1": 10, "ref_x2": 7, "label": "3.00 m"},
            {"kind": "v", "x": -0.90, "y1": 3, "y2": 7, "ref_x1": 0, "ref_x2": 0, "label": "4.00 m"},
        ],
        "windows": [
            ((3.6, 0), (6.4, 0)),
            ((3.6, 10), (6.4, 10)),
            ((0, 3.6), (0, 6.4)),
            ((10, 3.6), (10, 6.4)),
        ],
    },
]


def all_reference_points(plan):
    points = list(plan["polygon"])
    for hole in plan.get("holes", []):
        points.extend(hole)
    for dim in plan["dims"]:
        if dim["kind"] == "h":
            points.extend([(dim["x1"], dim["y"]), (dim["x2"], dim["y"])])
            points.extend([(dim["x1"], dim["ref_y1"]), (dim["x2"], dim["ref_y2"])])
        else:
            points.extend([(dim["x"], dim["y1"]), (dim["x"], dim["y2"])])
            points.extend([(dim["ref_x1"], dim["y1"]), (dim["ref_x2"], dim["y2"])])
    return points


def make_transform(plan):
    points = all_reference_points(plan)
    min_x = min(x for x, _ in points) - 0.65
    max_x = max(x for x, _ in points) + 0.65
    min_y = min(y for _, y in points) - 0.65
    max_y = max(y for _, y in points) + 0.65

    box_left, box_top, box_right, box_bottom = 130, 150, 1470, 1000
    scale = min((box_right - box_left) / (max_x - min_x), (box_bottom - box_top) / (max_y - min_y))
    drawn_w = (max_x - min_x) * scale
    drawn_h = (max_y - min_y) * scale
    offset_x = box_left + ((box_right - box_left) - drawn_w) / 2
    offset_y = box_top + ((box_bottom - box_top) - drawn_h) / 2

    def transform(point):
        x, y = point
        return (offset_x + (x - min_x) * scale, offset_y + (max_y - y) * scale)

    return transform, (min_x, min_y, max_x, max_y), scale


def draw_centered_text(draw, center, text, font, fill=INK, pad=8, rotated=False):
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    if not rotated:
        x = center[0] - text_w / 2
        y = center[1] - text_h / 2
        box = [x - pad, y - pad, x + text_w + pad, y + text_h + pad]
        draw.rounded_rectangle(box, radius=5, fill=WHITE, outline="#d6d2ca")
        draw.text((x, y), text, font=font, fill=fill)
        return tuple(box)

    label = Image.new("RGBA", (text_w + pad * 2, text_h + pad * 2), (255, 255, 255, 0))
    label_draw = ImageDraw.Draw(label)
    label_draw.rounded_rectangle([0, 0, label.width - 1, label.height - 1], radius=5, fill=(255, 255, 255, 246), outline=(214, 210, 202, 255))
    label_draw.text((pad, pad), text, font=font, fill=fill)
    label = label.rotate(90, expand=True)
    paste = (int(center[0] - label.width / 2), int(center[1] - label.height / 2))
    return label, paste


def draw_tick(draw, point, scale):
    x, y = point
    length = max(8, min(16, scale * 0.16))
    draw.line([(x - length, y + length), (x + length, y - length)], fill=DIM, width=3)


def draw_dimension_h(draw, transform, dim, scale, label_boxes):
    p1 = transform((dim["x1"], dim["y"]))
    p2 = transform((dim["x2"], dim["y"]))
    r1 = transform((dim["x1"], dim["ref_y1"]))
    r2 = transform((dim["x2"], dim["ref_y2"]))
    draw.line([r1, p1], fill=DIM, width=2)
    draw.line([r2, p2], fill=DIM, width=2)
    draw.line([p1, p2], fill=DIM, width=2)
    draw_tick(draw, p1, scale)
    draw_tick(draw, p2, scale)
    center = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    label_boxes.append(draw_centered_text(draw, center, dim["label"], FONT_LABEL))


def draw_dimension_v(base, draw, transform, dim, scale, label_boxes):
    p1 = transform((dim["x"], dim["y1"]))
    p2 = transform((dim["x"], dim["y2"]))
    r1 = transform((dim["ref_x1"], dim["y1"]))
    r2 = transform((dim["ref_x2"], dim["y2"]))
    draw.line([r1, p1], fill=DIM, width=2)
    draw.line([r2, p2], fill=DIM, width=2)
    draw.line([p1, p2], fill=DIM, width=2)
    draw_tick(draw, p1, scale)
    draw_tick(draw, p2, scale)
    center = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    label, paste = draw_centered_text(draw, center, dim["label"], FONT_LABEL, rotated=True)
    base.alpha_composite(label, dest=paste)
    label_boxes.append((paste[0], paste[1], paste[0] + label.width, paste[1] + label.height))


def draw_window(draw, transform, start, end, scale):
    p1 = transform(start)
    p2 = transform(end)
    gap_width = int(max(8, min(14, scale * 0.18)))
    draw.line([p1, p2], fill=WHITE, width=gap_width)
    draw.line([p1, p2], fill=WINDOW, width=max(2, gap_width // 4))


def draw_grid(draw, transform, bounds):
    min_x, min_y, max_x, max_y = bounds
    for x in range(floor(min_x), ceil(max_x) + 1):
        p1 = transform((x, min_y))
        p2 = transform((x, max_y))
        draw.line([p1, p2], fill=GRID_MAJOR if x % 5 == 0 else GRID_MINOR, width=1)
    for y in range(floor(min_y), ceil(max_y) + 1):
        p1 = transform((min_x, y))
        p2 = transform((max_x, y))
        draw.line([p1, p2], fill=GRID_MAJOR if y % 5 == 0 else GRID_MINOR, width=1)


def draw_title_block(draw, plan):
    x1, y1, x2, y2 = 760, 1030, 1545, 1138
    draw.rectangle([x1, y1, x2, y2], outline=INK, width=2, fill="#fbfaf7")
    draw.line([(x1, y1 + 35), (x2, y1 + 35)], fill=INK, width=1)
    draw.line([(x1 + 385, y1), (x1 + 385, y2)], fill=INK, width=1)
    draw.text((x1 + 16, y1 + 9), "ABSCISSA CI", font=FONT_SMALL, fill=INK)
    draw.text((x1 + 401, y1 + 9), "TRAINING FLOOR PLAN", font=FONT_SMALL, fill=INK)
    draw.text((x1 + 16, y1 + 50), plan["title"], font=FONT_SMALL, fill=INK)
    draw.text((x1 + 401, y1 + 50), "DIMENSIONS IN METERS", font=FONT_SMALL, fill=INK)
    draw.text((x1 + 16, y1 + 81), "DRAFT REFERENCE", font=FONT_TINY, fill=DIM)
    draw.text((x1 + 401, y1 + 81), "HUMAN REVIEW REQUIRED", font=FONT_TINY, fill=DIM)


def draw_north_arrow(draw):
    cx, cy = 1450, 118
    draw.polygon([(cx, cy - 35), (cx - 12, cy + 18), (cx, cy + 10), (cx + 12, cy + 18)], fill=INK)
    bbox = draw.textbbox((0, 0), "N", font=FONT_SMALL)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, cy + 26), "N", font=FONT_SMALL, fill=INK)


def draw_scale_bar(draw):
    x, y = 90, 1090
    segment = 48
    for i in range(4):
        fill = INK if i % 2 == 0 else WHITE
        draw.rectangle([x + i * segment, y, x + (i + 1) * segment, y + 14], fill=fill, outline=INK)
    draw.text((x, y + 23), "0", font=FONT_TINY, fill=INK)
    draw.text((x + segment * 2 - 8, y + 23), "2 m", font=FONT_TINY, fill=INK)
    draw.text((x + segment * 4 - 12, y + 23), "4 m", font=FONT_TINY, fill=INK)


def draw_plan(plan):
    image = Image.new("RGBA", (CANVAS_W, CANVAS_H), PAGE_BG)
    draw = ImageDraw.Draw(image)

    draw.rectangle([42, 42, CANVAS_W - 42, CANVAS_H - 42], outline=INK, width=3)
    draw.rectangle([57, 57, CANVAS_W - 57, CANVAS_H - 57], outline="#b8b1a4", width=1)

    title_bbox = draw.textbbox((0, 0), plan["title"], font=FONT_TITLE)
    draw.text(((CANVAS_W - (title_bbox[2] - title_bbox[0])) / 2, 58), plan["title"], font=FONT_TITLE, fill=INK)
    subtitle = "Rectilinear orthogonal footprint - dimensions shown in meters"
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=FONT_SUBTITLE)
    draw.text(((CANVAS_W - (subtitle_bbox[2] - subtitle_bbox[0])) / 2, 103), subtitle, font=FONT_SUBTITLE, fill=DIM)

    transform, bounds, scale = make_transform(plan)
    draw_grid(draw, transform, bounds)

    polygon = [transform(point) for point in plan["polygon"]]
    shadow = [(x + 8, y + 8) for x, y in polygon]
    draw.polygon(shadow, fill="#d2cabc")
    draw.polygon(polygon, fill=FLOOR)
    closed = polygon + [polygon[0]]
    draw.line(closed, fill=WALL, width=max(14, int(scale * 0.22)), joint="curve")
    draw.line(closed, fill="#111111", width=2)

    for hole in plan.get("holes", []):
        hole_polygon = [transform(point) for point in hole]
        draw.polygon(hole_polygon, fill=PAGE_BG)
        draw.line(hole_polygon + [hole_polygon[0]], fill=WALL, width=max(14, int(scale * 0.22)), joint="curve")
        draw.line(hole_polygon + [hole_polygon[0]], fill="#111111", width=2)

    for start, end in plan["windows"]:
        draw_window(draw, transform, start, end, scale)

    label_boxes = []
    for dim in plan["dims"]:
        if dim["kind"] == "h":
            draw_dimension_h(draw, transform, dim, scale, label_boxes)
        else:
            draw_dimension_v(image, draw, transform, dim, scale, label_boxes)

    draw_north_arrow(draw)
    draw_scale_bar(draw)
    draw_title_block(draw, plan)

    output = ROOT / f"{plan['slug']}_floor_plan.png"
    image.convert("RGB").save(output, quality=96)
    return output


def main():
    for plan in PLANS:
        path = draw_plan(plan)
        print(path)


if __name__ == "__main__":
    main()
