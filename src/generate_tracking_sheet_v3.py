#!/usr/bin/env python3
"""
Generate a PDF tracking sheet with system hardware information (v3 preview
fork of generate_tracking_sheet.py).

Adds auto-populated, coded "Notes & Cosmetics" entries (e.g. "KB2: Key(s)
Sticking (F, G)") built from each manual test page's get_notes_entries().

Usage: python3 generate_tracking_sheet_v3.py <item_name> [output_path]
"""

import io
import sys
import os
import threading
from datetime import date

try:
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        Image,
        KeepInFrame,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.graphics.shapes import Drawing, Circle, Line
except ImportError:
    print(
        "Error: reportlab is required. Install with: sudo apt install python3-reportlab"
    )
    sys.exit(1)

from utils import Utils

TRACKING_SHEET_TITLE = "Kramden Institute Tracking Sheet"
TRACKING_SHEET_REV = "Rev. 1.0 - July 2026"

# Step-order hints shown in the QC table header (None = no fixed order).
# Triage is step 1 and is inferred, so it has no column of its own.
QC_STAGES = [
    ("Parts<br/>Installed?", 2),
    ("OS<br/>Loaded?", 3),
    ("Cleaned?", None),
    ("Updated?", 3),
    ("Final<br/>Tested?", 4),
    ("Activated?", 5),
]

# Target number of note-line-equivalents to budget for in the Notes &
# Cosmetics box (matches the original's fixed 13 blank lines). Whatever's
# left over after each entry's wrapped height is filled with blank ruled
# lines for handwritten notes.
NOTE_LINE_BUDGET = 13
NOTE_LINE_HEIGHT = 0.19 * inch
MIN_BLANK_NOTE_LINES = 2


_system_info_cache = None
_system_info_lock = threading.Lock()


def get_system_info(force_refresh=False):
    """Retrieve system hardware information using Utils.

    Some of these queries (discrete-GPU detection in particular, which
    shells out to glxinfo) can take a second or more, and the hardware they
    inspect can't change mid-session, so the result is cached for the life
    of the process. See prefetch_tracking_sheet_data() to warm this cache
    in the background well before the tech clicks Print.
    """
    global _system_info_cache
    if _system_info_cache is not None and not force_refresh:
        return _system_info_cache
    with _system_info_lock:
        if _system_info_cache is not None and not force_refresh:
            return _system_info_cache
        info = _gather_system_info()
        _system_info_cache = info
        return info


def _gather_system_info():
    utils = Utils()

    brand = utils.get_vendor()
    model = utils.get_model()
    cpu = utils.get_cpu_info()
    ram = utils.get_mem()
    disks = utils.get_disks()
    gpu = utils.get_discrete_gpu()
    serial = utils.get_serial()
    batteries = utils.get_battery_capacities()
    device_type = utils.get_chassis_type()

    # Format storage as "<size>GB <TYPE>", one line per disk. Devices with no
    # drive installed (the common case for this line) get a blank field
    # instead of a misleading "None".
    if disks:
        storage_lines = [f"{d['size']}GB {d['type']}" for d in disks.values()]
        total_storage = ",<br/>".join(storage_lines)
    else:
        total_storage = ""

    info = {
        "Brand": brand,
        "Model": model,
        "CPU": cpu,
        "RAM": ram,
        "Storage": total_storage,
        "Serial# Scanner": serial,
        "Batteries": batteries,
    }

    if device_type:
        info["Item Type"] = device_type
    if gpu:
        info["Graphics"] = gpu
    else:
        igpu = utils.get_integrated_gpu()
        if igpu:
            info["Graphics"] = igpu

    return info


