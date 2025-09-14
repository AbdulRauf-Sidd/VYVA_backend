"""
Email service for sending emails using Mailgun API.
"""

import requests
import httpx
from typing import List, Optional, Dict, Union
from core.config import settings
from core.logging import get_logger
from services.helpers import generate_random_string
from datetime import datetime


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
            subject = "Your VYVA Health Symptom Assessment"

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
                    .header {{ background-color: #2c5aa0; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .section {{ margin-bottom: 25px; }}
                    .section-title {{ color: #2c5aa0; font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 2px solid #2c5aa0; padding-bottom: 5px; }}
                    .symptom-item {{ background-color: #f8f9fa; padding: 10px; margin: 5px 0; border-left: 4px solid #2c5aa0; }}
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
                    <h1 style="color:#FFF; font-size:20px; text-align:right;">VYVA Symptom Checker</h1>
                    </div>
                </div>
                </div>
                <div class="content">
                    <h2>Dear User,</h2>
                    <p>Thank you for using VYVA Symptom Checker. Here is your detailed symptom assessment:</p>
                    
                    <div class="section">
                        <div class="section-title">📋 Symptoms Reported</div>
                        <div class="symptom-item"><strong>Symptoms:</strong> {symptoms}</div>
                        <div class="symptom-item"><strong>Duration:</strong> {duration}</div>
                        <div class="symptom-item"><strong>Pain Level:</strong> {pain_level}</div>
                        <div class="symptom-item"><strong>Additional Notes:</strong> {additional_notes}</div>
                    </div>
            """

            # Add vitals section if available
            if heart_rate.get('value') or respiratory_rate.get('value'):
                html_body += """
                    <div class="section">
                        <div class="section-title">🩺 Vital Signs</div>
                        <div class="vitals">
                """

                if heart_rate.get('value'):
                    html_body += f"""
                            <div class="vital-item">
                                <div style="font-weight: bold; color: #d32f2f;">❤️ Heart Rate</div>
                                <div style="font-size: 14px; color: #d32f2f;">Value: {heart_rate.get('value', '—')} {heart_rate.get('unit', 'bpm')}</div>
                            </div>
                    """

                if respiratory_rate.get('value'):
                    html_body += f"""
                            <div class="vital-item">
                                <div style="font-weight: bold; color: #1976d2;">🫁 Respiratory Rate</div>
                                <div style="font-size: 14px; color: #1976d2;">Value: {respiratory_rate.get('value', '—')} {respiratory_rate.get('unit', 'breaths/min')}</div>
                            </div>
                    """

                html_body += """
                        </div>
                    </div>
                """

            # Continue with the rest of the email
            html_body += f"""
                    <div class="section">
                        <div class="section-title">🩺 Medical Analysis</div>
                        <div class="analysis">{analysis_content}</div>
                    </div>
                    
                    <div class="section">
                        <div class="section-title">⚠️ Severity Assessment</div>
                        <div class="severity {'severe' if severity.lower() == 'severe' else 'mild'}">
                            <strong>Classification:</strong> <span style="text-transform: uppercase;">{severity}</span>
                        </div>
                    </div>
                    
                    <div class="disclaimer">
                        <strong>⚠️ Important Disclaimer:</strong><br>
                        This assessment is for informational purposes only. Please consult with a healthcare professional for proper medical advice.
                    </div>
                    
                    <div style="margin-top: 30px;">
                        <p><strong>Record ID:</strong> {record_id}</p>
                        <p><strong>Assessment Date:</strong> {created_at}</p>
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>Best regards,<br>VYVA Symptom Checker Team</strong></p>
                    <p style="font-size: 12px; color: #999;">This email was generated automatically by VYVA Symptom Checker System</p>
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
        performance_tier: Optional[str] = None
    ):
        tier = report_content[0].get(
            'tier', 'N/A') if report_content else 'N/A'
        session_id = generate_random_string(6)
        current_date = datetime.now().strftime("%A, %B %d, %Y")

        table_rows = ""
        user_score = 0
        total_max_score = 0
        for item in report_content:
            table_rows += f"<tr><td>{item.get('question_type', '')}</td><td>{item.get('question_text', '')}</td><td>{item.get('score', '')}</td></tr>"
            user_score += item.get('score', 0)
            total_max_score += item.get('max_score', 0)

        html = f"""
                        <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>VYVA Brain Coach – Daily Cognitive Session Report</title>
              <style>
                body {{
                  font-family: Arial, sans-serif;
                  margin: 20px;
                  background: #fff;
                  color: #000;
                  line-height: 1.5;
                }}
                .report-container {{
                  max-width: 800px;
                  margin: auto;
                  padding: 20px;
                  border: 1px solid #ddd;
                  border-radius: 8px;
                  box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                }}
                .row {{
                  display: flex;
                  flex-wrap: wrap;
                  margin-bottom: 10px;
                }}
                .label {{
                  flex: 1 0 200px;
                  font-weight: bold;
                }}
                .value {{
                  flex: 2 0 300px;
                }}
                .section-title {{
                  font-size: 18px;
                  margin-top: 20px;
                  border-bottom: 1px solid #ccc;
                  padding-bottom: 5px;
                }}
                .notes {{
                  background: #f9f9f9;
                  padding: 10px;
                  border-radius: 6px;
                  margin-top: 10px;
                  font-style: italic;
                }}
                table {{
                  width: 100%;
                  border-collapse: collapse;
                  margin-top: 15px;
                }}
                th, td {{
                  border: 1px solid #ccc;
                  padding: 8px;
                  text-align: center;
                }}
                th {{
                  background: #f0f0f0;
                }}
                .header_bg {{
                  background: #642997;
                  border-radius: 6px 6px 0 0;
                  margin: -20px -20px 20px -20px;
                }}
                @media (max-width: 600px) {{
                  .row {{
                    flex-direction: column;
                  }}
                  .label, .value {{
                    flex: 1 0 100%;
                  }}
                }}
                @media only screen and (max-width: 690px) {{
                  .new_dic {{
                    color: #FFF;
                    font-size: 8px !important;
                    text-align: right;
                    padding: 0px 14px 0px 0px !important;
                  }}
                  .second_div {{
                    margin: 2px 0px 0px !important;
                  }}
                }}
                .logo img {{
                  max-width: 100%;
                  height: auto;
                }}
                .logo_div {{
                  width: 20%; 
                  padding: 15px 0px 8px 19px;
                }}
                .main {{
                  width: 100%;
                  display: flex;
                  justify-content: space-between;
                  align-items: center;
                }}
                .second_div {{
                  width: 74%;
                  margin: 15px 0px;
                  padding-right: 15px;
                }}
                .new_dic {{
                  color: #FFF; 
                  font-size: 18px; 
                  text-align: right;
                  margin: 0;
                }}
              </style>
            </head>
            <body>
              <div class="report-container">
                <div class="header_bg">
                  <div class="main">
                    <div class="logo logo_div">
                      <img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png" alt="VYVA Logo">
                    </div>
                    <div class="second_div">
                      <h1 class="new_dic">VYVA Brain Coach – Daily Cognitive Session Report</h1>
                    </div>
                  </div>
                </div>

                <div class="row">
                  <div class="label">Name:</div>
                  <div class="value"> {name}</div>
                </div>
                <div class="row">
                  <div class="label">Cognitive Tier:</div>
                  <div class="value">Tier {tier} – Moderate Impairment</div>
                </div>
                <div class="row">
                  <div class="label">Date:</div>
                  <div class="value"> {current_date}</div>
                </div>
                <div class="row">
                  <div class="label">Session ID:</div>
                  <div class="value"># {session_id}</div>
                </div>

                <div class="section-title">Activity Domain Scores</div>
                <table>
                  <tr>
                    <th>Activity Domain</th>
                    <th>Question</th>
                    <th>Score</th>
                  </tr>
                  {table_rows}
                </table>

                <div class="row">
                  <div class="label">Total Score:</div>
                  <div class="value"> {user_score} / {total_max_score}</div>
                </div>
                <div class="row">
                  <div class="label">Performance Tier:</div>
                  <div class="value"> {performance_tier}</div>
                </div>
                <div class="row">
                  <div class="label">Session Completed:</div>
                  <div class="value">Yes</div>
                </div>

                <div class="section-title">Agent Notes & Suggestions</div>
                <div class="notes">
                  {suggestions}<br><br>
                </div>
              </div>
            </body>
            </html>"""
        result = await self.send_email_via_mailgun(
            to=[recipient_email],
            subject='VYVA Brain Coach – Daily Cognitive Session Report',
            html=html
        )

        logger.info(f"Medical report sent successfully to {recipient_email}")
        return True
    
    async def send_medication_reminder(
        self,
        user
    ):
        try:
            name = user['first_name']

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
                <body>
                  <div class="container">
                    <div class="header">
                      <img src="https://pub-5793da9d92e544e7a4e39b1d9957215d.r2.dev/assets/logo.png" alt="VYVA Logo" class="logo">
                      <h1>Medication Reminder</h1>
                      <p>Your health is our priority</p>
                    </div>

                    <div class="content">
                      <h1 class="greeting">Hi <span id="patient-name"> {name}</span>,</h1>

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


                </body>
                </html>"""

            result = await self.send_email_via_mailgun(
                to=[user['email']],
                subject='VYVA Brain Coach – Daily Cognitive Session Report',
                html=html
            )

            logger.info(f"Medical report sent successfully to {user['email']}")
            return True
        except Exception as e:
            logger.error(f'Error while sending reminder email for user {user['user_id']}: {e}')
            return False
        
email_service = EmailService()
