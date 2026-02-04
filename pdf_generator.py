"""
RadioTrack - Department of Corrections Radio Management System
--------------------------------------
pdf_generator.py file for Streamlit UI
--------------------------------------
Author: Arthur Belanger (github.com/coding-with-arty)
Copyright (c) 2025 Arthur Belanger
All rights reserved.
"""

import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import pandas as pd

from models import get_items, get_locations
from config import CONDITION_COLORS


def generate_inventory_pdf(report_type="complete", filter_value=None):
    """Generate a PDF report of the inventory with optional filtering

    Args:
        report_type (str): Type of report - "complete", "item", "location", "category", "condition"
        filter_value (str/int): Value to filter by (item_id for item, location/category/condition name for others)
    """
    buffer = io.BytesIO()

    try:
        # Create PDF document with enhanced browser-compatible settings
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            author="RadioTrack",
            title="MCC Radio Inventory Report",
            # Allow tables to fit within page boundaries
            allowSplitting=1
        )

        styles = getSampleStyleSheet()
        elements = []

        # Apply filtering based on report type
        items = get_items()

        if report_type == "item" and filter_value:
            items = items[items["id"] == int(filter_value)]
            title = f"MCC Radio Inventory - Item: {
                items.iloc[0]['name'] if len(items) > 0 else 'Not Found'}"
        elif report_type == "location" and filter_value:
            items = items[items["location"] == filter_value]
            title = f"MCC Radio Inventory - Location: {filter_value}"
        elif report_type == "category" and filter_value:
            items = items[items["category"] == filter_value]
            title = f"MCC Radio Inventory - Category: {filter_value}"
        elif report_type == "condition" and filter_value:
            items = items[items["condition"] == filter_value]
            title = f"MCC Radio Inventory - Condition: {filter_value}"
        else:
            title = "MCC Radio Inventory"

        # Enhanced title styling
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.HexColor("#1976D2")
        )

        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(
            f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles["Normal"]))
        elements.append(Spacer(1, 20))

        # Enhanced summary for complete reports
        if report_type == "complete" and len(items) > 0:
            summary_data = [["Total Items", str(len(items))]]
            summary_table = Table(summary_data, colWidths=[2 * inch, 2 * inch])
            summary_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976D2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ])
            )
            elements.append(summary_table)
            elements.append(Spacer(1, 20))

            # Enhanced filtered reports with proper word wrapping
        if report_type in ["category", "condition", "location"] and filter_value and len(items) > 0:
            # Create enhanced table with better styling
            table_data = [["Item Name", "Category",
                           "Location", "Condition", "Notes"]]

            for _, item in items.iterrows():
                # Use Paragraph objects for proper word wrapping instead of truncating
                name_style = ParagraphStyle(
                    "name_style", fontSize=9, leading=11, wordWrap='CJK')  # Enable word wrapping
                cat_style = ParagraphStyle(
                    "cat_style", fontSize=9, leading=11, wordWrap='CJK')
                loc_style = ParagraphStyle(
                    "loc_style", fontSize=9, leading=11, wordWrap='CJK')
                notes_style = ParagraphStyle(
                    "notes_style", fontSize=9, leading=11, wordWrap='CJK')

                name = Paragraph(str(item["name"]), name_style)
                category = Paragraph(str(item["category"]), cat_style)
                location = Paragraph(str(item["location"]), loc_style)
                condition = str(item["condition"])
                notes = Paragraph(str(item["notes"]) if pd.notna(
                    item["notes"]) else "", notes_style)

                table_data.append([name, category, location, condition, notes])

            # Create table with enhanced styling and optimized column widths
            table = Table(
                table_data,
                # Optimized to fit 10" available width
                colWidths=[2.5 * inch, 1.8 * inch,
                           1.8 * inch, 1.2 * inch, 2.7 * inch],
                repeatRows=1
            )

            # Enable row splitting and proper text wrapping
            table.splitByRow = 1
            table.spaceAfter = 15
            table.hAlign = 'LEFT'
            # Ensure proper table breaking across pages
            table.repeatRows = 1
            table.repeatCols = 0

            table.setStyle(
                TableStyle([
                    # Enhanced header styling
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976D2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("TOPPADDING", (0, 0), (-1, 0), 12),
                    ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                    # Enhanced content styling with word wrap support
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#DEE2E6")),
                    ("VALIGN", (0, 1), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 1), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 1), (-1, -1), 10),
                    ("TOPPADDING", (0, 1), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                ])
            )

            # Add alternating row colors
            for i in range(1, len(table_data)):
                bg_color = colors.HexColor(
                    "#FFFFFF") if i % 2 == 0 else colors.HexColor("#F5F5F5")
                table.setStyle(TableStyle(
                    [("BACKGROUND", (0, i), (-1, i), bg_color)]))

            elements.append(table)

        # Enhanced complete reports with location-based grouping
        if report_type == "complete" and len(items) > 0:
            locations = get_locations()
            for location in sorted(locations):
                location_items = items[items["location"] == location]
                if len(location_items) > 0:
                    # Location header with enhanced styling
                    location_style = ParagraphStyle(
                        "LocationHeader",
                        parent=styles["Heading2"],
                        fontSize=16,
                        textColor=colors.HexColor("#2196F3"),
                        spaceAfter=15,
                        alignment=1,
                    )
                    elements.append(
                        Paragraph(f"{location} ({len(location_items)} items)", location_style))
                    elements.append(Spacer(1, 10))

                    # Enhanced table for this location
                    table_data = [
                        ["Item Name", "Category", "Condition", "Notes"]]

                    for _, item in location_items.iterrows():
                        # Use Paragraph objects for proper word wrapping instead of truncating
                        name_style = ParagraphStyle(
                            "name_style", fontSize=8, leading=10, wordWrap='CJK')  # Enable word wrapping
                        cat_style = ParagraphStyle(
                            "cat_style", fontSize=8, leading=10, wordWrap='CJK')
                        notes_style = ParagraphStyle(
                            "notes_style", fontSize=8, leading=10, wordWrap='CJK')

                        name = Paragraph(str(item["name"]), name_style)
                        category = Paragraph(str(item["category"]), cat_style)
                        condition = str(item["condition"])
                        notes = Paragraph(str(item["notes"]) if pd.notna(
                            item["notes"]) else "", notes_style)

                        table_data.append([name, category, condition, notes])

                    table = Table(
                        table_data,
                        # Optimized for complete report layout
                        colWidths=[2.5 * inch, 1.8 *
                                   inch, 1.2 * inch, 3.5 * inch],
                        repeatRows=1
                    )

                    table.splitByRow = 1
                    table.spaceAfter = 15
                    table.hAlign = 'LEFT'
                    # Ensure proper table breaking across pages
                    table.repeatRows = 1
                    table.repeatCols = 0

                    table.setStyle(
                        TableStyle([
                            # Enhanced header styling
                            ("BACKGROUND", (0, 0), (-1, 0),
                             colors.HexColor("#2196F3")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                            ("TOPPADDING", (0, 0), (-1, 0), 10),
                            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                            # Enhanced content styling with word wrap support
                            ("BACKGROUND", (0, 1), (-1, -1),
                             colors.HexColor("#F8F9FA")),
                            ("GRID", (0, 0), (-1, -1), 1,
                             colors.HexColor("#DEE2E6")),
                            ("VALIGN", (0, 1), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 1), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 1), (-1, -1), 8),
                            ("TOPPADDING", (0, 1), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                        ])
                    )

                    # Add alternating row colors
                    for i in range(1, len(table_data)):
                        bg_color = colors.HexColor(
                            "#FFFFFF") if i % 2 == 0 else colors.HexColor("#F5F5F5")
                        table.setStyle(TableStyle(
                            [("BACKGROUND", (0, i), (-1, i), bg_color)]))

                    elements.append(table)
                    elements.append(Spacer(1, 20))

        # Build PDF with error handling
        doc.build(elements)

    except Exception as e:
        # If PDF generation fails, create a minimal fallback PDF
        print(f"PDF generation error: {e}")
        buffer = create_fallback_pdf()

    buffer.seek(0)
    return buffer


def create_fallback_pdf():
    """Create a minimal fallback PDF when main generation fails"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    elements = []

    elements.append(
        Paragraph("RadioTrack Inventory Report", styles["Heading1"]))
    elements.append(
        Paragraph("PDF generation encountered an issue.", styles["Normal"]))
    elements.append(Paragraph(
        "Please check the application data and try again.", styles["Normal"]))

    doc.build(elements)
    return buffer


# Legacy functions removed for browser compatibility
# These complex functions were causing PDF parsing issues in browsers
