"""Images of a bin above their WHOI blobs, as one PNG (what section 4 of the app shows).

    python show_blobs.py <project folder> [<bin>] [--n 12] [--seed 0]

The blob is the outline WHOI ifcb-features found in the image: the features are measured on it. Check that it
covers the particle, not the background or a bubble. Without a bin, the first bin that has blobs is shown and the
bins with blobs are listed. --seed 1, 2… picks other images. Writes figures/blobs_<bin>_seed<seed>.png.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

CELL, PAD, CAPTION, PER_ROW = 160, 8, 16, 6  # pixels


def sheet(pairs, title):
    """One image: each image above its blob, PER_ROW per row. All images get the same scale (the widest is CELL
    pixels wide), so their sizes can be compared."""
    from PIL import Image, ImageDraw
    scale = CELL / max(image.width for _, image, _ in pairs)
    size = lambda p: (max(1, round(p.width * scale)), max(1, round(p.height * scale)))
    rows = [pairs[i:i + PER_ROW] for i in range(0, len(pairs), PER_ROW)]
    heights = [max(size(image)[1] for _, image, _ in row) + CAPTION for row in rows]
    out = Image.new("RGB", (PER_ROW * (CELL + PAD) + PAD, CAPTION + PAD + sum(2 * h + PAD for h in heights)), "white")
    draw = ImageDraw.Draw(out)
    draw.text((PAD, 2), title, fill="black")
    y = CAPTION + PAD
    for row, h in zip(rows, heights):
        for k, (n, image, blob) in enumerate(row):
            x = PAD + k * (CELL + PAD)
            for top, picture, caption in ((y, image, f"ROI {n} {image.width}x{image.height}"), (y + h, blob, "blob")):
                draw.text((x, top), caption if picture is not None else "no blob", fill="black")
                if picture is not None:
                    out.paste(picture.convert("L").resize(size(image)), (x, top + CAPTION))
        y += 2 * h + PAD
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("bin", nargs="?", help="bin name, e.g. D20250601T120000_IFCB225; default: the first with blobs")
    parser.add_argument("--n", type=int, default=12, help="number of images (default 12)")
    parser.add_argument("--seed", type=int, default=0, help="change it to see other images")
    args = parser.parse_args()

    root = os.path.abspath(args.project)
    with_blobs = project.bins_with_blobs(root)
    if not with_blobs:
        sys.exit("No blobs yet: they are made by the feature extraction (extract_features.py).")
    if args.bin and args.bin not in with_blobs:
        sys.exit(f"No blobs for {args.bin}. Bins with blobs: {with_blobs[0]} … {with_blobs[-1]} ({len(with_blobs)})")
    bin_name = args.bin or with_blobs[0]
    if not args.bin:
        print(f"{len(with_blobs)} bins with blobs, from {with_blobs[0]} to {with_blobs[-1]}. Showing {bin_name}.")
    pairs = project.images_and_blobs(root, bin_name, n=args.n, seed=args.seed)
    os.makedirs(os.path.join(root, "figures"), exist_ok=True)
    path = os.path.join(root, "figures", f"blobs_{bin_name}_seed{args.seed}.png")
    sheet(pairs, f"{os.path.basename(root)} - {bin_name} - images above their blobs (seed {args.seed})").save(path)
    print(f"Written: {path}")
    if os.name == "nt" and sys.stdout.isatty():
        os.startfile(path)  # opens it in the image viewer


if __name__ == "__main__":
    main()
