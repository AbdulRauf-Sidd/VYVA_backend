"""
Email service for sending emails using Mailgun API.
"""

import requests
import httpx
from typing import List, Optional, Dict, Union
from core.config import settings
from core.logging import get_logger
from services.helpers import generate_random_string
from datetime import datetime, timezone

logger = get_logger(__name__)


class EmailService:
    """Email service for sending emails via Mailgun."""

    def __init__(self):
        self.api_key = settings.MAILGUN_API_KEY
        self.api_url = settings.MAILGUN_API_URL or "https://api.eu.mailgun.net/v3/vyva.life/messages"
        self.from_email = "VYVA Health <postmaster@vyva.life>"

    async def send_email_via_mailgun(
        self,
        to: List[str],
        subject: str,
        text: Optional[str] = None,
        html: Optional[str] = None,
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Union[str, int]]:
        """
        Send an email using Mailgun's API.
        """
        try:
            if not self.api_key:
                raise ValueError("Mailgun API key is not configured")

            if not self.api_url:
                raise ValueError("Mailgun API URL is not configured")

            # Prepare authentication
            auth = ("api", self.api_key)

            # Prepare email data
            data = {
                "from": from_email or self.from_email,
                "to": ", ".join(to),
                "subject": subject,
            }

            if text:
                data["text"] = text
            if html:
                data["html"] = html
            if cc:
                data["cc"] = ", ".join(cc)
            if bcc:
                data["bcc"] = ", ".join(bcc)

            # Handle attachments
            files = []
            if attachments:
                for attachment in attachments:
                    if "file_data" in attachment:
                        files.append(
                            ("attachment",
                             (attachment["file_name"], attachment["file_data"]))
                        )
                    elif "file_url" in attachment:
                        data.setdefault("attachment", []).append(
                            attachment["file_url"])

            # Send the email
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    auth=auth,
                    data=data,
                    files=files,
                    headers=headers or {},
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Email sent successfully to {to}. Message ID: {result.get('id', 'unknown')}")
                return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Mailgun API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Failed to send email: {e.response.text}")
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            raise Exception(f"Failed to send email: {str(e)}")

    async def send_medical_report(
        self,
        recipient_email: str,
        report_content: Dict[str, any]
    ) -> bool:
        """
        Send a medical report email with the provided content.
        """
        try:
            subject = "Su Evaluación de Síntomas VYVA Health"

            # Extract content for email template
            symptoms = report_content.get('symptoms', 'N/A')
            duration = report_content.get('duration', 'N/A')
            pain_level = report_content.get('pain_level', 'N/A')
            additional_notes = report_content.get('additional_notes', 'N/A')
            analysis_content = report_content.get(
                'email', 'N/A')  # Use 'email' field from database
            severity = report_content.get('severity', 'N/A')
            user_id = report_content.get('user_id', 'N/A')
            # Use 'conversation_id' field
            record_id = report_content.get('conversation_id', 'N/A')
            created_at = report_content.get('created_at', 'N/A')

            # Get vitals information
            vitals = report_content.get('vitals', {})
            heart_rate = vitals.get('heart_rate', {})
            respiratory_rate = vitals.get('respiratory_rate', {})

            # Build HTML email body
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }}
                    .header {{ background-color: #642997; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .section {{ margin-bottom: 25px; }}
                    .section-title {{ color: #642997; font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 2px solid #642997; padding-bottom: 5px; }}
                    .symptom-item {{ background-color: #f8f9fa; padding: 10px; margin: 5px 0; border-left: 4px solid #642997; }}
                    .severity {{ padding: 15px; text-align: center; font-weight: bold; border-radius: 5px; }}
                    .severe {{ background-color: #ffe6e6; color: #d63384; border: 2px solid #d63384; }}
                    .mild {{ background-color: #e6ffe6; color: #198754; border: 2px solid #198754; }}
                    .analysis {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
                    .disclaimer {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; color: #856404; border: 1px solid #ffeaa7; }}
                    .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; color: #666; }}
                    .vitals {{ background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                    .vital-item {{ margin: 10px 0; }}
                    .logo img{{ max-width:100%; }}
                    .logo_div{{ width:20%; padding:26px 0px 8px 19px; }}
                    .main{{ width:100%; display:flex; }}
                    .second_div{{ width:74%; margin:20px 0px 0px; }}
                </style>
            </head>
            <body>
                <div class="header">
                <div class="main">
                    <div class="logo logo_div"><img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png"></div>
                    <div class="second_div">
                    <h1 style="color:#FFF; font-size:20px; text-align:right;">Verificador de Síntomas</h1>
                    </div>
                </div>
                </div>
                <div class="content">
                    <h2>Estimado Usuario,</h2>
                    <p>Gracias por usar el Verificador de Síntomas VYVA. Aquí está su evaluación detallada de síntomas:</p>
                    
                    <div class="section">
                        <div class="section-title">📋 Síntomas Reportados</div>
                        <div class="symptom-item"><strong>Síntomas:</strong> {symptoms}</div>
                        <div class="symptom-item"><strong>Duración:</strong> {duration}</div>
                        <div class="symptom-item"><strong>Nivel de Dolor:</strong> {pain_level}</div>
                        <div class="symptom-item"><strong>Notas Adicionales:</strong> {additional_notes}</div>
                    </div>
            """

            # Add vitals section if available
            if heart_rate.get('value') or respiratory_rate.get('value'):
                html_body += """
                    <div class="section">
                        <div class="section-title">🩺 Signos Vitales</div>
                        <div class="vitals">
                """

                if heart_rate.get('value'):
                    html_body += f"""
                            <div class="vital-item">
                                <div style="font-weight: bold; color: #d32f2f;">❤️ Frecuencia Cardíaca</div>
                                <div style="font-size: 14px; color: #d32f2f;">Valor: {heart_rate.get('value', '—')} {heart_rate.get('unit', 'lpm')}</div>
                            </div>
                    """

                if respiratory_rate.get('value'):
                    html_body += f"""
                            <div class="vital-item">
                                <div style="font-weight: bold; color: #1976d2;">🫁 Frecuencia Respiratoria</div>
                                <div style="font-size: 14px; color: #1976d2;">Valor: {respiratory_rate.get('value', '—')} {respiratory_rate.get('unit', 'respiraciones/min')}</div>
                            </div>
                    """

                html_body += """
                        </div>
                    </div>
                """

            # Continue with the rest of the email
            html_body += f"""
                    <div class="section">
                        <div class="section-title">🩺 Análisis Médico</div>
                        <div class="analysis">{analysis_content}</div>
                    </div>
                    
                    <div class="section">
                        <div class="section-title">⚠️ Evaluación de Gravedad</div>
                        <div class="severity {'severe' if severity.lower() == 'severe' else 'mild'}">
                            <strong>Clasificación:</strong> <span style="text-transform: uppercase;">{severity}</span>
                        </div>
                    </div>
                    
                    <div class="disclaimer">
                        <strong>⚠️ Descargo de Responsabilidad Importante:</strong><br>
                        Esta evaluación es solo para fines informativos. Por favor, consulte con un profesional de la salud para obtener asesoramiento médico adecuado.
                    </div>
                    
                    <div style="margin-top: 30px;">
                        <p><strong>ID de Registro:</strong> {record_id}</p>
                        <p><strong>Fecha de Evaluación:</strong> {created_at}</p>
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>Saludos cordiales,<br>Equipo del Verificador de Síntomas VYVA</strong></p>
                    <p style="font-size: 12px; color: #999;">Este correo fue generado automáticamente por el Sistema Verificador de Síntomas VYVA</p>
                </div>
            </body>
            </html>
            """

            # Send the email
            result = await self.send_email_via_mailgun(
                to=[recipient_email],
                subject=subject,
                html=html_body
            )

            logger.info(
                f"Medical report sent successfully to {recipient_email}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send medical report to {recipient_email}: {str(e)}")
            return False

    async def send_brain_coach_report(
        self,
        recipient_email: str,
        report_content: List[Dict[str, any]],
        name: Optional[str] = "N/A",
        suggestions: Optional[str] = None,
        performance_tier: Optional[str] = None,
        language: Optional[str] = 'en'
    ):
        tier = report_content[0].get(
            'tier', 'N/A') if report_content else 'N/A'
        session_id = generate_random_string(6)
        current_date = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

        user_score = 0
        total_max_score = 0
        table_rows_html = ''
        for item in report_content:
            score = item.get('score', 0)
            max_score = item.get('max_score', 0)
            user_score += score
            total_max_score += max_score
            ratio = score / max_score if max_score else 0
            badge_cls = 'badge-high' if ratio >= 0.75 else ('badge-mid' if ratio >= 0.5 else 'badge-low')
            domain = item.get('question_type', '')
            question = item.get('question_text', '')
            table_rows_html += (
                f'<tr><td class="domain">{domain}</td>'
                f'<td>{question}</td>'
                f'<td class="score-cell"><span class="badge {badge_cls}">{score} / {max_score}</span></td></tr>\n'
            )

        lang_code = 'es' if language.lower() in ('es', 'spanish') else ('de' if language.lower() in ('de', 'german') else 'en')

        labels = {
            'en': {
                'title': 'Daily Cognitive Session Report',
                'sub': 'Your Daily Cognitive Assessment Summary',
                'details': 'Session Details',
                'scores': 'Activity Domain Scores',
                'notes': 'Agent Notes & Suggestions',
                'l_name': 'Name',
                'l_tier': 'Cognitive Tier',
                'v_tier': f'Tier {tier} – Moderate Impairment',
                'l_date': 'Date',
                'l_sid': 'Session ID',
                'l_done': 'Session Completed',
                'v_done': 'Yes',
                'c_domain': 'Domain',
                'c_question': 'Question / Activity',
                'c_score': 'Score',
                'l_total': 'Total Score',
                'l_perf': 'Performance Tier',
                'n_heading': 'Personalized Recommendations',
                'footer': 'Generated automatically by VYVA Brain Coach',
            },
            'de': {
                'title': 'Täglicher Kognitiver Sitzungsbericht',
                'sub': 'Ihre tägliche kognitive Bewertungszusammenfassung',
                'details': 'Sitzungsdetails',
                'scores': 'Aktivitätsdomänen-Bewertungen',
                'notes': 'Agenten-Hinweise & Empfehlungen',
                'l_name': 'Name',
                'l_tier': 'Kognitive Stufe',
                'v_tier': f'Stufe {tier} – Mittlere Beeinträchtigung',
                'l_date': 'Datum',
                'l_sid': 'Sitzungs-ID',
                'l_done': 'Sitzung abgeschlossen',
                'v_done': 'Ja',
                'c_domain': 'Domäne',
                'c_question': 'Frage / Aktivität',
                'c_score': 'Punkte',
                'l_total': 'Gesamtpunktzahl',
                'l_perf': 'Leistungsstufe',
                'n_heading': 'Personalisierte Empfehlungen',
                'footer': 'Automatisch generiert von VYVA Brain Coach',
            },
            'es': {
                'title': 'Informe Diario de Sesión Cognitiva',
                'sub': 'Su Resumen Diario de Evaluación Cognitiva',
                'details': 'Detalles de la Sesión',
                'scores': 'Puntuaciones por Dominio de Actividad',
                'notes': 'Notas y Sugerencias del Agente',
                'l_name': 'Nombre',
                'l_tier': 'Nivel Cognitivo',
                'v_tier': f'Nivel {tier} – Deterioro Moderado',
                'l_date': 'Fecha',
                'l_sid': 'ID de Sesión',
                'l_done': 'Sesión Completada',
                'v_done': 'Sí',
                'c_domain': 'Dominio',
                'c_question': 'Pregunta / Actividad',
                'c_score': 'Puntaje',
                'l_total': 'Puntaje Total',
                'l_perf': 'Nivel de Rendimiento',
                'n_heading': 'Recomendaciones Personalizadas',
                'footer': 'Generado automáticamente por VYVA Brain Coach',
            },
        }

        t = labels[lang_code]

        html = f"""<!DOCTYPE html>
<html lang="{lang_code}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VYVA Brain Coach – {t['title']}</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}

    body {{
      font-family: 'Outfit', sans-serif;
      margin: 0;
      padding: 40px 16px;
      background: #f7f5fb;
      color: #1a1025;
      line-height: 1.6;
    }}

    .page {{
      max-width: 900px;
      margin: auto;
      background: #fff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 8px 40px rgba(100,41,151,.10);
      border: 1px solid rgba(100,41,151,.12);
    }}

    .header {{
      padding: 32px;
      background: linear-gradient(135deg, #4a1a73 0%, #642997 45%, #8a54c5 100%);
      color: #fff;
    }}

    .header-content {{
      display: flex;
      align-items: flex-start;
      gap: 20px;
    }}
    .logo-wrap {{
      flex-shrink: 0;
      width: 80px;
      height: 80px;
      background: rgba(255,255,255,.1);
      border-radius: 12px;
      padding: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .logo-wrap img {{ width: 100%; display: block; object-fit: contain; }}

    .header-text .eyebrow {{
      font-family: 'DM Mono', monospace;
      font-size: 11px;
      letter-spacing: .15em;
      color: rgba(255,255,255,.6);
      margin: 0 0 6px;
    }}
    .header-text h1 {{ margin: 0; font-size: 26px; font-weight: 600; line-height: 1.25; }}
    .header-text .sub {{ margin: 6px 0 0; font-size: 14px; color: rgba(255,255,255,.65); }}

    .body {{ padding: 0 32px 32px; }}

    .section-title {{
      margin: 32px 0 16px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: #642997;
      border-bottom: 1px solid rgba(100,41,151,.2);
      padding-bottom: 8px;
    }}

    .info-table {{ width: 100%; border-collapse: collapse; border-radius: 8px; overflow: hidden; border: 1px solid rgba(100,41,151,.12); }}
    .info-table tr {{ border-bottom: 1px solid rgba(100,41,151,.12); }}
    .info-table tr:last-child {{ border-bottom: none; }}
    .info-table .lbl {{ width: 176px; padding: 12px 16px; font-size: 13px; font-weight: 600; color: #642997; background: #f3eaff; vertical-align: top; }}
    .info-table .val {{ padding: 12px 16px; font-size: 13px; color: #1a1025; }}

    .score-wrap {{ overflow-x: auto; border-radius: 8px; border: 1px solid rgba(100,41,151,.12); }}
    .score-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .score-table thead tr {{ background: #f3eaff; }}
    .score-table th {{ padding: 12px 16px; font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #642997; border-bottom: 1px solid rgba(100,41,151,.12); text-align: left; }}
    .score-table th:last-child {{ text-align: center; width: 110px; }}
    .score-table td {{ padding: 12px 16px; border-bottom: 1px solid rgba(100,41,151,.08); vertical-align: middle; }}
    .score-table tbody tr:nth-child(even) {{ background: #faf7ff; }}
    .score-table tbody tr:nth-child(odd) {{ background: #fff; }}
    .score-table td.domain {{ font-weight: 600; color: #642997; width: 150px; }}
    .score-table td.score-cell {{ text-align: center; }}

    .badge {{ display: inline-block; font-family: 'DM Mono', monospace; font-size: 12px; font-weight: 500; padding: 2px 10px; border-radius: 99px; min-width: 58px; text-align: center; }}
    .badge-high {{ background: #ecfdf5; color: #047857; box-shadow: 0 0 0 1px #a7f3d0; }}
    .badge-mid  {{ background: #fffbeb; color: #b45309; box-shadow: 0 0 0 1px #fde68a; }}
    .badge-low  {{ background: #fff1f2; color: #be123c; box-shadow: 0 0 0 1px #fecdd3; }}

    .totals-bar {{ margin-top: 12px; display: flex; align-items: center; gap: 24px; flex-wrap: wrap; background: #f3eaff; border: 1px solid rgba(100,41,151,.15); border-radius: 8px; padding: 16px 20px; }}
    .totals-bar .tot-label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: #7b6490; margin-right: 6px; }}
    .totals-bar .tot-num {{ font-family: 'DM Mono', monospace; font-size: 26px; font-weight: 700; color: #642997; }}
    .totals-bar .tot-denom {{ font-family: 'DM Mono', monospace; font-size: 13px; color: #7b6490; margin-left: 4px; }}
    .totals-bar .divider {{ width: 1px; height: 28px; background: rgba(100,41,151,.2); }}
    .totals-bar .tier-val {{ font-size: 13px; font-weight: 600; color: #642997; }}

    .notes {{ background: #faf7ff; border-left: 4px solid #642997; border-radius: 8px; padding: 20px 24px; font-size: 13px; line-height: 1.7; }}
    .notes .notes-heading {{ font-weight: 600; color: #642997; margin: 0 0 8px; }}
    .notes .notes-body {{ font-style: italic; color: #3d2655; margin: 0; }}

    .footer {{ padding: 16px 32px; text-align: center; font-family: 'DM Mono', monospace; font-size: 11px; color: #7b6490; background: #f7f5fb; border-top: 1px solid rgba(100,41,151,.10); }}

    @media (max-width: 640px) {{
      body {{ padding: 20px 12px; }}
      .header-content {{ flex-direction: column; align-items: center; text-align: center; }}
      .header-text h1 {{ font-size: 20px; }}
      .body {{ padding: 0 20px 24px; }}
      .totals-bar .divider {{ display: none; }}
      .info-table .lbl {{ width: 130px; }}
    }}
  </style>
</head>
<body>
<div class="page">

  <div class="header">
    <div class="header-content">
      <div class="logo-wrap">
        <img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png" alt="VYVA Logo">
      </div>
      <div class="header-text">
        <p class="eyebrow">VYVA BRAIN COACH</p>
        <h1>{t['title']}</h1>
        <p class="sub">{t['sub']}</p>
      </div>
    </div>
  </div>

  <div class="body">
    <div class="section-title">{t['details']}</div>
    <table class="info-table">
      <tr><td class="lbl">{t['l_name']}</td><td class="val">{name}</td></tr>
      <tr><td class="lbl">{t['l_tier']}</td><td class="val">{t['v_tier']}</td></tr>
      <tr><td class="lbl">{t['l_date']}</td><td class="val">{current_date}</td></tr>
      <tr><td class="lbl">{t['l_sid']}</td><td class="val">#{session_id}</td></tr>
      <tr><td class="lbl">{t['l_done']}</td><td class="val">{t['v_done']}</td></tr>
    </table>

    <div class="section-title">{t['scores']}</div>
    <div class="score-wrap">
      <table class="score-table">
        <thead>
          <tr>
            <th>{t['c_domain']}</th>
            <th>{t['c_question']}</th>
            <th>{t['c_score']}</th>
          </tr>
        </thead>
        <tbody>
          {table_rows_html}
        </tbody>
      </table>
    </div>

    <div class="totals-bar">
      <div>
        <span class="tot-label">{t['l_total']}</span>
        <span class="tot-num">{user_score}</span>
        <span class="tot-denom">/ {total_max_score}</span>
      </div>
      <div class="divider"></div>
      <div>
        <span class="tot-label">{t['l_perf']}</span>
        <span class="tier-val">{performance_tier}</span>
      </div>
    </div>

    <div class="section-title">{t['notes']}</div>
    <div class="notes">
      <p class="notes-heading">{t['n_heading']}</p>
      <p class="notes-body">{suggestions}</p>
    </div>
  </div>

  <div class="footer">{t['footer']}</div>
</div>
</body>
</html>"""

        subject = 'VYVA Brain Coach – Daily Cognitive Session Report'
        if lang_code == 'es':
            subject = 'VYVA Brain Coach – Informe Diario de Sesión Cognitiva'
        elif lang_code == 'de':
            subject = 'VYVA Brain Coach – Täglicher Kognitiver Sitzungsbericht'
        result = await self.send_email_via_mailgun(
            to=[recipient_email],
            subject=subject,
            html=html
        )

        logger.info(
            f"Medical report sent successfully to {recipient_email} with language {language}")
        return True

    async def send_medication_reminder(
        self,
        user,
        language='en'
    ):
        try:
            first_name = user['first_name']

            medication_content = ''
            medications = user['medications']
            for medication in medications:
                name = medication['medication_name']
                dosage = medication['medication_dosage']
                medication_content += f"""
                    <li class="medication-item">
                      <span class="med-name">{name}</span>
                      <span class="med-dosage">{dosage}</span>
                    </li>"""

            body_en = f"""<body>
                  <div class="container">
                    <div class="header">
                      <img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png" alt="VYVA Logo" class="logo">
                      <h1>Medication Reminder</h1>
                      <p>Your health is our priority</p>
                    </div>

                    <div class="content">
                      <h1 class="greeting">Hi <span id="patient-name"> {first_name}</span>,</h1>

                      <p class="message">This is VYVA. Remember to take the following medications:</p>

                      <ul class="medication-list" id="medication-list">
                        {medication_content}
                      </ul>

                      <p class="message">Please take your medications as prescribed by your healthcare provider. Set up additional reminders in the VYVA app.</p>
                    </div>

                    <div class="footer">
                      <p>This is an automated reminder from VYVA Medication Reminder.</p>
                      <p>© 2025 VYVA Health. All rights reserved.</p>
                    </div>
                  </div>


                </body>"""

            body_es = f"""<body>
                  <div class="container">
                    <div class="header">
                      <img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png" alt="Logo VYVA" class="logo">
                      <h1>Recordatorio de Medicación</h1>
                      <p>Tu salud es nuestra prioridad</p>
                    </div>

                    <div class="content">
                      <h1 class="greeting">Hola <span id="patient-name"> {first_name}</span>,</h1>

                      <p class="message">Soy VYVA. Recuerda tomar los siguientes medicamentos:</p>

                      <ul class="medication-list" id="medication-list">
                        {medication_content}
                      </ul>

                      <p class="message">Por favor, toma tus medicamentos según lo indicado por tu profesional de salud. Configura recordatorios adicionales en la aplicación VYVA.</p>
                    </div>

                    <div class="footer">
                      <p>Este es un recordatorio automático de VYVA Recordatorio de Medicación.</p>
                      <p>© 2025 VYVA Health. Todos los derechos reservados.</p>
                    </div>
                  </div>
                </body>
                """

            body = body_en
            if language == 'es':
                body = body_es

            html = f"""<!DOCTYPE html>
                <html lang="en">
                <head>
                  <meta charset="UTF-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1.0">
                  <title>VYVA Medication Reminder</title>
                  <style>
                    * {{
                      margin: 0;
                      padding: 0;
                      box-sizing: border-box;
                      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    }}

                body {{
                      background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
                      color: #333;
                      line-height: 1.6;
                      padding: 20px;
                      min-height: 100vh;
                      display: flex;
                      justify-content: center;
                      align-items: center;
                    }}

                    .container {{
                      max-width: 800px;
                      width: 100%;
                      background: white;
                      border-radius: 15px;
                      overflow: hidden;
                      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                    }}

                    .header {{
                      background: linear-gradient(135deg, #642997 0%, #8a54c5 100%);
                      padding: 25px;
                      text-align: center;
                      color: white;
                    }}

                    .logo {{
                      max-width: 150px;
                      height: auto;
                      margin-bottom: 15px;
                    }}

                    .header h1 {{
                      font-weight: 500;
                      font-size: 28px;
                      margin-bottom: 5px;
                    }}

                    .header p {{
                      opacity: 0.9;
                    }}

                    .content {{
                      padding: 30px;
                    }}

                    .greeting {{
                      font-size: 24px;
                      color: #642997;
                      margin-bottom: 20px;
                      font-weight: 600;
                    }}

                    .message {{
                      font-size: 17px;
                      margin-bottom: 25px;
                      color: #555;
                      line-height: 1.6;
                    }}

                    .reminder-time {{
                      background: #e8f5e9;
                      padding: 15px;
                      border-radius: 10px;
                      margin: 25px 0;
                      text-align: center;
                      font-weight: 500;
                      color: #2e7d32;
                      border: 2px dashed #4caf50;
                      font-size: 18px;
                    }}

                    .medication-list {{
                      list-style-type: none;
                      margin: 25px 0;
                    }}

                    .medication-item {{
                      background: #f9f5ff;
                      margin-bottom: 15px;
                      padding: 20px;
                      border-radius: 10px;
                      border-left: 5px solid #642997;
                      display: flex;
                      justify-content: space-between;
                      align-items: center;
                      transition: transform 0.3s ease, box-shadow 0.3s ease;
                    }}

                    .medication-item:hover {{
                      transform: translateY(-3px);
                      box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
                    }}

                    .med-name {{
                      font-weight: 600;
                      color: #642997;
                      font-size: 18px;
                    }}

                    .med-dosage {{
                      color: #6c757d;
                      font-size: 16px;
                      background: #fff;
                      padding: 5px 12px;
                      border-radius: 20px;
                      border: 1px solid #e0d4f7;
                    }}

                    .footer {{
                      background: #f9f9f9;
                      padding: 25px;
                      text-align: center;
                      font-size: 15px;
                      color: #777;
                      border-top: 1px solid #eee;
                    }}

                    .actions {{
                      display: flex;
                      justify-content: center;
                      gap: 15px;
                      margin-top: 20px;
                    }}

                    .btn {{
                      padding: 12px 25px;
                      border-radius: 30px;
                      border: none;
                      font-weight: 600;
                      cursor: pointer;
                      transition: all 0.3s ease;
                      font-size: 16px;
                    }}

                    .btn-primary {{
                      background: #642997;
                      color: white;
                    }}

                    .btn-primary:hover {{
                      background: #5a238a;
                      transform: translateY(-2px);
                    }}

                    .btn-secondary {{
                      background: #f0e6ff;
                      color: #642997;
                    }}

                    .btn-secondary:hover {{
                      background: #e4d5ff;
                      transform: translateY(-2px);
                    }}

                    @media (max-width: 600px) {{
                      .content {{
                        padding: 20px;
                      }}

                      .greeting {{
                        font-size: 22px;
                      }}

                      .medication-item {{
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 10px;
                      }}

                      .med-dosage {{
                        align-self: flex-start;
                      }}

                      .actions {{
                        flex-direction: column;
                      }}
                    }}
                  </style>
                </head>
                {body}
                </html>"""

            subject = "VYVA Brain Coach – Daily Cognitive Session Report"
            if language == 'es':
                subject = "VYVA Brain Coach – Informe Diario de Sesión Cognitiva"

            result = await self.send_email_via_mailgun(
                to=[user['email']],
                subject=subject,
                html=html
            )

            logger.info(f"Medical report sent successfully to {user['email']}")
            return True
        except Exception as e:
            logger.error(
                f'Error while sending reminder email for user {user['user_id']}: {e}')
            return False
        
    
    # async def send_welcome_email(
    #     self,
    #     first_name: str,
    #     email: str,
    #     language='en'
    # ):
    #     try:
            
    #         body_en = f"""<body>
    #               <div class="container">
    #                 <div class="header">
    #                   <img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png" alt="VYVA Logo" class="logo">
    #                   <h1>Welcome to VYVA!</h1>
    #                   <p>Your journey to better life starts here</p>
    #                 </div>

    #                 <div class="content">
    #                   <h1 class="greeting">Hi <span id="patient-name">{first_name}</span>,</h1>

    #                   <p class="message">Welcome to VYVA! We're thrilled to have you join our community dedicated to improving health and wellbeing.</p>


    #                   <div class="cta-section">
    #                     <p class="message">Get started by exploring the app and setting up your profile:</p>
    #                     <a href="{VYVA_ZAMORA_LINK}" class="btn btn-primary">Open VYVA App</a>
    #                   </div>

    #                   <p class="message">If you have any questions or need assistance, don't hesitate to reach out to our support team.</p>
    #                 </div>

    #                 <div class="footer">
    #                   <p>Welcome to the VYVA family!</p>
    #                   <p>© 2025 VYVA Health. All rights reserved.</p>
    #                 </div>
    #               </div>
    #             </body>"""

    #         body_es = f"""<body>
    #               <div class="container">
    #                 <div class="header">
    #                   <img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png" alt="Logo VYVA" class="logo">
    #                   <h1>¡Bienvenido a VYVA!</h1>
    #                   <p>Tu camino hacia una mejor salud comienza aquí</p>
    #                 </div>

    #                 <div class="content">
    #                   <h1 class="greeting">Hola <span id="patient-name">{first_name}</span>,</h1>

    #                   <p class="message">¡Bienvenido a VYVA! Estamos encantados de que te unas a nuestra comunidad dedicada a mejorar la salud y el bienestar.</p>


    #                   <div class="cta-section">
    #                     <p class="message">Comienza explorando la aplicación y configurando tu perfil:</p>
    #                     <a href="{VYVA_ZAMORA_LINK}" class="btn btn-primary">Abrir App VYVA</a>
    #                   </div>

    #                   <p class="message">Si tienes alguna pregunta o necesitas ayuda, no dudes en contactar a nuestro equipo de soporte.</p>
    #                 </div>

    #                 <div class="footer">
    #                   <p>¡Bienvenido a la familia VYVA!</p>
    #                   <p>© 2025 VYVA Health. Todos los derechos reservados.</p>
    #                 </div>
    #               </div>
    #             </body>"""

    #         body = body_en
    #         if language == 'es':
    #             body = body_es

    #         html = f"""<!DOCTYPE html>
    #             <html lang="en">
    #             <head>
    #               <meta charset="UTF-8">
    #               <meta name="viewport" content="width=device-width, initial-scale=1.0">
    #               <title>Welcome to VYVA</title>
    #               <style>
    #                 * {{
    #                   margin: 0;
    #                   padding: 0;
    #                   box-sizing: border-box;
    #                   font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    #                 }}

    #                 body {{
    #                   background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
    #                   color: #333;
    #                   line-height: 1.6;
    #                   padding: 20px;
    #                   min-height: 100vh;
    #                   display: flex;
    #                   justify-content: center;
    #                   align-items: center;
    #                 }}

    #                 .container {{
    #                   max-width: 800px;
    #                   width: 100%;
    #                   background: white;
    #                   border-radius: 15px;
    #                   overflow: hidden;
    #                   box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
    #                 }}

    #                 .header {{
    #                   background: linear-gradient(135deg, #642997 0%, #8a54c5 100%);
    #                   padding: 25px;
    #                   text-align: center;
    #                   color: white;
    #                 }}

    #                 .logo {{
    #                   max-width: 150px;
    #                   height: auto;
    #                   margin-bottom: 15px;
    #                 }}

    #                 .header h1 {{
    #                   font-weight: 500;
    #                   font-size: 28px;
    #                   margin-bottom: 5px;
    #                 }}

    #                 .header p {{
    #                   opacity: 0.9;
    #                 }}

    #                 .content {{
    #                   padding: 30px;
    #                 }}

    #                 .greeting {{
    #                   font-size: 24px;
    #                   color: #642997;
    #                   margin-bottom: 20px;
    #                   font-weight: 600;
    #                 }}

    #                 .message {{
    #                   font-size: 17px;
    #                   margin-bottom: 25px;
    #                   color: #555;
    #                   line-height: 1.6;
    #                 }}

    #                 .feature-list {{
    #                   list-style-type: none;
    #                   margin: 25px 0;
    #                 }}

    #                 .feature-list li {{
    #                   background: #f9f5ff;
    #                   margin-bottom: 12px;
    #                   padding: 15px 20px;
    #                   border-radius: 10px;
    #                   border-left: 5px solid #642997;
    #                   color: #555;
    #                   font-size: 16px;
    #                   transition: transform 0.3s ease, box-shadow 0.3s ease;
    #                 }}

    #                 .feature-list li:hover {{
    #                   transform: translateX(5px);
    #                   box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
    #                 }}

    #                 .feature-list li:before {{
    #                   content: "✓";
    #                   color: #642997;
    #                   font-weight: bold;
    #                   margin-right: 10px;
    #                 }}

    #                 .cta-section {{
    #                   text-align: center;
    #                   margin: 30px 0;
    #                   padding: 25px;
    #                   background: #f9f5ff;
    #                   border-radius: 10px;
    #                   border: 2px dashed #8a54c5;
    #                 }}

    #                 .btn {{
    #                   display: inline-block;
    #                   padding: 15px 35px;
    #                   border-radius: 30px;
    #                   border: none;
    #                   font-weight: 600;
    #                   cursor: pointer;
    #                   transition: all 0.3s ease;
    #                   font-size: 18px;
    #                   text-decoration: none;
    #                   margin-top: 15px;
    #                 }}

    #                 .btn-primary {{
    #                   background: #642997;
    #                   color: white;
    #                 }}

    #                 .btn-primary:hover {{
    #                   background: #5a238a;
    #                   transform: translateY(-2px);
    #                   box-shadow: 0 5px 15px rgba(100, 41, 151, 0.3);
    #                 }}

    #                 .footer {{
    #                   background: #f9f9f9;
    #                   padding: 25px;
    #                   text-align: center;
    #                   font-size: 15px;
    #                   color: #777;
    #                   border-top: 1px solid #eee;
    #                 }}

    #                 @media (max-width: 600px) {{
    #                   .content {{
    #                     padding: 20px;
    #                   }}

    #                   .greeting {{
    #                     font-size: 22px;
    #                   }}

    #                   .btn {{
    #                     display: block;
    #                     width: 100%;
    #                     text-align: center;
    #                   }}

    #                   .feature-list li {{
    #                     padding: 12px 15px;
    #                     font-size: 15px;
    #                   }}
    #                 }}
    #               </style>
    #             </head>
    #             {body}
    #             </html>"""

    #         subject = "Welcome to VYVA - Get Started with Your Health Journey"
    #         if language == 'es':
    #             subject = "Bienvenido a VYVA - Comienza tu Viaje de Salud"

    #         result = await self.send_email_via_mailgun(
    #             to=[email],
    #             subject=subject,
    #             html=html
    #         )

    #         logger.info(f"Welcome email sent successfully to {email}")
    #         return True
    #     except Exception as e:
    #         logger.error(f'Error while sending welcome email for {first_name, email}: {e}')
    #         return False


email_service = EmailService()
