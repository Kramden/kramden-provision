#!/usr/bin/env python3
"""
Generate a PDF tracking sheet with system hardware information.

Usage: python3 generate_tracking_sheet.py <item_name> [output_path]
"""

import sys
import os
from datetime import date

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        Image,
        HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    print(
        "Error: reportlab is required. Install with: sudo apt install python3-reportlab"
    )
    sys.exit(1)

from utils import Utils


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

    # Sum total storage in GB
    if disks:
        total_storage = sum(disks.values())
    else:
        total_storage = 0

    # Format battery capacity
    if batteries:
        capacities = list(batteries.values())
        if len(capacities) == 1:
            battery_health = f"{capacities[0]}%"
        else:
            # Multiple batteries - show all
            battery_health = ", ".join(f"{c}%" for c in capacities)
    else:
        battery_health = None

    info = {
        "Brand": brand,
        "Model": model,
        "CPU": cpu,
        "RAM": ram,  # Numeric value only
        "Storage": total_storage,  # Numeric value only
        "Serial# Scanner": serial,
    }

    # Only include Item Type if chassis type could be determined
    if device_type:
        info["Item Type"] = device_type

    # Only include Graphics if a discrete GPU is detected
    if gpu:
        info["Graphics"] = gpu

    # Only include Battery Capacity if batteries are detected
    if battery_health:
        info["Battery Capacity"] = battery_health

    return info