def _static_bold_stream(path):
    """Instantiate a real wght=700 static font from a variable font file.

    Modern Ubuntu installs ship Ubuntu-B.ttf as a symlink into a single
    variable-weight font file. reportlab's TrueType parser has no concept
    of variable font axes: it just reads the glyph outlines baked into
    the file at its default weight, so "bold" text came out looking
    identical to regular no matter which weight file it was given.
    Pulling the wght=700 instance out with fontTools before handing the
    bytes to reportlab works around that, in memory, without needing a
    separate font file on disk. Returns None if `path` isn't a variable
    font (older static Ubuntu-B.ttf), so the raw file can be used as-is.
    """
    from fontTools.ttLib import TTFont as VarTTFont
    from fontTools.varLib import instancer

    font = VarTTFont(path)
    if "fvar" not in font:
        return None

    axes = {axis.axisTag: axis.defaultValue for axis in font["fvar"].axes}
    axes["wght"] = 700.0
    instancer.instantiateVariableFont(font, axes, updateFontNames=True, inplace=True)

    buf = io.BytesIO()
    font.save(buf)
    buf.seek(0)
    return buf


# Instantiating the wght=700 static font from Ubuntu's variable-weight file
# via fontTools is by far the slowest step in generating a tracking sheet
# (measured at ~12s on typical hardware) -- far more than every hardware
# query in get_system_info() combined. It's also pure, input-only-changes-
# with-the-OS-image work, so it's cached to disk (survives repeat prints in
# the same session/boot) and only ever runs once per process (guarded by
# _fonts_registered, so a background prefetch and a real print racing each
# other don't both pay the cost).
BOLD_FONT_CACHE_PATH = "/tmp/kramden_ubuntu_bold_instance.ttf"

_fonts_registered = False
_fonts_lock = threading.Lock()


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    with _fonts_lock:
        if _fonts_registered:
            return
        _do_register_fonts()
        _fonts_registered = True


def _do_register_fonts():
    font_dir = "/usr/share/fonts/truetype/ubuntu"
    ubuntu_regular = os.path.join(font_dir, "Ubuntu-R.ttf")
    ubuntu_bold = os.path.join(font_dir, "Ubuntu-B.ttf")

    if not (os.path.exists(ubuntu_regular) and os.path.exists(ubuntu_bold)):
        raise FileNotFoundError(
            "Error: Ubuntu fonts not found at "
            f"{font_dir}. Install with: sudo apt install fonts-ubuntu "
            "or update the font paths in generate_tracking_sheet_v3.py."
        )

    pdfmetrics.registerFont(TTFont("Ubuntu", ubuntu_regular))

    bold_font_source = ubuntu_bold
    if os.path.exists(BOLD_FONT_CACHE_PATH) and os.path.getmtime(
        BOLD_FONT_CACHE_PATH
    ) >= os.path.getmtime(ubuntu_bold):
        bold_font_source = BOLD_FONT_CACHE_PATH
    else:
        try:
            bold_stream = _static_bold_stream(ubuntu_bold)
            if bold_stream is not None:
                bold_font_source = bold_stream
                try:
                    with open(BOLD_FONT_CACHE_PATH, "wb") as f:
                        f.write(bold_stream.getvalue())
                    bold_font_source = BOLD_FONT_CACHE_PATH
                except OSError:
                    bold_stream.seek(0)  # cache write failed; use the stream as-is
        except ImportError:
            pass  # python3-fonttools not installed; fall back to the raw file

    pdfmetrics.registerFont(TTFont("Ubuntu-Bold", bold_font_source))
    pdfmetrics.registerFontFamily("Ubuntu", normal="Ubuntu", bold="Ubuntu-Bold")


def prefetch_tracking_sheet_data():
    """Kick off the slow, one-time-per-session work (variable-font
    instancing, discrete-GPU detection, etc.) on background threads as soon
    as possible, so it's already done/cached by the time the tech reaches
    the Spec Complete page and clicks Print Tracking Sheet."""
    threading.Thread(target=_register_fonts, daemon=True).start()
    threading.Thread(target=get_system_info, daemon=True).start()


LABEL_BG = colors.HexColor("#f0f0f0")

# Matches the "text-error" red libadwaita applies to emblem-important-symbolic
# elsewhere in the app (specinfo.py, sysinfo.py, etc).
IMPORTANT_RED = colors.HexColor("#e01b24")


