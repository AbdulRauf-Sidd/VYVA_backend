"""
Email service for sending emails using Mailgun API.
"""

import requests
import httpx
from typing import List, Optional, Dict, Union
from core.config import settings
from core.logging import get_logger

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
                            ("attachment", (attachment["file_name"], attachment["file_data"]))
                        )
                    elif "file_url" in attachment:
                        data.setdefault("attachment", []).append(attachment["file_url"])
            
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
                
                logger.info(f"Email sent successfully to {to}. Message ID: {result.get('id', 'unknown')}")
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Mailgun API error: {e.response.status_code} - {e.response.text}")
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
            analysis_content = report_content.get('email', 'N/A')  # Use 'email' field from database
            severity = report_content.get('severity', 'N/A')
            user_id = report_content.get('user_id', 'N/A')
            record_id = report_content.get('conversation_id', 'N/A')  # Use 'conversation_id' field
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
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🏥 VYVA Symptom Checker</h1>
                    <p>Symptom Assessment Report</p>
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
                        <p><strong>User ID:</strong> {user_id}</p>
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
            
            logger.info(f"Medical report sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send medical report to {recipient_email}: {str(e)}")
            return False
    
    # async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
    #     """Send welcome email to new users."""
    #     subject = "Welcome to Vyva!"
        
    #     body = f"""
    #     Hello {user_name},
        
    #     Welcome to Vyva! We're excited to have you on board.
        
    #     Your account has been successfully created and you can now access all our features.
        
    #     If you have any questions, please don't hesitate to contact our support team.
        
    #     Best regards,
    #     Vyva Team
    #     """
        
    #     html_body = f"""
    #     <html>
    #     <body>
    #         <h2>Welcome to Vyva!</h2>
    #         <p>Hello {user_name},</p>
    #         <p>Welcome to Vyva! We're excited to have you on board.</p>
    #         <p>Your account has been successfully created and you can now access all our features.</p>
    #         <p>If you have any questions, please don't hesitate to contact our support team.</p>
    #         <p>Best regards,<br>Vyva Team</p>
    #     </body>
    #     </html>
    #     """
        
    #     return await self.send_email(to_email, subject, body, html_body) 