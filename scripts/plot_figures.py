#!/usr/bin/env python3
"""Draw the recorded residual-fan order percentages, without running experiments."""
import argparse
import csv
import json
import shutil
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path, delimiter=","):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def canvas(width, height, box, fontsize=8):
    """Canvas and axis geometry in PDF points, measured in the original PDF."""
    fig = plt.figure(figsize=(width / 72, height / 72))
    left, bottom, axis_width, axis_height = box
    ax = fig.add_axes([left / width, bottom / height,
                       axis_width / width, axis_height / height])
    ax.tick_params(direction="in", length=2.5, width=.4, pad=3,
                   labelsize=fontsize)
    for spine in ax.spines.values():
        spine.set_linewidth(.4)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, name, output, paper_figures):
    output.mkdir(parents=True, exist_ok=True)
    target = output / (name + ".pdf")
    fig.savefig(target, format="pdf", metadata={"Creator": None,
                                               "Producer": None,
                                               "CreationDate": None,
                                               "ModDate": None})
    plt.close(fig)
    if paper_figures is not None:
        paper_figures.mkdir(parents=True, exist_ok=True)
        if target.resolve() != (paper_figures / target.name).resolve():
            shutil.copyfile(target, paper_figures / target.name)
    print(json.dumps({"asset": target.name,
                      "size_bp": [round(v * 72, 5) for v in fig.get_size_inches()]}))


def configure_fonts(font_dir, temporary):
    """Resolve the manuscript family; convert CFF outlines for valid Type-42 PDFs.

    TeX's Type-1 body and these OpenType outlines are the same Linux Libertine
    family. Conversion is only a temporary font-format adaptation, not a
    distributed replacement font; advance widths and Unicode maps are retained.
    """
    import subprocess
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont
    sources = []
    for name in ("LinLibertine_R.otf", "LinLibertine_RI.otf"):
        if font_dir is not None:
            source = font_dir / name
        else:
            installed = [Path(f.fname) for f in font_manager.fontManager.ttflist
                         if Path(f.fname).name == name]
            if installed:
                source = installed[0]
            elif shutil.which("kpsewhich"):
                result = subprocess.run(["kpsewhich", name], check=True,
                                        capture_output=True, text=True)
                source = Path(result.stdout.strip())
            else:
                raise RuntimeError("Install Linux Libertine, put kpsewhich on PATH, "
                                   "or pass --font-dir with its OTF files.")
        if not source.is_file():
            raise FileNotFoundError(source)
        original = TTFont(source)
        glyph_set = original.getGlyphSet()
        order = original.getGlyphOrder()
        glyphs = {}
        for glyph_name in order:
            pen = TTGlyphPen(glyph_set)
            glyph_set[glyph_name].draw(
                Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
            glyphs[glyph_name] = pen.glyph()
        builder = FontBuilder(original["head"].unitsPerEm, isTTF=True)
        builder.setupGlyphOrder(order)
        builder.setupCharacterMap(original.getBestCmap())
        builder.setupGlyf(glyphs)
        builder.setupHorizontalMetrics(original["hmtx"].metrics)
        builder.setupHorizontalHeader(ascent=original["hhea"].ascent,
                                      descent=original["hhea"].descent)
        builder.setupOS2()
        builder.font["OS/2"] = original["OS/2"]
        builder.font["name"] = original["name"]
        builder.setupPost(italicAngle=original["post"].italicAngle)
        builder.setupMaxp()
        builder.setupHead(macStyle=original["head"].macStyle,
                          created=original["head"].created,
                          modified=original["head"].modified)
        converted = Path(temporary) / (source.stem + ".ttf")
        builder.save(converted)
        if TTFont(converted)["hmtx"].metrics != original["hmtx"].metrics:
            raise ValueError("Font conversion changed glyph advance widths.")
        font_manager.fontManager.addfont(converted)
        sources.append(str(source))
    family = font_manager.FontProperties(fname=converted).get_name()
    plt.rcParams.update({
        "font.family": family, "font.size": 8.97,
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "pdf.use14corefonts": False, "text.usetex": False,
        "mathtext.fontset": "custom", "mathtext.rm": family,
        "mathtext.it": family + ":italic", "mathtext.bf": family,
        "mathtext.fallback": None, "axes.unicode_minus": True,
        "axes.labelpad": 5, "legend.fontsize": 8.97,
    })
    print(json.dumps({"font_family": family, "font_files": sources,
                      "temporary_format": "TrueType; original hmtx retained"}))

def main():
    import math
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--output", type=Path, default=ROOT / "figures")
    parser.add_argument("--paper-figures", type=Path)
    parser.add_argument("--font-dir", type=Path)
    args = parser.parse_args()
    rows = read_rows(args.results / "packets.csv")
    ks = [int(row["branches"]) for row in rows]
    # Same decimal rendering as tables.py and the original packet-orders.dat.
    percentages = [float(format(100 * float(row["repair_retained_fraction"]),
                                ".12g")) for row in rows]
    for row in rows:
        k = int(row["branches"])
        unrestricted = math.factorial(2 * k) // 2**k
        repaired = math.factorial(k - 1) * sum(
            math.factorial(k + m) // (2**m * math.factorial(m))
            for m in range(k))
        if (int(row["unrestricted_orders"]) != unrestricted
                or int(row["repaired_orders"]) != repaired):
            raise ValueError("Recorded order counts disagree with manuscript formulas.")
    # FreeType can retain open font handles in its render cache on Windows.
    with tempfile.TemporaryDirectory(prefix="libertine-plot-",
                                     ignore_cleanup_errors=True) as temporary:
        configure_fonts(args.font_dir, temporary)
        fig, ax = canvas(425, 253, (37.0, 27.0, 383.57027, 220.77528), 8.97)
        ax.plot(ks, percentages, color=".25", linewidth=.65,
                marker="o", markersize=3.6, markeredgewidth=.5)
        ax.set(xlim=(0, 200), ylim=(0, 100),
               xticks=[2, 32, 64, 128, 192], yticks=[0, 20, 40, 60, 80, 100],
               xlabel=r"branches $k$",
               ylabel="orders retained by edge repair (%)")
        ax.grid(True, color=".75", linewidth=.35)
        save(fig, "packet-orders-plot", args.output, args.paper_figures)
    print(json.dumps({"rows": len(rows), "exact_order_formulas_checked": len(rows)}))


if __name__ == "__main__":
    main()
