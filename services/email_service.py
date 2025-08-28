"""
Email service for sending emails.

Uses aiosmtplib for async email sending.
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class EmailService:
    """Email service for sending emails."""
    
    def __init__(self):
        self.url = settings.MAILGUN_API_URL
        self.key = settings.MAILGUN_API_KEY
    
    async def send_email_via_mailgun(
        api_key: str,
        domain: str,
        to: List[str],
        subject: str,
        text: Optional[str] = None,
        html: Optional[str] = None,
        from_email: str = "noreply@yourdomain.com",
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Union[str, int]]:
    """
    Send an email using Mailgun's API.
    """




    auth = ("api", self.key)
    data = {
        "from": from_email,
        "to": to,
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

    files = []
    if attachments:
        for attachment in attachments:
            if "file_data" in attachment:
                files.append(
                    ("attachment", (attachment["file_name"], attachment["file_data"]))
                )
            elif "file_url" in attachment:
                data.setdefault("attachment", []).append(attachment["file_url"])

    response = requests.post(
        url,
        auth=auth,
        data=data,
        files=files,
        headers=headers or {}
    )

    response.raise_for_status()
    return response.json()
    
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