def _important_symbol(size=9):
    """A small circle-with-exclamation-mark Drawing, standing in for the
    emblem-important-symbolic icon used elsewhere in the app (that icon is
    an SVG from the system icon theme, which reportlab can't embed directly)."""
    d = Drawing(size, size)
    r = size / 2.0
    d.add(Circle(r, r, r, fillColor=IMPORTANT_RED, strokeColor=None))
    bar_width = max(1, size * 0.14)
    d.add(
        Line(
            r,
            size * 0.72,
            r,
            size * 0.4,
            strokeColor=colors.white,
            strokeWidth=bar_width,
            strokeLineCap=1,
        )
    )
    d.add(
        Circle(
            r, size * 0.24, bar_width / 2.0, fillColor=colors.white, strokeColor=None
        )
    )
    return d


def _grid_table(data, col_widths, row_heights=None, extra_cmds=None):
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if extra_cmds:
        style_cmds.extend(extra_cmds)
    table = Table(data, colWidths=col_widths, rowHeights=row_heights)
    table.setStyle(TableStyle(style_cmds))
    return table


def _notes_table_rows(notes_entries, notes_label_style, value_style, content_width):
    """Build the [row, ...]/[height, ...] pairs for the Notes & Cosmetics
    box: the auto-filled entries first, then enough blank ruled lines to
    fill out the usual line budget.

    Entry text is concatenated (comma-separated) by the callers, so a
    single entry can be longer than one line's worth of characters; its
    row height is measured via Paragraph.wrap() and rounded up to a whole
    number of NOTE_LINE_HEIGHT-tall lines so wrapped text pushes later
    rows down instead of overlapping them.
    """
    rows = [[Paragraph("Notes &amp; Cosmetics:", notes_label_style)]]
    heights = [0.28 * inch]
    used_lines = 0

    from math import ceil

    wrapped_value_style = ParagraphStyle(
        "NotesValueWrapped", parent=value_style, leading=NOTE_LINE_HEIGHT
    )

    for entry in notes_entries or []:
        text = entry.get("text")
        if text:
            para = Paragraph(text, wrapped_value_style)
            _, wrapped_height = para.wrap(
                content_width, NOTE_LINE_BUDGET * NOTE_LINE_HEIGHT
            )
            line_count = max(1, ceil(wrapped_height / NOTE_LINE_HEIGHT))
            rows.append([para])
            heights.append(line_count * NOTE_LINE_HEIGHT)
            used_lines += line_count

        strokes_list = entry.get("image_strokes_list")
        if strokes_list and _DIAGRAM_RENDER_AVAILABLE:
            rows.append([_diagrams_row(strokes_list, content_width)])
            heights.append(3 * NOTE_LINE_HEIGHT)
            used_lines += 3

    blank_lines = max(MIN_BLANK_NOTE_LINES, NOTE_LINE_BUDGET - used_lines)
    for _ in range(blank_lines):
        rows.append([""])
        heights.append(NOTE_LINE_HEIGHT)

    return rows, heights


