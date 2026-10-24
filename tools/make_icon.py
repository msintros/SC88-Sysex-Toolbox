"""Draw the app icon: a dot-matrix toolbox on the orange LCD, in a slate bezel.

Run from anywhere:  python3 tools/make_icon.py
Writes cpp/app/resources/icon.png (1024 x 1024).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cpp" / "app" / "resources" / "icon.png"

# '#' = lit dot, '.' = unlit dot. 20 x 20 grid.
TOOLBOX = """
....................
....................
.....##########.....
.....#........#.....
.....#........#.....
...##############...
..################..
.##################.
.##################.
....................
.########..########.
.########..########.
.##################.
.##################.
.##################.
.##################.
.##################.
.##################.
....................
....................
""".split()

SIZE = 1024
SS = 4  # supersampling for smooth edges

BEZEL_TOP = (0x4a, 0x53, 0x64)
BEZEL_BOTTOM = (0x2c, 0x32, 0x3d)
LCD_FRAME = (0x16, 0x19, 0x1f)
LCD_TOP = (0xff, 0x7a, 0x14)
LCD_BOTTOM = (0xf0, 0x60, 0x00)
LIT = (0x1e, 0x0c, 0x00)
UNLIT = (0xd8, 0x55, 0x00)


def vertical_gradient(size, top, bottom):
    w, h = size
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return grad.resize((w, h))


def rounded_mask(size, box, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def main():
    s = SIZE * SS
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Slate body with a soft shadow, inset like a macOS app icon.
    inset = round(s * 0.09)
    body = (inset, inset, s - inset, s - inset)
    radius = round(s * 0.18)
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((body[0], body[1] + s * 0.012, body[2], body[3] + s * 0.012),
                                             radius=radius, fill=(0, 0, 0, 120))
    icon.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s * 0.012)))
    icon.paste(vertical_gradient((s, s), BEZEL_TOP, BEZEL_BOTTOM), (0, 0), rounded_mask((s, s), body, radius))

    # LCD glass.
    pad = round(s * 0.075)
    frame = (body[0] + pad, body[1] + pad, body[2] - pad, body[3] - pad)
    d = ImageDraw.Draw(icon)
    d.rounded_rectangle(frame, radius=round(s * 0.07), fill=LCD_FRAME)
    glass_inset = round(s * 0.022)
    glass = (frame[0] + glass_inset, frame[1] + glass_inset, frame[2] - glass_inset, frame[3] - glass_inset)
    glass_size = (glass[2] - glass[0], glass[3] - glass[1])
    icon.paste(vertical_gradient(glass_size, LCD_TOP, LCD_BOTTOM), glass[:2],
               rounded_mask(glass_size, (0, 0, *glass_size), round(s * 0.05)))

    # Dot matrix.
    cells = len(TOOLBOX)
    margin = glass_size[0] * 0.06
    pitch = (glass_size[0] - 2 * margin) / cells
    dot = pitch * 0.84
    corner = dot * 0.22
    for row, line in enumerate(TOOLBOX):
        for col, ch in enumerate(line):
            x = glass[0] + margin + col * pitch + (pitch - dot) / 2
            y = glass[1] + margin + row * pitch + (pitch - dot) / 2
            d.rounded_rectangle((x, y, x + dot, y + dot), radius=corner, fill=LIT if ch == "#" else UNLIT)

    icon = icon.resize((SIZE, SIZE), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    icon.save(OUT, optimize=True)
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
