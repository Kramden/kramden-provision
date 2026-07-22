#!/usr/bin/env python3
"""
Generate a PDF tracking sheet with system hardware information.

Layout follows the Kramden Institute paper tracking sheet: a single
portrait page with a spec grid, a hardware test grid, a notes area, an
OS selection line, and a QC sign-off table.

Usage: python3 generate_tracking_sheet.py <item_name> [output_path]
"""

import io
import sys
import os
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
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
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


def get_system_info():
    """Retrieve system hardware information using Utils."""
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

    # Format storage as "<size>GB <TYPE>", one line per disk.
    if disks:
        storage_lines = [f"{d['size']}GB {d['type']}" for d in disks.values()]
        total_storage = ",<br/>".join(storage_lines)
    else:
        total_storage = "None"

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
    instancer.instantiateVariableFont(
        font, axes, updateFontNames=True, inplace=True
    )

    buf = io.BytesIO()
    font.save(buf)
    buf.seek(0)
    return buf


def _register_fonts():
    font_dir = "/usr/share/fonts/truetype/ubuntu"
    ubuntu_regular = os.path.join(font_dir, "Ubuntu-R.ttf")
    ubuntu_bold = os.path.join(font_dir, "Ubuntu-B.ttf")

    if not (os.path.exists(ubuntu_regular) and os.path.exists(ubuntu_bold)):
        raise FileNotFoundError(
            "Error: Ubuntu fonts not found at "
            f"{font_dir}. Install with: sudo apt install fonts-ubuntu "
            "or update the font paths in generate_tracking_sheet.py."
        )

    pdfmetrics.registerFont(TTFont("Ubuntu", ubuntu_regular))

    bold_font_source = ubuntu_bold
    try:
        bold_stream = _static_bold_stream(ubuntu_bold)
        if bold_stream is not None:
            bold_font_source = bold_stream
    except ImportError:
        pass  # python3-fonttools not installed; fall back to the raw file

    pdfmetrics.registerFont(TTFont("Ubuntu-Bold", bold_font_source))
    pdfmetrics.registerFontFamily("Ubuntu", normal="Ubuntu", bold="Ubuntu-Bold")


LABEL_BG = colors.HexColor("#e6e6e6")


def _bool_result(value):
    if value is None:
        return ""
    return "GOOD" if value else "BAD"


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


def generate_tracking_sheet(
    item_name, output_path=None, spec_passed=None, manual_test_results=None
):
    """Generate a single-page portrait PDF tracking sheet for a computer."""
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
        fontName="Ubuntu-Bold",
    )

    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
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

    ram_value = f"{system_info.get('RAM', '')}GB"
    spec_grid_data = [
        [
            Paragraph("RAM", label_style),
            Paragraph(ram_value, value_style),
            Paragraph("Storage", label_style),
            Paragraph(system_info.get("Storage", ""), value_style),
            Paragraph("CPU", label_style),
            Paragraph(system_info.get("CPU", ""), value_style),
        ],
        [
            Paragraph("Model", label_style),
            Paragraph(system_info.get("Model", ""), value_style),
            "",
            "",
            Paragraph(bat0_label, label_style),
            Paragraph(bat0_value, value_style),
        ],
        [
            Paragraph("Graphics", label_style),
            Paragraph(system_info.get("Graphics", "N/A"), value_style),
            "",
            "",
            Paragraph(bat1_label, label_style),
            Paragraph(bat1_value, value_style),
        ],
    ]
    spec_label_col0 = 62
    spec_label_col2 = 58
    spec_label_col4 = 42
    spec_flex = usable_width - spec_label_col0 - spec_label_col2 - spec_label_col4
    spec_col_widths = [
        spec_label_col0,
        spec_flex * 0.22,
        spec_label_col2,
        spec_flex * 0.40,
        spec_label_col4,
        spec_flex * 0.38,
    ]
    spec_grid = _grid_table(
        spec_grid_data,
        spec_col_widths,
        extra_cmds=[
            ("SPAN", (1, 1), (3, 1)),
            ("SPAN", (1, 2), (3, 2)),
            # Label columns: RAM/Model/Graphics, Storage (row 0 only), CPU/Bat0/Bat1
            ("BACKGROUND", (0, 0), (0, -1), LABEL_BG),
            ("BACKGROUND", (2, 0), (2, 0), LABEL_BG),
            ("BACKGROUND", (4, 0), (4, -1), LABEL_BG),
        ],
    )
    elements.append(spec_grid)
    elements.append(Spacer(1, 4))

    # ===== Hardware test grid (3x3) =====
    mt = manual_test_results or {}

    def test_value(name):
        if name not in mt:
            return ""
        return _bool_result(mt[name])

    webcam_map = {"Pass": "GOOD", "Fail": "BAD", "N/A": "N/A", "Untested": ""}
    webcam_value = webcam_map.get(mt.get("WebCam"), "")
    touchscreen_value = "YES" if Utils.has_touchscreen() else "NO"

    test_grid_data = [
        [
            Paragraph("Keyboard:", label_style),
            Paragraph(test_value("Keyboard"), value_style),
            Paragraph("USB:", label_style),
            Paragraph(test_value("USB"), value_style),
            Paragraph("Screen:", label_style),
            Paragraph(test_value("ScreenTest"), value_style),
        ],
        [
            Paragraph("Wi-Fi:", label_style),
            Paragraph(test_value("WiFi"), value_style),
            Paragraph("Sound:", label_style),
            Paragraph("", value_style),
            Paragraph("Touchpad:", label_style),
            Paragraph(test_value("Touchpad"), value_style),
        ],
        [
            Paragraph("Webcam:", label_style),
            Paragraph(webcam_value, value_style),
            Paragraph("Touchscreen?", label_style),
            Paragraph(touchscreen_value, value_style),
            Paragraph("Physical:", label_style),
            Paragraph("", value_style),
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
    note_line_count = 11
    notes_rows = [[Paragraph("Notes &amp; Cosmetics:", notes_label_style)]]
    for _ in range(note_line_count):
        notes_rows.append([""])

    notes_table = Table(
        notes_rows,
        colWidths=[usable_width],
        rowHeights=[0.28 * inch] + [0.19 * inch] * note_line_count,
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
        rowHeights=[None, 0.42 * inch, 0.8 * inch, None],
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
