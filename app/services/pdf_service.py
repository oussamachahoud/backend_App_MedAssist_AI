from xml.sax.saxutils import escape as xml_escape
"""
app/services/pdf_service.py
Service for generating professional medical PDF reports for lesion analyses,
including clinical metrics, risk indicators, doctor feedback, and patient follow-up QR code.
"""

import io
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import qrcode
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db_models.analysis import AnalysisRecord
from app.db_models.patient import Patient
from app.db_models.user import DoctorProfile


def _generate_qr_flowable(qr_content: str, size: float = 85.0) -> Image:
    """Generate a ReportLab Image Flowable containing a QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return Image(img_buffer, width=size, height=size)


def _safe_str(val, default='N/A'):
    if val is None or str(val).strip() == '':
        return default
    return xml_escape(str(val).strip())


def generate_analysis_pdf(
    analysis: AnalysisRecord,
    doctor_profile: Optional[DoctorProfile] = None,
    patient: Optional[Patient] = None,
    qr_token: Optional[str] = None,
    base_url: str = "https://medassist.dz",
) -> bytes:
    """
    Generate an official, structured medical PDF report for a given AnalysisRecord.

    Args:
        analysis: The AnalysisRecord database instance.
        doctor_profile: Profile of the examining physician (optional).
        patient: Associated pseudonymous patient record (optional).
        qr_token: Signed JWT token for patient QR follow-up.
        base_url: Base domain for patient follow-up URL.

    Returns:
        bytes: Raw PDF document bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=8,
        spaceAfter=4,
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_normal = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
    )

    story: List[Any] = []

    # ── 1. Document Header ───────────────────────────────────────────────────
    header_data = [
        [
            Paragraph("<b>MedAssist AI Telemedicine</b><br/>Clinical Dermatology Decision Support", title_style),
            Paragraph(
                f"<b>Report ID:</b> {str(analysis.id)[:8]}...<br/>"
                f"<b>Date:</b> {analysis.created_at.strftime('%Y-%m-%d %H:%M') if analysis.created_at else 'N/A'}<br/>"
                f"<b>Model:</b> {analysis.model_version}",
                subtitle_style,
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[340, 180])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=12))

    # ── 2. Doctor & Patient Info ─────────────────────────────────────────────
    dr_name = doctor_profile.full_name if doctor_profile else "Authorized Clinician"
    dr_type = doctor_profile.doctor_type.value.replace("_", " ").title() if (doctor_profile and hasattr(doctor_profile.doctor_type, "value")) else "Practitioner"
    dr_inst = (doctor_profile.institution_name or "Hospital / Clinic") if doctor_profile else "General Practice"
    dr_wilaya = f"Wilaya {doctor_profile.wilaya}" if (doctor_profile and doctor_profile.wilaya) else ""

    pt_code = patient.patient_code if patient else "Pseudonymous / Mobile Triage"
    pt_birth = str(patient.birth_year) if patient else "N/A"
    pt_sex = patient.sex.value.capitalize() if (patient and hasattr(patient.sex, "value")) else "N/A"
    lesion_tag = analysis.lesion_tag or "Unspecified site"

    meta_table_data = [
        [
            Paragraph("<b>EXAMINING PHYSICIAN</b>", cell_bold),
            Paragraph("<b>PATIENT & LESION FILE</b>", cell_bold),
        ],
        [
            Paragraph(
                f"<b>Dr.</b> {_safe_str(dr_name)}<br/>"
                f"<b>Role:</b> {dr_type}<br/>"
                f"<b>Institution:</b> {dr_inst} {dr_wilaya}",
                cell_normal,
            ),
            Paragraph(
                f"<b>Patient ID:</b> {_safe_str(pt_code)}<br/>"
                f"<b>Birth Year:</b> {pt_birth} | <b>Sex:</b> {pt_sex}<br/>"
                f"<b>Lesion Site / Tag:</b> {lesion_tag}",
                cell_normal,
            ),
        ],
    ]
    meta_table = Table(meta_table_data, colWidths=[260, 260])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # ── 3. Diagnostic AI Findings ────────────────────────────────────────────
    story.append(Paragraph("Diagnostic AI Inference & Risk Evaluation", section_heading))

    risk_colors_map = {
        "LOW": colors.HexColor("#10b981"),
        "MODERATE": colors.HexColor("#f59e0b"),
        "HIGH": colors.HexColor("#ef4444"),
        "CRITICAL": colors.HexColor("#7f1d1d"),
        "INCONCLUSIVE": colors.HexColor("#64748b"),
    }
    risk_color = risk_colors_map.get(str(analysis.risk_level).upper(), colors.HexColor("#2563eb"))

    confidence_pct = f"{analysis.confidence * 100:.1f}%"
    findings_data = [
        [
            Paragraph("<b>Predicted Pathology:</b>", cell_bold),
            Paragraph(f"<b>{analysis.predicted_class}</b>", cell_bold),
            Paragraph("<b>Clinical Risk Level:</b>", cell_bold),
            Paragraph(f"<font color='{risk_color.hexval()}'><b>{analysis.risk_level.upper()}</b></font>", cell_bold),
        ],
        [
            Paragraph("<b>Model Confidence:</b>", cell_bold),
            Paragraph(confidence_pct, cell_normal),
            Paragraph("<b>Inference Latency:</b>", cell_bold),
            Paragraph(f"{analysis.inference_time_ms:.1f} ms", cell_normal),
        ],
        [
            Paragraph("<b>Risk Escalation:</b>", cell_bold),
            Paragraph("Yes (Active Alert)" if analysis.risk_escalated else "No (Standard Protocol)", cell_normal),
            Paragraph("<b>Biopsy Recommended:</b>", cell_bold),
            Paragraph("Yes" if analysis.risk_level in ["HIGH", "CRITICAL", "INCONCLUSIVE"] else "Optional/Follow-up", cell_normal),
        ],
    ]
    findings_table = Table(findings_data, colWidths=[120, 140, 130, 130])
    findings_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(findings_table)
    story.append(Spacer(1, 12))

    # ── 4. Differential Class Probabilities ─────────────────────────────────
    if analysis.all_probabilities:
        story.append(Paragraph("Differential Diagnosis Probabilities", section_heading))
        prob_headers = [Paragraph(f"<b>{cls}</b>", cell_bold) for cls in analysis.all_probabilities.keys()]
        prob_values = [
            Paragraph(f"{val * 100:.1f}%", cell_normal) for val in analysis.all_probabilities.values()
        ]
        col_w = 520.0 / max(len(prob_headers), 1)
        prob_table = Table([prob_headers, prob_values], colWidths=[col_w] * len(prob_headers))
        prob_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(prob_table)
        story.append(Spacer(1, 12))

    # ── 5. Doctor Review & Clinical Feedback ─────────────────────────────────
    story.append(Paragraph("Doctor Clinical Validation & Action Plan", section_heading))
    confirmed_str = (
        "Confirmed by Doctor"
        if analysis.doctor_confirmed is True
        else ("Rejected / Overridden" if analysis.doctor_confirmed is False else "Pending Clinical Review")
    )
    feedback_data = [
        [
            Paragraph("<b>Doctor Status:</b>", cell_bold),
            Paragraph(confirmed_str, cell_normal),
            Paragraph("<b>Confirmed Diagnosis:</b>", cell_bold),
            Paragraph(_safe_str(analysis.doctor_diagnosis, "Pending"), cell_normal),
        ],
        [
            Paragraph("<b>Biopsy Performed:</b>", cell_bold),
            Paragraph(
                "Yes" if analysis.biopsy_performed is True else ("No" if analysis.biopsy_performed is False else "Not recorded"),
                cell_normal,
            ),
            Paragraph("<b>Biopsy Result:</b>", cell_bold),
            Paragraph(_safe_str(analysis.biopsy_result, "N/A"), cell_normal),
        ],
        [
            Paragraph("<b>Next Follow-up Date:</b>", cell_bold),
            Paragraph(str(analysis.next_followup_date) if analysis.next_followup_date else "Not scheduled", cell_normal),
            Paragraph("<b>Storage Key:</b>", cell_bold),
            Paragraph(str(analysis.image_storage_key)[:25] + "...", cell_normal),
        ],
    ]
    fb_table = Table(feedback_data, colWidths=[120, 140, 130, 130])
    fb_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(fb_table)
    story.append(Spacer(1, 14))

    # ── 6. Recommendations & Patient QR Follow-up ────────────────────────────
    follow_up_url = (
        f"{base_url}/dashboard/follow-up.html?token={qr_token}"
        if qr_token
        else f"{base_url}/api/v1/analyses/{analysis.id}"
    )
    qr_image = _generate_qr_flowable(follow_up_url, size=80.0)

    recs_list = analysis.recommendations or ["Consult dermatologist for suspicious lesions.", "Monitor changes via ABCDE protocol."]
    if isinstance(recs_list, list):
        recs_text = "<br/>".join([f"• {r}" for r in recs_list])
    else:
        recs_text = str(recs_list)

    recs_qr_data = [
        [
            Paragraph(
                f"<b>Clinical Recommendations:</b><br/>{recs_text}<br/><br/>"
                f"<font size='8' color='#64748b'>To verify this report or check follow-up instructions, "
                f"scan the patient QR code or visit the official telemedicine portal.</font>",
                cell_normal,
            ),
            qr_image,
        ]
    ]
    recs_qr_table = Table(recs_qr_data, colWidths=[420, 100])
    recs_qr_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(recs_qr_table)
    story.append(Spacer(1, 16))

    # ── 7. Medical Disclaimer Footer ─────────────────────────────────────────
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=6)
    )
    disclaimer_text = (
        "CONFIDENTIAL MEDICAL REPORT — For Healthcare Professional Decision Support Only.<br/>"
        "This automated computer-aided analysis was generated using MedAssist AI deep neural networks. "
        "It does not substitute for a comprehensive clinical examination, dermoscopic assessment, "
        "or histopathological diagnosis. MedAssist AI Telemedicine Platform (Algeria)."
    )
    story.append(Paragraph(disclaimer_text, disclaimer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