def generate_tracking_sheet(
    item_name,
    output_path=None,
    spec_passed=None,
    manual_test_results=None,
    notes_entries=None,
):
    """Generate a single-page portrait PDF tracking sheet for a computer.

    notes_entries, if given, is a list of {"text": str} dicts (see
    manualtest_v3.TogglePage.get_notes_entries) that are pre-filled into the
    "Notes & Cosmetics" box.
    """
    if output_path is None:
        if item_name:
            output_path = f"/tmp/{item_name}_tracking_sheet.pdf"
        else:
            # No K-Number entered yet; keep output paths unique per run.
            stamp = date.today().strftime("%Y%m%d") + f"-{os.getpid()}"
            output_path = f"/tmp/tracking_sheet_{stamp}.pdf"

    print("Gathering system information...")
    system_info = get_system_info()

    print("\nSystem information:")
    for key, value in system_info.items():
        print(f"  {key}: {value}")

    page_size = A5
    margin_lr = 0.5 * cm
    doc = SimpleDocTemplate(
        output_path,
        pagesize=page_size,
        topMargin=0.4 * cm,
        bottomMargin=0.4 * cm,
        leftMargin=margin_lr,
        rightMargin=margin_lr,
    )

    _register_fonts()

    styles = getSampleStyleSheet()
    usable_width = page_size[0] - 2 * margin_lr

    # A5 is A4 scaled by 1/sqrt(2) on both axes, so every size below is the
    # A4 value scaled by ~0.7071 to keep identical proportions, just smaller.
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
        leading=12,
    )

    knum_style = ParagraphStyle(
        "KNumber",
        parent=styles["Normal"],
        fontSize=24,
        fontName="Ubuntu-Bold",
        leading=27,
        alignment=TA_RIGHT,
    )

    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
    )

    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
    )

    bad_value_style = ParagraphStyle(
        "BadValue",
        parent=value_style,
        fontName="Ubuntu-Bold",
    )

    notes_label_style = ParagraphStyle(
        "NotesLabel",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu-Bold",
    )

    os_style = ParagraphStyle(
        "Checkbox",
        parent=styles["Normal"],
        fontSize=12,
        fontName="Ubuntu-Bold",
    )

    qc_header_style = ParagraphStyle(
        "QCHeader",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu-Bold",
        alignment=TA_CENTER,
        leading=11,
    )

    qc_step_style = ParagraphStyle(
        "QCStep",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Ubuntu",
        textColor=colors.grey,
    )

    instructions_style = ParagraphStyle(
        "Instructions",
        parent=styles["Normal"],
        fontSize=9,
        fontName="Ubuntu",
        textColor=colors.grey,
        alignment=TA_CENTER,
    )

    footer_title_style = ParagraphStyle(
        "FooterTitle",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
    )

    footer_sub_style = ParagraphStyle(
        "FooterSub",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
        textColor=colors.grey,
    )

    elements = []

    # ===== Header: Generated/Initials (left) + K-Number (right) =====
    meta_para = Paragraph(
        f"Generated {date.today().strftime('%m-%d-%Y')}<br/>Initials: __________",
        meta_style,
    )
    knum_para = Paragraph(item_name or "_____________", knum_style)
    header_table = Table(
        [[meta_para, knum_para]],
        colWidths=[usable_width * 0.4, usable_width * 0.6],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 4))

    # ===== Spec grid: RAM/Storage/CPU, Model/Bat0, Graphics/Bat1 =====
    batteries = system_info.get("Batteries") or {}
    battery_names = list(batteries.keys())

    def battery_cell(index):
        if index >= len(battery_names):
            return "", ""
        name = battery_names[index]
        label = "Bat" + name[3:] if name.upper().startswith("BAT") else name
        return f"{label}:", f"{batteries[name]}%"

    bat0_label, bat0_value = battery_cell(0)
    bat1_label, bat1_value = battery_cell(1)

    # No batteries at all (e.g. a desktop) is worth calling out explicitly
    # rather than leaving the Bat0 field blank.
    if not battery_names:
        bat0_label, bat0_value = "Bat0:", "NONE"

    ram_value = f"{system_info.get('RAM', '')}GB"

    # RAM, Storage, and Battery values have a known maximum length ("128GB",
    # "1000GB NVMe", "100%"), so their columns are sized to just fit that text
    # instead of splitting the row proportionally. The width saved is handed
    # to CPU (row 0) and to Model/Graphics (rows 1-2), which need much more
    # room. RAM/Storage and Model/Graphics/Battery are split into two separate
    # tables below so their column widths can be sized independently instead
    # of sharing one grid of columns.
    CELL_HPAD = 12  # matches LEFTPADDING + RIGHTPADDING in _grid_table
    WIDTH_BUFFER = 4

    def _fit_width(text, buffer=WIDTH_BUFFER):
        return pdfmetrics.stringWidth(text, "Ubuntu", 10) + CELL_HPAD + buffer

    ram_val_width = _fit_width("128GB")
    storage_val_width = _fit_width("1000GB NVMe", buffer=1)
    bat_val_width = _fit_width("100%")

    # RAM/Storage labels are their own row-0-only columns (sized to just fit
    # their text), decoupled from the wider Model/Graphics label column below.
    ram_label_width = _fit_width("RAM")
    storage_label_width = _fit_width("Storage")

    model_label_width = _fit_width("Model")
    spec_label_col0 = 62  # Graphics label
    spec_label_col4 = 42  # CPU / Bat0 / Bat1 label

    row0_col_widths = [
        ram_label_width,
        ram_val_width,
        storage_label_width,
        storage_val_width,
        spec_label_col4,
        usable_width
        - ram_label_width
        - ram_val_width
        - storage_label_width
        - storage_val_width
        - spec_label_col4,
    ]
    row0_table = _grid_table(
        [
            [
                Paragraph("RAM", label_style),
                Paragraph(ram_value, value_style),
                Paragraph("Storage", label_style),
                Paragraph(system_info.get("Storage", ""), value_style),
                Paragraph("CPU", label_style),
                Paragraph(system_info.get("CPU", ""), value_style),
            ]
        ],
        row0_col_widths,
        extra_cmds=[
            ("BACKGROUND", (0, 0), (0, 0), LABEL_BG),
            ("BACKGROUND", (2, 0), (2, 0), LABEL_BG),
            ("BACKGROUND", (4, 0), (4, 0), LABEL_BG),
        ],
    )

    model_row_widths = [
        model_label_width,
        usable_width - model_label_width - spec_label_col4 - bat_val_width,
        spec_label_col4,
        bat_val_width,
    ]
    model_row_table = _grid_table(
        [
            [
                Paragraph("Model", label_style),
                Paragraph(system_info.get("Model", ""), value_style),
                Paragraph(bat0_label, label_style),
                Paragraph(bat0_value, value_style),
            ],
        ],
        model_row_widths,
        extra_cmds=[
            ("BACKGROUND", (0, 0), (0, -1), LABEL_BG),
            ("BACKGROUND", (2, 0), (2, -1), LABEL_BG),
        ],
    )

    # When there's no second battery, drop the Bat1 label/value columns and
    # hand the freed width to the Graphics value column instead.
    if len(battery_names) < 2:
        graphics_row_widths = [
            spec_label_col0,
            usable_width - spec_label_col0,
        ]
        graphics_row_table = _grid_table(
            [
                [
                    Paragraph("Graphics", label_style),
                    Paragraph(system_info.get("Graphics", "N/A"), value_style),
                ],
            ],
            graphics_row_widths,
            extra_cmds=[
                ("BACKGROUND", (0, 0), (0, -1), LABEL_BG),
            ],
        )
    else:
        graphics_row_widths = [
            spec_label_col0,
            usable_width - spec_label_col0 - spec_label_col4 - bat_val_width,
            spec_label_col4,
            bat_val_width,
        ]
        graphics_row_table = _grid_table(
            [
                [
                    Paragraph("Graphics", label_style),
                    Paragraph(system_info.get("Graphics", "N/A"), value_style),
                    Paragraph(bat1_label, label_style),
                    Paragraph(bat1_value, value_style),
                ],
            ],
            graphics_row_widths,
            extra_cmds=[
                ("BACKGROUND", (0, 0), (0, -1), LABEL_BG),
                ("BACKGROUND", (2, 0), (2, -1), LABEL_BG),
            ],
        )
    elements.append(row0_table)
    elements.append(model_row_table)
    elements.append(graphics_row_table)
    elements.append(Spacer(1, 4))

    # ===== Hardware test grid (3x3) =====
    mt = manual_test_results or {}

    # manual_test_results values are the "Pass"/"Fail"/"Untested" (or, for
    # WebCam, also "N/A") strings returned by each page's get_result().
    RESULT_LABELS = {"Pass": "GOOD", "Fail": "BAD", "N/A": "N/A", "Untested": ""}

    def test_value(name):
        return RESULT_LABELS.get(mt.get(name), "")

    webcam_value = test_value("WebCam")
    # A "Touchscreen" key is only present in manual_test_results at all on
    # devices that have one (see spec_v3.py's has_touchscreen() gating);
    # its absence is what distinguishes "not a touchscreen" from "not
    # tested yet".
    touchscreen_value = test_value("Touchscreen") if "Touchscreen" in mt else "N/A"

    def test_result_cell(value):
        if value != "BAD":
            return Paragraph(value, value_style)
        return Table(
            [[Paragraph("BAD", bad_value_style), _important_symbol()]],
            colWidths=[None, 12],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )

    def usb_result_cell():
        """USB-A and USB-C are separate manual test pages (see
        manualtest_v3.UsbAPage/UsbCPage) but share one "USB:" cell here.
        "USBC" is only present in manual_test_results on devices with a
        USB-C port (see spec_v3.py's has_usb_c() gating), mirroring the
        Touchscreen key's presence-means-applicable convention above."""
        segments = [("A", test_value("USBA"))]
        if "USBC" in mt:
            segments.append(("C", test_value("USBC")))
        lines = []
        any_bad = False
        for label, value in segments:
            if value == "BAD":
                any_bad = True
                lines.append(f'{label}: <font name="Ubuntu-Bold">BAD</font>')
            else:
                lines.append(f"{label}: {value}" if value else f"{label}:")
        para = Paragraph("<br/>".join(lines), value_style)
        if not any_bad:
            return para
        return Table(
            [[para, _important_symbol()]],
            colWidths=[None, 12],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )

    test_grid_data = [
        [
            Paragraph("Keyboard:", label_style),
            test_result_cell(test_value("Keyboard")),
            Paragraph("USB:", label_style),
            usb_result_cell(),
            Paragraph("Screen:", label_style),
            test_result_cell(test_value("ScreenTest")),
        ],
        [
            Paragraph("Wi-Fi:", label_style),
            test_result_cell(test_value("WiFi")),
            Paragraph("Sound:", label_style),
            test_result_cell(test_value("Sound")),
            Paragraph("Touchpad:", label_style),
            test_result_cell(test_value("Touchpad")),
        ],
        [
            Paragraph("Webcam:", label_style),
            test_result_cell(webcam_value),
            Paragraph("Touchscreen?", label_style),
            test_result_cell(touchscreen_value),
            Paragraph("Physical:", label_style),
            test_result_cell(test_value("PhysicalDefects")),
        ],
    ]
    test_label_col0 = 62
    test_label_col2 = 80
    test_label_col4 = 62
    test_flex = (
        usable_width - test_label_col0 - test_label_col2 - test_label_col4
    ) / 3.0
    test_col_widths = [
        test_label_col0,
        test_flex,
        test_label_col2,
        test_flex,
        test_label_col4,
        test_flex,
    ]
    test_grid = _grid_table(
        test_grid_data,
        test_col_widths,
        extra_cmds=[
            # Label columns: Keyboard/Wi-Fi/Webcam, USB/Sound/Touchscreen?, Screen/Touchpad/Physical
            ("BACKGROUND", (0, 0), (0, -1), LABEL_BG),
            ("BACKGROUND", (2, 0), (2, -1), LABEL_BG),
            ("BACKGROUND", (4, 0), (4, -1), LABEL_BG),
        ],
    )
    elements.append(test_grid)
    elements.append(Spacer(1, 4))

    # ===== Notes & Cosmetics =====
    notes_content_width = usable_width - 12  # minus cell LEFT/RIGHTPADDING
    notes_rows, notes_row_heights = _notes_table_rows(
        notes_entries, notes_label_style, value_style, notes_content_width
    )

    notes_table = Table(
        notes_rows,
        colWidths=[usable_width],
        rowHeights=notes_row_heights,
    )
    notes_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                ("LINEBELOW", (0, 1), (-1, -2), 0.5, colors.HexColor("#999999")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (0, 0), 6),
                ("BOTTOMPADDING", (0, 0), (0, 0), 6),
                ("LEFTPADDING", (0, 0), (0, 0), 10),
            ]
        )
    )
    elements.append(notes_table)
    elements.append(Spacer(1, 4))

    # ===== OS selection line =====
    os_para = Paragraph(
        "OS:&nbsp;&nbsp; Ubuntu &nbsp;&nbsp;|&nbsp;&nbsp; Windows 11 "
        "&nbsp;&nbsp;|&nbsp;&nbsp; MacOS &nbsp;&nbsp;|&nbsp;&nbsp; Other: ____________",
        os_style,
    )
    # ===== QC sign-off rows (header + entry) =====
    qc_header_row = []
    qc_step_row = []
    for label, step in QC_STAGES:
        qc_header_row.append(Paragraph(label, qc_header_style))
        qc_step_row.append(
            [Paragraph(str(step) if step is not None else "", qc_step_style)]
        )

    qc_col_widths = [usable_width / 6.0] * 6

    instructions_para = Paragraph(
        "(Please put your initials &amp; the date above as steps are completed. Triage is inferred.)",
        instructions_style,
    )

    # OS selection, QC sign-off, and instructions are combined into a single
    # table so the sign-off flow reads as one continuous block instead of
    # three separately-bordered pieces.
    os_qc_data = [
        [os_para, "", "", "", "", ""],
        qc_header_row,
        qc_step_row,
        [instructions_para, "", "", "", "", ""],
    ]
    os_qc_table = Table(
        os_qc_data,
        colWidths=qc_col_widths,
        rowHeights=[None, 0.42 * inch, 0.5 * inch, None],
    )
    os_qc_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.black),
                ("SPAN", (0, 0), (-1, 0)),
                ("SPAN", (0, 3), (-1, 3)),
                # OS row
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("LEFTPADDING", (0, 0), (-1, 0), 10),
                ("RIGHTPADDING", (0, 0), (-1, 0), 10),
                # QC header row
                ("VALIGN", (0, 1), (-1, 1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, 1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 3),
                ("LEFTPADDING", (0, 1), (-1, 1), 3),
                ("RIGHTPADDING", (0, 1), (-1, 1), 3),
                # QC entry row
                ("VALIGN", (0, 2), (-1, 2), "TOP"),
                ("TOPPADDING", (0, 2), (-1, 2), 1.5),
                ("LEFTPADDING", (0, 2), (-1, 2), 3),
                # Instructions row
                ("VALIGN", (0, 3), (-1, 3), "MIDDLE"),
                ("TOPPADDING", (0, 3), (-1, 3), 4),
                ("BOTTOMPADDING", (0, 3), (-1, 3), 4),
                ("LEFTPADDING", (0, 3), (-1, 3), 6),
                ("RIGHTPADDING", (0, 3), (-1, 3), 6),
            ]
        )
    )
    elements.append(os_qc_table)
    elements.append(Spacer(1, 4))

    # ===== Footer: title/rev (left) + logo (right) =====
    logo_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "pixmaps",
        "kramden_tracking_header.png",
    )
    if not os.path.exists(logo_path):
        logo_path = "/usr/share/pixmaps/kramden_tracking_header.png"

    footer_text = Table(
        [
            [Paragraph(TRACKING_SHEET_TITLE, footer_title_style)],
            [Paragraph(TRACKING_SHEET_REV, footer_sub_style)],
        ],
        colWidths=[usable_width * 0.6],
    )
    footer_text.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    if os.path.exists(logo_path):
        logo = Image(
            logo_path, width=1.4 * inch, height=0.63 * inch, kind="proportional"
        )
        footer_table = Table(
            [[footer_text, logo]],
            colWidths=[usable_width * 0.6, usable_width * 0.4],
        )
        footer_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(footer_table)
    else:
        elements.append(footer_text)

    # Safety net: however the notes budget above works out, never hard-fail
    # with a "flowable too large" error if a page's worth of content still
    # doesn't fit (e.g. an unusually large number of failure notes) -- shrink
    # the whole page to fit instead, same as it would if hand-tuned to fit.
    frame_padding = 12  # default SimpleDocTemplate frame padding (6 top + 6 bottom)
    available_height = page_size[1] - doc.topMargin - doc.bottomMargin - frame_padding
    elements = [KeepInFrame(usable_width, available_height, elements, mode="shrink")]

    # Build PDF
    print(f"\nGenerating PDF: {output_path}")
    doc.build(elements)
    print(f"Done! Tracking sheet saved to: {output_path}")
    return output_path


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <item_name> [output_path]")
        sys.exit(1)

    item_name = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    generate_tracking_sheet(item_name, output_path)


if __name__ == "__main__":
    main()
