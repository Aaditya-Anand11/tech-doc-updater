"""
PDF Documentation Generator for EcoStruxure Device Manager
Creates a professional PDF user manual with embedded GUI screenshot.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, 
    PageBreak, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
import os

# Configuration
IMAGE_PATH = r"C:\Users\mdiza\OneDrive\Pictures\Screenshots 1\Screenshot 2026-01-23 163920.png"
OUTPUT_PDF = r"c:\Users\mdiza\coding\Schneider_hackathon_new\data\test_examples\EcoStruxure_User_Manual.pdf"

def create_pdf_documentation(image_path: str, output_path: str):
    """Generate PDF documentation with embedded image."""
    
    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=20,
        textColor=HexColor('#3dcd58'),
        alignment=TA_CENTER
    )
    
    heading1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=18,
        spaceBefore=20,
        spaceAfter=10,
        textColor=HexColor('#1a1a2e')
    )
    
    heading2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=8,
        textColor=HexColor('#2c9c47')
    )
    
    heading3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=6,
        textColor=HexColor('#333333')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        alignment=TA_JUSTIFY,
        leading=14
    )
    
    caption_style = ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=HexColor('#666666'),
        spaceAfter=15
    )
    
    # Build content
    content = []
    
    # ===== TITLE PAGE =====
    content.append(Spacer(1, 2*inch))
    content.append(Paragraph("ECOSTRUXURE DEVICE MANAGER", title_style))
    content.append(Paragraph("User Manual", ParagraphStyle(
        'Subtitle', parent=styles['Title'], fontSize=16, textColor=HexColor('#666666')
    )))
    content.append(Spacer(1, 0.5*inch))
    content.append(Paragraph("Version 2.1.0", body_style))
    content.append(Paragraph("January 2026", body_style))
    content.append(Spacer(1, 1*inch))
    content.append(Paragraph("Schneider Electric", ParagraphStyle(
        'Company', parent=styles['Normal'], fontSize=12, textColor=HexColor('#3dcd58'), alignment=TA_CENTER
    )))
    content.append(PageBreak())
    
    # ===== DOCUMENT INFORMATION =====
    content.append(Paragraph("DOCUMENT INFORMATION", heading1_style))
    
    doc_info = [
        ['Document Version:', '2.1.0'],
        ['Last Updated:', 'January 2026'],
        ['Product:', 'EcoStruxure Device Manager'],
        ['Manufacturer:', 'Schneider Electric'],
    ]
    
    info_table = Table(doc_info, colWidths=[2.5*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#3dcd58')),
    ]))
    content.append(info_table)
    content.append(Spacer(1, 0.5*inch))
    
    # ===== TABLE OF CONTENTS =====
    content.append(Paragraph("TABLE OF CONTENTS", heading1_style))
    toc_items = [
        "1. Introduction",
        "2. System Requirements",
        "3. User Interface Overview",
        "4. Dashboard",
        "5. Navigation Menu",
        "6. Device Management",
        "7. Troubleshooting"
    ]
    for item in toc_items:
        content.append(Paragraph(item, body_style))
    content.append(PageBreak())
    
    # ===== 1. INTRODUCTION =====
    content.append(Paragraph("1. INTRODUCTION", heading1_style))
    content.append(Paragraph(
        "EcoStruxure Device Manager is a comprehensive platform for monitoring and managing "
        "industrial electrical devices. This application provides real-time visibility into your "
        "connected devices, enabling efficient energy management and predictive maintenance.",
        body_style
    ))
    content.append(Spacer(1, 0.2*inch))
    
    content.append(Paragraph("Key Features:", heading3_style))
    features = [
        "Real-time device monitoring",
        "Centralized dashboard with system overview",
        "Alert and notification management",
        "User access control",
        "Comprehensive reporting"
    ]
    for feature in features:
        content.append(Paragraph(f"• {feature}", body_style))
    content.append(Spacer(1, 0.3*inch))
    
    # ===== 2. SYSTEM REQUIREMENTS =====
    content.append(Paragraph("2. SYSTEM REQUIREMENTS", heading1_style))
    
    content.append(Paragraph("Minimum Requirements:", heading3_style))
    requirements = [
        "Modern web browser (Chrome, Firefox, Edge)",
        "Internet connection",
        "Screen resolution: 1280x720 or higher",
        "JavaScript enabled"
    ]
    for req in requirements:
        content.append(Paragraph(f"• {req}", body_style))
    content.append(PageBreak())
    
    # ===== 3. USER INTERFACE OVERVIEW =====
    content.append(Paragraph("3. USER INTERFACE OVERVIEW", heading1_style))
    content.append(Paragraph(
        "The EcoStruxure Device Manager interface consists of three main areas: "
        "the Header Bar, Sidebar Navigation, and Main Content Area.",
        body_style
    ))
    content.append(Spacer(1, 0.2*inch))
    
    # Add the screenshot image
    content.append(Paragraph("Dashboard Overview:", heading2_style))
    
    if os.path.exists(image_path):
        # Calculate image dimensions to fit the page
        img = Image(image_path)
        # Get original dimensions
        img_width = img.imageWidth
        img_height = img.imageHeight
        
        # Scale to fit page width (max 6 inches)
        max_width = 6 * inch
        max_height = 4 * inch
        
        aspect_ratio = img_width / img_height
        
        if img_width > max_width:
            new_width = max_width
            new_height = new_width / aspect_ratio
        else:
            new_width = img_width
            new_height = img_height
            
        if new_height > max_height:
            new_height = max_height
            new_width = new_height * aspect_ratio
        
        img = Image(image_path, width=new_width, height=new_height)
        content.append(img)
        content.append(Paragraph("Figure 1: EcoStruxure Device Manager - Dashboard View", caption_style))
    else:
        content.append(Paragraph(f"[Image not found: {image_path}]", caption_style))
    
    content.append(Spacer(1, 0.2*inch))
    
    # ===== 3.1 HEADER BAR =====
    content.append(Paragraph("3.1 Header Bar", heading2_style))
    header_info = [
        ['Location:', 'Top of the screen'],
        ['Background:', 'Green gradient (#3dcd58 to #2c9c47)'],
    ]
    header_table = Table(header_info, colWidths=[1.5*inch, 4.5*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    content.append(header_table)
    content.append(Spacer(1, 0.1*inch))
    
    content.append(Paragraph("Components:", heading3_style))
    components = [
        '<b>Logo:</b> "SE" icon followed by "EcoStruxure Device Manager" text',
        '<b>Notifications button:</b> Displays "🔔 Notifications"',
        '<b>Settings button:</b> Displays "⚙️ Settings"',
        '<b>User information:</b> Avatar with initials and username'
    ]
    for comp in components:
        content.append(Paragraph(f"• {comp}", body_style))
    
    # ===== 3.2 SIDEBAR NAVIGATION =====
    content.append(Paragraph("3.2 Sidebar Navigation", heading2_style))
    sidebar_info = [
        ['Location:', 'Left side of the screen'],
        ['Background:', 'Dark blue (#1a1a2e)'],
        ['Width:', '250 pixels'],
    ]
    sidebar_table = Table(sidebar_info, colWidths=[1.5*inch, 4.5*inch])
    sidebar_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    content.append(sidebar_table)
    content.append(Spacer(1, 0.1*inch))
    
    content.append(Paragraph("MAIN MENU Section:", heading3_style))
    main_menu = [
        "Dashboard (📊 icon) - System overview",
        "Devices (🔌 icon) - Device list and management",
        "Analytics (📈 icon) - Data analysis and trends",
        "Alerts (⚠️ icon) - Warning and notification center"
    ]
    for item in main_menu:
        content.append(Paragraph(f"• {item}", body_style))
    
    content.append(Paragraph("MANAGEMENT Section:", heading3_style))
    mgmt_menu = [
        "Users (👥 icon) - User account management",
        "Reports (📋 icon) - Generate and view reports",
        "Configuration (🔧 icon) - System settings"
    ]
    for item in mgmt_menu:
        content.append(Paragraph(f"• {item}", body_style))
    
    content.append(PageBreak())
    
    # ===== 4. DASHBOARD =====
    content.append(Paragraph("4. DASHBOARD", heading1_style))
    
    # 4.1 Page Header
    content.append(Paragraph("4.1 Page Header", heading2_style))
    page_header = [
        ['Title:', 'Dashboard (28px font size)'],
        ['Subtitle:', 'Welcome back, John! Here\'s your system overview.'],
        ['Primary Action:', '+ Add New Device (green button)'],
    ]
    ph_table = Table(page_header, colWidths=[1.5*inch, 4.5*inch])
    ph_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    content.append(ph_table)
    
    # 4.2 Statistics Cards
    content.append(Paragraph("4.2 Statistics Cards", heading2_style))
    content.append(Paragraph("Layout: 4 cards in a horizontal grid", body_style))
    content.append(Paragraph("Card Style: White background, rounded corners (12px), shadow effect", body_style))
    content.append(Spacer(1, 0.1*inch))
    
    stats_data = [
        ['Card', 'Icon', 'Value', 'Label', 'Change Indicator'],
        ['1', 'Green plug', '24', 'Total Devices', '↑ 12% from last month'],
        ['2', 'Blue checkmark', '21', 'Online Devices', '↑ 5% from last week'],
        ['3', 'Orange warning', '3', 'Warnings', '↑ 2 new today'],
        ['4', 'Red X', '0', 'Critical Alerts', 'No issues detected'],
    ]
    
    stats_table = Table(stats_data, colWidths=[0.5*inch, 1.2*inch, 0.6*inch, 1.2*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3dcd58')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#dddddd')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    content.append(stats_table)
    
    # 4.3 Connected Devices Table
    content.append(Paragraph("4.3 Connected Devices Table", heading2_style))
    content.append(Paragraph("Section Title: Connected Devices", body_style))
    content.append(Paragraph("Search Box: Located at top right, placeholder text \"Search devices...\"", body_style))
    content.append(Spacer(1, 0.1*inch))
    
    content.append(Paragraph("Table Columns:", heading3_style))
    columns = [
        "Device Name - Includes icon, name, and device ID",
        "Type - Device category",
        "Location - Physical installation location",
        "Status - Online/Offline/Warning indicator",
        "Last Update - Time since last communication",
        "Actions - View and Edit buttons"
    ]
    for i, col in enumerate(columns, 1):
        content.append(Paragraph(f"{i}. {col}", body_style))
    
    content.append(Paragraph("Status Indicators:", heading3_style))
    status_data = [
        ['Status', 'Appearance'],
        ['Online', 'Green badge with "● Online" text'],
        ['Offline', 'Gray badge with "○ Offline" text'],
        ['Warning', 'Orange badge with "⚠ Warning" text'],
    ]
    status_table = Table(status_data, colWidths=[1.5*inch, 4*inch])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3dcd58')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#dddddd')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    content.append(status_table)
    
    content.append(Paragraph("Sample Devices:", heading3_style))
    device_data = [
        ['Device', 'ID', 'Type', 'Location', 'Status'],
        ['Power Meter PM5560', 'DEV-001', 'Power Meter', 'Building A - Floor 1', 'Online'],
        ['Temperature Sensor TS-200', 'DEV-002', 'Sensor', 'Building A - Floor 2', 'Online'],
        ['Circuit Breaker CB-150', 'DEV-003', 'Breaker', 'Building B - Basement', 'Warning'],
    ]
    device_table = Table(device_data, colWidths=[1.8*inch, 0.8*inch, 1*inch, 1.5*inch, 0.8*inch])
    device_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#dddddd')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    content.append(device_table)
    
    content.append(PageBreak())
    
    # ===== 5. NAVIGATION MENU =====
    content.append(Paragraph("5. NAVIGATION MENU", heading1_style))
    
    content.append(Paragraph("5.1 Accessing Menu Items", heading2_style))
    content.append(Paragraph(
        "Click on any menu item in the sidebar to navigate to that section. "
        "The currently active page is highlighted with a green left border (#3dcd58), "
        "green text color, and slightly darker background.",
        body_style
    ))
    
    content.append(Paragraph("5.2 Menu Structure", heading2_style))
    content.append(Paragraph("MAIN MENU:", heading3_style))
    main_nav = [
        "├── Dashboard - Overview of all systems",
        "├── Devices - Complete device inventory",
        "├── Analytics - Charts and data analysis",
        "└── Alerts - Active warnings and alerts"
    ]
    for item in main_nav:
        content.append(Paragraph(item, body_style))
    
    content.append(Paragraph("MANAGEMENT:", heading3_style))
    mgmt_nav = [
        "├── Users - User account administration",
        "├── Reports - Report generation",
        "└── Configuration - System configuration"
    ]
    for item in mgmt_nav:
        content.append(Paragraph(item, body_style))
    
    # ===== 6. DEVICE MANAGEMENT =====
    content.append(Paragraph("6. DEVICE MANAGEMENT", heading1_style))
    
    content.append(Paragraph("6.1 Adding a New Device", heading2_style))
    add_steps = [
        'Click the "+ Add New Device" button on the Dashboard',
        'Fill in the required device information',
        'Select device type from dropdown',
        'Assign location',
        'Click "Save" to add the device'
    ]
    for i, step in enumerate(add_steps, 1):
        content.append(Paragraph(f"{i}. {step}", body_style))
    
    content.append(Paragraph("6.2 Viewing Device Details", heading2_style))
    view_steps = [
        'Locate the device in the Connected Devices table',
        'Click the "View" button in the Actions column',
        'Review device status, history, and configuration'
    ]
    for i, step in enumerate(view_steps, 1):
        content.append(Paragraph(f"{i}. {step}", body_style))
    
    content.append(Paragraph("6.3 Editing Device Settings", heading2_style))
    edit_steps = [
        'Click the "Edit" button next to the target device',
        'Modify the desired settings',
        'Click "Save" to apply changes'
    ]
    for i, step in enumerate(edit_steps, 1):
        content.append(Paragraph(f"{i}. {step}", body_style))
    
    # ===== 7. TROUBLESHOOTING =====
    content.append(Paragraph("7. TROUBLESHOOTING", heading1_style))
    
    content.append(Paragraph("Device shows 'Offline' status", heading2_style))
    content.append(Paragraph("<b>Solution:</b>", body_style))
    offline_solutions = [
        "Check network connectivity",
        "Verify device power supply",
        "Restart the device if necessary"
    ]
    for sol in offline_solutions:
        content.append(Paragraph(f"• {sol}", body_style))
    
    content.append(Paragraph("Warning status displayed", heading2_style))
    content.append(Paragraph("<b>Solution:</b>", body_style))
    warning_solutions = [
        "Click on the device to view warning details",
        'Address the specific issue indicated',
        'Monitor device until status returns to "Online"'
    ]
    for sol in warning_solutions:
        content.append(Paragraph(f"• {sol}", body_style))
    
    content.append(Spacer(1, 0.5*inch))
    
    # ===== FOOTER =====
    content.append(Paragraph("Application Footer:", heading2_style))
    content.append(Paragraph(
        '"© 2026 Schneider Electric. All rights reserved. | Version 2.1.0"',
        ParagraphStyle('Footer', parent=body_style, alignment=TA_CENTER, textColor=HexColor('#666666'))
    ))
    
    content.append(Spacer(1, 0.5*inch))
    content.append(Paragraph("— END OF USER MANUAL —", ParagraphStyle(
        'EndDoc', parent=body_style, alignment=TA_CENTER, fontSize=12, textColor=HexColor('#3dcd58')
    )))
    
    # Build PDF
    doc.build(content)
    print(f"[SUCCESS] PDF created successfully: {output_path}")
    return output_path

if __name__ == "__main__":
    create_pdf_documentation(IMAGE_PATH, OUTPUT_PDF)
