#!/usr/bin/env python3
"""
Generate a PDF tracking sheet with system hardware information for A5 paper.

Usage: python3 generate_tracking_sheet_a5.py <item_name> [output_path]
"""

import sys
import os
from datetime import date

try:
    from reportlab.lib.pagesizes import A5, landscape
    from reportlab.lib.units import inch, mm
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
    bios_password = utils.has_bios_password()
    asset_info = utils.has_asset_info()
    computrace = utils.has_computrace_enabled()

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
        "BIOS Password": "Yes" if bios_password else "No",
        "Asset Info": "Yes" if asset_info else "No",
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

    # Only include Computrace if status is known
    if computrace is True:
        info["Computrace"] = "Activated"
    elif computrace is False:
        info["Computrace"] = "Not Activated"

    return info


def generate_tracking_sheet(item_name, output_path=None, spec_passed=None, manual_test_results=None):
    """Generate a portrait A5 PDF tracking sheet for a computer.

    Layout: single-column portrait page with header, logo, specs,
    QC workflow, manual test results, and notes sections.
    """
    if output_path is None:
        output_path = f"/tmp/{item_name}_tracking_sheet_a5.pdf"

    print("Gathering system information...")
    system_info = get_system_info()

    print("\nSystem information:")
    for key, value in system_info.items():
        if key in ("RAM", "Storage"):
            print(f"  {key}: {value} GB")
        else:
            print(f"  {key}: {value}")

    page_size = A5
    margin_lr = 0.3 * inch

    doc = SimpleDocTemplate(
        output_path,
        pagesize=page_size,
        topMargin=0.25 * inch,
        bottomMargin=0.2 * inch,
        leftMargin=margin_lr,
        rightMargin=margin_lr,
    )

    # Register Ubuntu fonts
    font_dir = "/usr/share/fonts/truetype/ubuntu"
    ubuntu_regular = os.path.join(font_dir, "Ubuntu-R.ttf")
    ubuntu_bold = os.path.join(font_dir, "Ubuntu-B.ttf")

    if not (os.path.exists(ubuntu_regular) and os.path.exists(ubuntu_bold)):
        raise FileNotFoundError(
            "Error: Ubuntu fonts not found at "
            f"{font_dir}. Install with: sudo apt install fonts-ubuntu "
            "or update the font paths in generate_tracking_sheet_a5.py."
        )

    pdfmetrics.registerFont(TTFont("Ubuntu", ubuntu_regular))
    pdfmetrics.registerFont(TTFont("Ubuntu-Bold", ubuntu_bold))
    pdfmetrics.registerFontFamily("Ubuntu", normal="Ubuntu", bold="Ubuntu-Bold")

    styles = getSampleStyleSheet()
    usable_width = page_size[0] - 2 * margin_lr

    # Custom styles - scaled down for A5
    title_style = ParagraphStyle(
        "TrackingTitle",
        parent=styles["Title"],
        fontSize=14,
        fontName="Ubuntu-Bold",
        spaceAfter=0,
        spaceBefore=0,
        alignment=TA_LEFT,
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=7,
        fontName="Ubuntu",
        textColor=colors.grey,
        spaceAfter=0,
        spaceBefore=1,
    )

    knum_style = ParagraphStyle(
        "KNumber",
        parent=styles["Normal"],
        fontSize=16,
        fontName="Ubuntu-Bold",
        leading=20,
        spaceBefore=3,
        spaceAfter=4,
    )

    info_style = ParagraphStyle(
        "Info",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Ubuntu",
        spaceBefore=0,
        spaceAfter=3,
    )

    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontSize=9,
        fontName="Ubuntu-Bold",
        spaceBefore=6,
        spaceAfter=3,
        textColor=colors.HexColor("#333333"),
    )

    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=7,
        fontName="Ubuntu-Bold",
    )

    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontSize=7,
        fontName="Ubuntu",
    )

    checkbox_style = ParagraphStyle(
        "Checkbox",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Ubuntu",
        leading=12,
    )

    # ===== Build Content =====
    content = []

    # --- Header with logo on right side ---
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
            logo_path, width=0.65 * inch, height=0.65 * inch, kind="proportional"
        )
        header_data = [
            [title_para, logo],
            [date_para, ""],
        ]
        header_table = Table(
            header_data,
            colWidths=[usable_width - 0.75 * inch, 0.75 * inch],
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
        content.append(header_table)
    else:
        content.append(title_para)
        content.append(date_para)

    content.append(Spacer(1, 1))
    content.append(HRFlowable(width="100%", thickness=0.5, color=colors.black))
    content.append(Spacer(1, 2))

    # --- Item Identity ---
    content.append(Paragraph(item_name, knum_style))
    serial = system_info.get("Serial# Scanner", "N/A")
    device_type = system_info.get("Item Type", "Unknown")
    content.append(
        Paragraph(
            f"Serial: {serial}&nbsp;&nbsp;|&nbsp;&nbsp;Type: {device_type}",
            info_style,
        )
    )

    # --- System Specifications ---
    content.append(Paragraph("SYSTEM SPECIFICATIONS", section_header_style))

    spec_rows = [
        ("Brand", system_info.get("Brand", "")),
        ("Model", system_info.get("Model", "")),
    ]
    if "Item Type" in system_info:
        spec_rows.append(("Device Type", system_info["Item Type"]))
    spec_rows.append(("BIOS Password", system_info.get("BIOS Password", "")))
    spec_rows.append(("Asset Info", system_info.get("Asset Info", "")))
    if "Computrace" in system_info:
        spec_rows.append(("Computrace", system_info["Computrace"]))
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

    # Add OS row with checkboxes
    spec_table_data.append(
        [
            Paragraph("OS", label_style),
            Paragraph("☐ Ubuntu  ☐ Windows", checkbox_style),
        ]
    )

    spec_table = Table(
        spec_table_data,
        colWidths=[0.8 * inch, usable_width - 0.8 * inch],
    )
    spec_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    content.append(spec_table)

    # --- QC Workflow ---
    content.append(Paragraph("QC WORKFLOW", section_header_style))

    qc_header = [
        Paragraph("Stage", label_style),
        Paragraph("Pass", label_style),
        Paragraph("Fail", label_style),
        Paragraph("Init.", label_style),
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

    qc_col_widths = [0.7 * inch, 0.35 * inch, 0.35 * inch, 0.5 * inch, usable_width - 1.9 * inch]
    # Scale columns to fit width
    total_qc = sum(qc_col_widths)
    if abs(total_qc - usable_width) > 0.01:
        scale = usable_width / total_qc
        qc_col_widths = [w * scale for w in qc_col_widths]

    qc_table = Table(
        qc_data,
        colWidths=qc_col_widths,
        rowHeights=[None] + [0.22 * inch] * len(qc_stages),
    )
    qc_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (2, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    content.append(qc_table)

    # --- Manual Test Results ---
    content.append(Paragraph("MANUAL TEST RESULTS", section_header_style))

    # Fixed display order
    test_display_order = [
        "USB", "Browser", "WiFi", "WebCam",
        "Keyboard", "Touchpad", "ScreenTest", "Battery",
    ]

    mt_header = [
        Paragraph("Test", label_style),
        Paragraph("Result", label_style),
    ]
    mt_data = [mt_header]

    for test_name in test_display_order:
        result_text = ""
        if manual_test_results is not None and test_name in manual_test_results:
            value = manual_test_results[test_name]
            if isinstance(value, bool):
                result_text = "\u2713 Pass" if value else "\u2717 Fail"
            else:
                # WebCam string values: "Pass", "Fail", "N/A", "Untested"
                if value == "Pass":
                    result_text = "\u2713 Pass"
                elif value == "N/A":
                    result_text = "N/A"
                elif value == "Fail":
                    result_text = "\u2717 Fail"
                else:
                    result_text = "\u2717 Untested"
        mt_data.append([
            Paragraph(test_name, value_style),
            Paragraph(result_text, value_style),
        ])

    mt_table = Table(
        mt_data,
        colWidths=[usable_width * 0.5, usable_width * 0.5],
    )
    mt_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    content.append(mt_table)

    # --- Notes ---
    content.append(Paragraph("NOTES", section_header_style))

    note_count = 8
    note_data = [[""] for _ in range(note_count)]
    notes_table = Table(
        note_data, colWidths=[usable_width], rowHeights=[0.22 * inch] * note_count
    )
    notes_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ]
        )
    )
    content.append(notes_table)

    # Build PDF
    print(f"\nGenerating PDF: {output_path}")
    doc.build(content)
    print(f"Done! A5 tracking sheet saved to: {output_path}")
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
