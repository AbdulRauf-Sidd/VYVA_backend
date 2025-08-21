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
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_tls = settings.SMTP_TLS
        self.smtp_ssl = settings.SMTP_SSL
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_email: Optional[str] = None
    ) -> bool:
        """Send an email."""
        if not all([self.smtp_host, self.smtp_user, self.smtp_password]):
            logger.warning("SMTP configuration incomplete, skipping email send")
            return False
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = from_email or self.smtp_user
            message["To"] = to_email
            
            # Add text and HTML parts
            text_part = MIMEText(body, "plain")
            message.attach(text_part)
            
            if html_body:
                html_part = MIMEText(html_body, "html")
                message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                use_tls=self.smtp_tls,
                start_tls=self.smtp_tls and not self.smtp_ssl
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        """Send password reset email."""
        subject = "Password Reset Request"
        reset_url = f"https://your-app.com/reset-password?token={reset_token}"
        
        body = f"""
        Hello,
        
        You have requested a password reset for your account.
        Please click the following link to reset your password:
        
        {reset_url}
        
        This link will expire in 1 hour.
        
        If you did not request this reset, please ignore this email.
        
        Best regards,
        Vyva Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Hello,</p>
            <p>You have requested a password reset for your account.</p>
            <p>Please click the following link to reset your password:</p>
            <p><a href="{reset_url}">Reset Password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you did not request this reset, please ignore this email.</p>
            <p>Best regards,<br>Vyva Team</p>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, body, html_body)
    
    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """Send welcome email to new users."""
        subject = "Welcome to Vyva!"
        
        body = f"""
        Hello {user_name},
        
        Welcome to Vyva! We're excited to have you on board.
        
        Your account has been successfully created and you can now access all our features.
        
        If you have any questions, please don't hesitate to contact our support team.
        
        Best regards,
        Vyva Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Welcome to Vyva!</h2>
            <p>Hello {user_name},</p>
            <p>Welcome to Vyva! We're excited to have you on board.</p>
            <p>Your account has been successfully created and you can now access all our features.</p>
            <p>If you have any questions, please don't hesitate to contact our support team.</p>
            <p>Best regards,<br>Vyva Team</p>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, body, html_body) 