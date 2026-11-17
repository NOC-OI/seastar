"""Draw ifcb_app.ico: IFCB instrument -> arrow -> grid of plankton vignettes (EcoTaxa)."""
from PIL import Image, ImageDraw

S = 1024
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)

# Background: sea gradient in a rounded square
bg = Image.new("RGBA", (S, S))
bd = ImageDraw.Draw(bg)
for y in range(S):
    t = y / S
    bd.line([0, y, S, y], fill=(int(40 + 10 * t), int(150 - 60 * t), int(190 - 50 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([16, 16, S - 16, S - 16], radius=190, fill=255)
im.paste(bg, (0, 0), mask)

# IFCB: tall black cylinder with an open cage on top
INK, EDGE = (22, 26, 30, 255), (70, 80, 88, 255)
x0, x1 = 150, 370
d.rounded_rectangle([x0, 420, x1, 900], radius=26, fill=INK)            # body
for y in range(470, 880, 62):                                            # body segments
    d.line([x0 + 18, y, x1 - 18, y], fill=EDGE, width=8)
d.rectangle([x0 - 14, 395, x1 + 14, 435], fill=INK)                      # collar
d.rectangle([x0 - 14, 150, x1 + 14, 190], fill=INK)                      # cage top ring
for x in [round(x0 - 4 + i * (x1 - 14 - x0) / 3) for i in range(4)]:  # 4 cage bars, evenly spaced
    d.rectangle([x, 170, x + 22, 410], fill=INK)

# Arrow from the instrument to the vignettes
W = (255, 255, 255, 255)
d.arc([300, 120, 720, 560], start=200, end=330, fill=W, width=44)
d.polygon([(700, 190), (610, 150), (650, 262)], fill=W)

# EcoTaxa side: 2x2 grid of white vignettes, each with a plankton silhouette
cells = [(560, 400), (780, 400), (560, 620), (780, 620)]
for i, (cx, cy) in enumerate(cells):
    d.rounded_rectangle([cx - 95, cy - 95, cx + 95, cy + 95], radius=28, fill=(245, 250, 252, 255))
    if i == 0:   # diatom (pennate)
        d.ellipse([cx - 70, cy - 26, cx + 70, cy + 26], fill=INK)
        d.ellipse([cx - 50, cy - 10, cx + 50, cy + 10], fill=(150, 160, 168, 255))
    elif i == 1: # dinoflagellate (spiky diamond)
        d.polygon([(cx, cy - 75), (cx + 50, cy), (cx, cy + 75), (cx - 50, cy)], fill=INK)
        d.line([cx - 60, cy + 10, cx + 60, cy - 10], fill=INK, width=12)
    elif i == 2: # round cell
        d.ellipse([cx - 55, cy - 55, cx + 55, cy + 55], fill=INK)
        d.ellipse([cx - 20, cy - 30, cx + 10, cy], fill=(150, 160, 168, 255))
    else:        # chain
        for k in (-50, 0, 50):
            d.ellipse([cx + k - 26, cy - 26, cx + k + 26, cy + 26], fill=INK)
    # validation tick on the last one, like an annotated vignette
d.ellipse([835, 675, 905, 745], fill=(46, 160, 90, 255))
d.line([(852, 712), (866, 726), (890, 696)], fill=W, width=12)

im.save("ifcb_app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
im.resize((256, 256), Image.LANCZOS).save("../docs/ifcb_app_icon.png")  # the icon shown in the README
