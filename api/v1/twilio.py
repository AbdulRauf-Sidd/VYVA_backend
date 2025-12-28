"""
Twilio Webhook Endpoints

Handles incoming messages from Twilio webhooks.
"""

from fastapi import APIRouter, Request
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/incoming-message")
async def receive_incoming_message(request: Request):
    """
    Webhook endpoint for Twilio incoming messages.
    Receives POST requests from Twilio when a message is received.
    
    Twilio sends form-encoded data (application/x-www-form-urlencoded),
    so we need to handle it as form data.
    """
    try:
        # Parse form data (Twilio sends form-encoded data)
        # Note: This reads the body, so we can't read it again separately
        form_data = await request.form()
        
        # Convert form data to dictionary for easier handling
        message_data = {}
        for key, value in form_data.items():
            message_data[key] = value
        
        # Print the received data to console
        print("=" * 80)
        print("TWILIO WEBHOOK - INCOMING MESSAGE RECEIVED")
        print("=" * 80)
        print(f"Form Data: {json.dumps(dict(message_data), indent=2, default=str)}")
        print("=" * 80)
        
        # Log the received data
        logger.info(
            "Twilio incoming message webhook received",
            message_data=dict(message_data)
        )
        
        # Log individual fields that are commonly present in Twilio webhooks
        if 'MessageSid' in message_data:
            logger.info(f"Message SID: {message_data['MessageSid']}")
        if 'From' in message_data:
            logger.info(f"From: {message_data['From']}")
        if 'To' in message_data:
            logger.info(f"To: {message_data['To']}")
        if 'Body' in message_data:
            logger.info(f"Message Body: {message_data['Body']}")
        if 'AccountSid' in message_data:
            logger.info(f"Account SID: {message_data['AccountSid']}")
        
        # Return TwiML response (Twilio expects a response)
        # For now, we'll return a simple acknowledgment
        # You can customize this later to send automated responses
        return {
            "status": "received",
            "message": "Webhook processed successfully"
        }
        
    except Exception as e:
        logger.exception(f"Error processing Twilio webhook: {e}")
        print(f"ERROR processing Twilio webhook: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