def generate_tracking_sheet(item_name, output_path=None, spec_passed=None):
    """Generate a PDF tracking sheet for a computer."""
    if output_path is None:
        output_path = f"/tmp/{item_name}_tracking_sheet.pdf"

    print("Gathering system information...")
    system_info = get_system_info()

    print("\nSystem information:")
    for key, value in system_info.items():
        if key in ("RAM", "Storage"):
            print(f"  {key}: {value} GB")
        else:
            print(f"  {key}: {value}")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.4 * inch,
        bottomMargin=0.3 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    # Register Ubuntu fonts
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
    pdfmetrics.registerFont(TTFont("Ubuntu-Bold", ubuntu_bold))
    pdfmetrics.registerFontFamily("Ubuntu", normal="Ubuntu", bold="Ubuntu-Bold")

    styles = getSampleStyleSheet()
    page_width = letter[0] - 1.5 * inch  # Available width after margins

    # Custom styles
    title_style = ParagraphStyle(
        "TrackingTitle",
        parent=styles["Title"],
        fontSize=20,
        fontName="Ubuntu-Bold",
        spaceAfter=0,
        spaceBefore=0,
        alignment=TA_LEFT,
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
        textColor=colors.grey,
        spaceAfter=0,
        spaceBefore=2,
    )

    knum_style = ParagraphStyle(
        "KNumber",
        parent=styles["Normal"],
        fontSize=24,
        fontName="Ubuntu-Bold",
        leading=30,
        spaceBefore=4,
        spaceAfter=6,
    )

    info_style = ParagraphStyle(
        "Info",
        parent=styles["Normal"],
        fontSize=11,
        fontName="Ubuntu",
        spaceBefore=0,
        spaceAfter=4,
    )

    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontSize=12,
        fontName="Ubuntu-Bold",
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#333333"),
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

    checkbox_style = ParagraphStyle(
        "Checkbox",
        parent=styles["Normal"],
        fontSize=14,
        fontName="Ubuntu",
        leading=18,
    )

    elements = []

    # --- Header ---
    logo_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "pixmaps",
        "kramden_tracking_header.png",
    )
    if not os.path.exists(logo_path):
        logo_path = "/usr/share/pixmaps/kramden_tracking_header.png"

    title_para = Paragraph("Kramden Tracking Sheet", title_style)
    date_para = Paragraph(f"Generated: {date.today().strftime('%m-%d-%Y')}", subtitle_style)

    if os.path.exists(logo_path):
        logo = Image(
            logo_path, width=1.2 * inch, height=1.2 * inch, kind="proportional"
        )
        header_data = [
            [title_para, logo],
            [date_para, ""],
        ]
        header_table = Table(
            header_data,
            colWidths=[page_width - 1.5 * inch, 1.5 * inch],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("SPAN", (1, 0), (1, 1)),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(header_table)
    else:
        elements.append(title_para)
        elements.append(date_para)

    elements.append(Spacer(1, 2))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 4))

    # --- Item Identity ---
    elements.append(Paragraph(item_name, knum_style))
    serial = system_info.get("Serial# Scanner", "N/A")
    device_type = system_info.get("Item Type", "Unknown")
    elements.append(
        Paragraph(
            f"Serial: {serial}&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;Type: {device_type}",
            info_style,
        )
    )

    # --- System Specifications ---
    elements.append(Paragraph("SYSTEM SPECIFICATIONS", section_header_style))

    spec_rows = [
        ("Brand", system_info.get("Brand", "")),
        ("Model", system_info.get("Model", "")),
    ]
    if "Item Type" in system_info:
        spec_rows.append(("Device Type", system_info["Item Type"]))
    spec_rows.append(("CPU", system_info.get("CPU", "")))
    spec_rows.append(("RAM", f"{system_info.get('RAM', '')} GB"))
    spec_rows.append(("Storage", f"{system_info.get('Storage', '')} GB"))
    if "Graphics" in system_info:
        spec_rows.append(("Graphics", system_info["Graphics"]))
    if "Battery Capacity" in system_info:
        spec_rows.append(("Battery Capacity", system_info["Battery Capacity"]))
    spec_rows.append(("Serial", system_info.get("Serial# Scanner", "")))

    spec_table_data = [
        [Paragraph(label, label_style), Paragraph(str(value), value_style)]
        for label, value in spec_rows
    ]

    # Add OS row with larger checkboxes for usability
    spec_table_data.append(
        [
            Paragraph("OS", label_style),
            Paragraph("☐ Ubuntu      ☐ Windows", checkbox_style),
        ]
    )

    spec_table = Table(
        spec_table_data,
        colWidths=[1.5 * inch, page_width - 1.5 * inch],
    )
    spec_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(spec_table)

    # --- QC Workflow ---
    elements.append(Paragraph("QC WORKFLOW", section_header_style))

    qc_header = [
        Paragraph("Stage", label_style),
        Paragraph("Pass", label_style),
        Paragraph("Fail", label_style),
        Paragraph("Initials", label_style),
        Paragraph("Date", label_style),
    ]

    qc_stages = ["Spec", "OS Load", "Final Test", "Cleaning"]
    qc_data = [qc_header]
    for stage in qc_stages:
        pass_cell = ""
        fail_cell = ""
        date_cell = ""
        if stage == "Spec" and spec_passed is not None:
            if spec_passed:
                pass_cell = Paragraph("✓", checkbox_style)
            else:
                fail_cell = Paragraph("✓", checkbox_style)
            date_cell = Paragraph(date.today().strftime("%m-%d-%Y"), value_style)
        qc_data.append([Paragraph(stage, value_style), pass_cell, fail_cell, "", date_cell])

    qc_col_widths = [1.5 * inch, 0.75 * inch, 0.75 * inch, 1.8 * inch, 1.8 * inch]
    # Scale columns to fit page width
    total_qc = sum(qc_col_widths)
    if total_qc != page_width:
        scale = page_width / total_qc
        qc_col_widths = [w * scale for w in qc_col_widths]

    qc_table = Table(
        qc_data,
        colWidths=qc_col_widths,
        rowHeights=[None] + [0.35 * inch] * len(qc_stages),
    )
    qc_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (2, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(qc_table)

    # --- Notes ---
    elements.append(Paragraph("NOTES", section_header_style))

    note_data = [[""] for _ in range(5)]
    notes_table = Table(note_data, colWidths=[page_width], rowHeights=[0.35 * inch] * 5)
    notes_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ]
        )
    )
    elements.append(notes_table)

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
