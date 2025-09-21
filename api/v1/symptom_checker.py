from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import os
import httpx
import json
import re
import random
import string
import unicodedata
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from models.symptom_checker import SymptomCheckerResponse
from services import whatsapp_service
from services.email_service import EmailService
from services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter()


class SymptomCheckRequest(BaseModel):
    symptoms: str
    conversation_id: str  # Required - provided by frontend
    full_name: Optional[str] = None
    language: Optional[str] = None
    model_type: Optional[str] = "pro"
    followup_count: Optional[int] = 2
    # New optional fields for enhanced symptom analysis
    heart_rate: Optional[str] = None
    severity_scale: Optional[str] = None
    duration: Optional[str] = None
    respiratory_rate: Optional[str] = None
    additional_notes: Optional[str] = None
    system_prompt: Optional[str] = (
        "Please provide all responses in simple, consumer-friendly language. Avoid medical jargon when possible, "
        "and when medical terms must be used, define them clearly. Keep answers concise, prioritize practical advice. "
        "Limit responses to 3-4 short paragraphs maximum."
    )


class SendReportRequest(BaseModel):
    action: str  # "email" or "whatsapp"
    conversation_id: str  # Required - to identify the specific report
    recipient_email: Optional[str] = None
    phone_number: Optional[str] = None
    include_articles: Optional[bool] = True
    custom_message: Optional[str] = None


def _generate_id(length: int = 32) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _formulate_symptom_query(payload: SymptomCheckRequest) -> str:
    """
    Formulate a comprehensive search query for MediSearch API using all available parameters.
    """
    query_parts = []

    # Start with main symptoms
    query_parts.append(f"Symptoms: {payload.symptoms}")

    # Add severity scale if provided
    if payload.severity_scale:
        query_parts.append(f"with severity: {payload.severity_scale}")

    # Add duration if provided
    if payload.duration:
        query_parts.append(f"since: {payload.duration}")

    # Add vitals information if available
    vitals_parts = []
    if payload.heart_rate:
        vitals_parts.append(f"heart rate: {payload.heart_rate} bpm")
    if payload.respiratory_rate:
        vitals_parts.append(
            f"respiratory rate: {payload.respiratory_rate} breaths/min")

    if vitals_parts:
        query_parts.append(
            f"key current vitals information, {', '.join(vitals_parts)}")

    # Add additional notes if provided
    if payload.additional_notes:
        query_parts.append(f"Additional notes: {payload.additional_notes}")

    # Join all parts with periods and spaces
    formulated_query = ". ".join(query_parts) + "."

    return formulated_query


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        # Normalize and strip diacritics for latin scripts
        import unicodedata
        norm = (
            unicodedata.normalize("NFKD", value.lower())
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        norm = re.sub(r"\s+", " ", norm).strip()
        return norm
    except Exception:
        return value.lower().strip()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
        prev = curr
    return prev[lb]


KEYWORDS: Dict[str, List[str]] = {
    "en": [
        "emergency", "urgent", "immediate", "serious", "severe", "critical",
        "seek medical attention", "seek medical care", "call doctor", "call a doctor",
        "hospital", "911", "can't breathe", "cannot breathe", "difficulty breathing",
        "chest pain", "heavy bleeding", "bleeding heavily", "loss of consciousness",
        "unconscious", "not breathing", "no pulse", "seizure", "stroke",
    ],
    "es": [
        "emergencia", "urgente", "inmediato", "grave", "crítico",
        "buscar atención médica", "buscar asistencia médica", "llamar al médico",
        "hospital", "911", "no puede respirar", "dolor en el pecho", "sangrado abundante",
        "pérdida de conocimiento", "convulsión", "derrame cerebral",
    ],
    "fr": [
        "urgence", "urgent", "immédiat", "grave", "critique",
        "consulter un médecin", "chercher des soins médicaux", "appeler un médecin",
        "hôpital", "911", "ne peut pas respirer", "douleur thoracique", "saignement important",
        "perte de connaissance", "convulsion", "AVC",
    ],
    "de": [
        "notfall", "dringend", "sofort", "ernst", "kritisch",
        "ärztliche hilfe", "arzt rufen", "krankenhaus", "911", "112",
        "nicht atmen können", "brustschmerzen", "starke blutung", "bewusstlos", "anfälle",
    ],
    "pt": [
        "emergência", "urgente", "imediato", "grave", "crítico",
        "procure atendimento médico", "ligue para o médico", "hospital",
        "não consegue respirar", "dor no peito", "sangramento intenso", "inconsciente",
    ],
    "it": [
        "emergenza", "urgente", "immediato", "grave", "critico",
        "cerca assistenza medica", "chiama il medico", "ospedale",
        "non riesce a respirare", "dolore al petto", "emorragia", "incosciente",
    ],
    "ar": [
        "طوارئ", "عاجل", "حالة طارئة", "خطير",
        "اطلب المساعدة الطبية", "استدعاء الطبيب", "مستشفى",
        "لا يستطيع التنفس", "ألم صدر", "نزيف حاد", "فقدان الوعي", "نوبة",
    ],
    "ur": [
        "ہنگامی", "ہنگامی صورتحال", "فوری", "شدید", "طبی امداد",
        "ڈاکٹر کو بلائیں", "ہسپتال", "سانس نہیں", "چھاتی میں درد", "شدید خون بہنا", "بیہوش",
    ],
    "hi": [
        "आपातकाल", "आपात स्थिति", "तुरंत", "गंभीर", "खतरनाक",
        "चिकित्सकीय सहायता", "डॉक्टर को बुलाओ", "अस्पताल",
        "साँस नहीं", "सीने में दर्द", "भारी रक्तस्राव", "बेहोश", "दौरे",
    ],
    "bn": [
        "জরুরি", "তাত্ক্ষণিক", "গুরুতর", "তীব্র", "চিকিৎসা সহায়তা",
        "ডাক্তারকে ফোন করুন", "হাসপাতাল", "শ্বাস নিতে পারছে না", "বুকে ব্যথা", "রক্তপাত",
    ],
    "ru": [
        "чрезвычайная ситуация", "срочно", "немедленно", "серьезный", "критический",
        "обратитесь за медицинской помощью", "вызвать врача", "больница",
        "не может дышать", "боль в груди", "сильное кровотечение", "без сознания", "судорог",
    ],
    "tr": [
        "acil", "acil durum", "hemen", "ciddi", "kritik",
        "tıbbi yardım", "doktoru ara", "hastane",
        "nefes alamıyor", "göğüs ağrısı", "şiddetli kanama", "bilinç kaybı",
    ],
    "id": [
        "darurat", "mendesak", "segera", "serius", "kritis",
        "cari perawatan medis", "hubungi dokter", "rumah sakit",
        "sulit bernapas", "nyeri dada", "pendarahan hebat", "tidak sadarkan diri",
    ],
}


def _is_emergency(text: str) -> bool:
    text_norm = _normalize_text(text)
    if not text_norm:
        return False

    flat = []
    for phrases in KEYWORDS.values():
        for phrase in phrases:
            flat.append(_normalize_text(phrase) or phrase.lower())

    # quick substring
    for k in flat:
        if k and k in text_norm:
            return True

    # token-based fuzzy match
    tokens = [t for t in re.split(r'[\s,.;:()\[\]<>/\\]+', text_norm) if t]
    for token in tokens:
        for k in flat:
            if token == k:
                return True
            max_dist = 1 if len(k) <= 4 else 2
            if _levenshtein(token, k) <= max_dist:
                return True

    # emergency numbers
    if re.search(r"\b(911|112|999|000)\b", text_norm):
        return True

    return False


async def _call_medisearch_api(symptoms: str, conversation_id: str, language: str = "en", model_type: str = "pro",
                               system_prompt: str = None, followup_count: int = 2) -> Dict[str, Any]:
    """
    Call the MediSearch API and process the SSE response.
    Returns processed medical analysis with articles and emergency detection.
    """
    # Use the provided conversation_id

    # Prepare request payload
    request_payload = {
        "conversation": [symptoms],
        "key": "3d667019-0187-4793-b3a5-e6a14f078d40",  # API key
        "id": conversation_id,
        "settings": {
            "model_type": model_type,
            "system_prompt": system_prompt or (
                "Please provide all responses in simple, consumer-friendly language. "
                "Avoid medical jargon when possible, and when medical terms must be used, "
                "define them clearly. Keep answers concise, prioritize practical advice. "
                "Limit responses to 3-4 short paragraphs maximum."
            ),
            "followup_count": followup_count
        }
    }

    # Make API call
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.backend.medisearch.io/sse/medichat",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "Connection": "keep-alive",
                },
                json=request_payload
            )
            response.raise_for_status()

            # Process SSE stream
            raw_sse = response.text
            return _process_sse_stream(raw_sse)

    except httpx.TimeoutException:
        logger.error("MediSearch API timeout")
        raise HTTPException(
            status_code=504, detail="Medical analysis service timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"MediSearch API error: {e.response.status_code}")
        raise HTTPException(
            status_code=502, detail="Medical analysis service error")
    except Exception as e:
        logger.error(f"Unexpected error calling MediSearch API: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _process_sse_stream(raw_sse: str) -> Dict[str, Any]:
    """
    Process Server-Sent Events stream from MediSearch API.
    Extracts medical response, articles, and handles errors.
    """
    # Split into SSE messages
    chunks = re.split(r'\r?\n\r?\n', raw_sse)

    email = ""
    articles = []

    # Process each chunk
    for chunk in chunks:
        if not chunk.startswith("data:"):
            continue

        data_line = chunk.replace("data:", "").strip()
        if data_line == "[DONE]":
            break

        try:
            obj = json.loads(data_line)
        except json.JSONDecodeError:
            continue

        # Handle different event types
        if obj.get("event") == "articles" and isinstance(obj.get("data"), list):
            articles = obj["data"]
        elif obj.get("event") == "error":
            return {"error": obj.get("data", "Unknown error"), "email": "", "articles": []}
        elif obj.get("event") == "llm_response" and isinstance(obj.get("data"), str):
            email = obj["data"]

    # Replace reference markers with HTML anchors
    if articles:
        email = _replace_references_with_links(email, articles)

    return {
        "email": email,
        "articles": articles,
        "error": None
    }


def _replace_references_with_links(email: str, articles: List[Dict]) -> str:
    """
    Replace reference markers like [1, 2] with HTML anchor links.
    """
    def replace_match(match):
        nums_str = match.group(1)
        nums = [int(n.strip()) for n in nums_str.split(',')]

        links = []
        for num in nums:
            idx = num - 1
            if 0 <= idx < len(articles) and articles[idx].get('url'):
                links.append(
                    f'<a href="{articles[idx]["url"]}" target="_blank">[{num}]</a>')
            else:
                links.append(f'[{num}]')

        return ', '.join(links)

    return re.sub(r'\[(\d+(?:,\s*\d+)*)\]', replace_match, email)


def _clean_html_text(text: str) -> str:
    """
    Remove HTML anchor tags and links from text, including their inner text.
    
    Args:
        text: Text that may contain HTML anchor tags and links
        
    Returns:
        str: Clean text with HTML tags and their content completely removed
    """
    if not text:
        return ""
    
    # Remove HTML anchor tags completely including their inner text
    # Pattern matches <a href="...">text</a> and replaces with empty string
    text = re.sub(r'<a[^>]*href="[^"]*"[^>]*>.*?</a>', '', text)
    
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up extra whitespace and punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove trailing punctuation that might be left after removing links
    text = re.sub(r'[.,;:]\s*$', '', text)
    
    return text


def _create_breakdown(email: str, full_name: str = None) -> Dict[str, str]:
    """
    Break down the medical response into structured format.
    """
    lines = [line.strip() for line in email.split('\n') if line.strip()]

    breakdown = {
        "1": full_name or " ",
        "2": _clean_html_text(lines[0]) if lines else "",
        "3": _clean_html_text(lines[1].replace("1.", "").strip()) if len(lines) > 1 else "",
        "4": _clean_html_text(lines[2].replace("2.", "").strip()) if len(lines) > 2 else "",
        "5": _clean_html_text(lines[3].replace("3.", "").strip()) if len(lines) > 3 else ""
    }

    return breakdown


def _create_clean_summary(email: str) -> str:
    """
    Create a clean summary without HTML tags, references, or numbering.
    """
    if not email:
        return ""

    # Remove HTML anchor tags but keep the text
    clean_text = re.sub(r'<a[^>]*>\[(\d+)\]</a>', r'[\1]', email)

    # Remove any remaining HTML tags
    clean_text = re.sub(r'<[^>]+>', '', clean_text)

    # Remove reference markers like [1], [2, 3], etc.
    clean_text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', clean_text)

    # Remove numbering patterns like "1.", "2.", "3."
    clean_text = re.sub(r'^\d+\.\s*', '', clean_text, flags=re.MULTILINE)

    # Clean up extra whitespace and newlines
    clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
    clean_text = re.sub(r'[ \t]+', ' ', clean_text)
    clean_text = clean_text.strip()

    return clean_text


@router.post("/analyze-symptoms", status_code=status.HTTP_200_OK)
async def analyze_symptoms(payload: SymptomCheckRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Analyze symptoms using MediSearch API with emergency detection.
    Saves all response data to database and returns only the summary.
    """
    logger.info("=== SYMPTOM CHECKER ENDPOINT CALLED ===")
    logger.info(f"Received payload: {payload.model_dump()}")

    # Use the conversation_id provided by the frontend
    conversation_id = payload.conversation_id

    try:
        # Formulate comprehensive search query
        formulated_symptoms = _formulate_symptom_query(payload)
        logger.info(f"Formulated query: {formulated_symptoms}")

        # Call MediSearch API with formulated query
        api_result = await _call_medisearch_api(
            symptoms=formulated_symptoms,
            conversation_id=conversation_id,
            language=payload.language or "Spanish",
            model_type=payload.model_type,
            system_prompt=payload.system_prompt,
            followup_count=payload.followup_count
        )

        # Check for API errors
        if api_result.get("error"):
            # Save error response to database
            error_response = SymptomCheckerResponse(
                conversation_id=conversation_id,
                symptoms=payload.symptoms,
                full_name=payload.full_name,
                language=payload.language,
                model_type=payload.model_type,
                followup_count=payload.followup_count,
                # Enhanced symptom data
                heart_rate=payload.heart_rate,
                severity_scale=payload.severity_scale,
                duration=payload.duration,
                respiratory_rate=payload.respiratory_rate,
                additional_notes=payload.additional_notes,
                # Response data
                email="",
                summary="",
                breakdown={},
                severity="unknown",
                is_emergency=False,
                status="error"
            )
            db.add(error_response)
            await db.commit()

            return {
                "error": api_result["error"],
                "summary": "Error occurred during medical analysis. Please try again."
            }

        email = api_result.get("email", "")
        articles = api_result.get("articles", [])

        # Detect emergency situations
        is_emergency = _is_emergency(email)

        # Create structured breakdown
        breakdown = _create_breakdown(email, payload.full_name)

        # Create clean summary without HTML tags, references, or numbering
        summary = _create_clean_summary(email)

        # Save complete response to database
        response_record = SymptomCheckerResponse(
            conversation_id=conversation_id,
            symptoms=payload.symptoms,
            full_name=payload.full_name,
            language=payload.language,
            model_type=payload.model_type,
            followup_count=payload.followup_count,
            # Enhanced symptom data
            heart_rate=payload.heart_rate,
            severity_scale=payload.severity_scale,
            duration=payload.duration,
            respiratory_rate=payload.respiratory_rate,
            additional_notes=payload.additional_notes,
            # Response data
            email=email,
            summary=summary,
            breakdown=breakdown,
            severity="severe" if is_emergency else "mild",
            is_emergency=is_emergency,
            status="success"
        )

        db.add(response_record)
        await db.commit()

        logger.info(
            f"Saved symptom analysis to database with conversation_id: {conversation_id}")

        # Return only the summary as requested
        return {
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in analyze_symptoms: {str(e)}")

        # Try to save error to database
        try:
            error_response = SymptomCheckerResponse(
                conversation_id=conversation_id,
                symptoms=payload.symptoms,
                full_name=payload.full_name,
                language=payload.language,
                model_type=payload.model_type,
                followup_count=payload.followup_count,
                # Enhanced symptom data
                heart_rate=payload.heart_rate,
                severity_scale=payload.severity_scale,
                duration=payload.duration,
                respiratory_rate=payload.respiratory_rate,
                additional_notes=payload.additional_notes,
                # Response data
                email="",
                summary="",
                breakdown={},
                severity="unknown",
                is_emergency=False,
                status="error"
            )
            db.add(error_response)
            await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to save error to database: {str(db_error)}")

        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/send-report", status_code=status.HTTP_200_OK)
async def send_report(payload: SendReportRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Send a medical report via email or WhatsApp using the latest saved analysis.
    The record is automatically deleted after successful sending.
    """
    logger.info("=== SEND REPORT ENDPOINT CALLED ===")
    logger.info(f"Received payload: {payload.model_dump()}")

    try:
        # Get the specific analysis record by conversation_id
        from sqlalchemy import select

        result = await db.execute(
            select(SymptomCheckerResponse)
            .where(SymptomCheckerResponse.conversation_id == payload.conversation_id)
        )
        response_record = result.scalar_one_or_none()

        if not response_record:
            raise HTTPException(
                status_code=404,
                detail=f"No analysis found for conversation_id: {payload.conversation_id}. Please run symptom analysis first."
            )

        # Validate action and required fields
        if payload.action not in ["email", "whatsapp"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Must be 'email' or 'whatsapp'."
            )

        if payload.action == "email" and not payload.recipient_email:
            raise HTTPException(
                status_code=400,
                detail="Email address is required when action is 'email'."
            )

        if payload.action == "whatsapp" and not payload.phone_number:
            raise HTTPException(
                status_code=400,
                detail="Phone number is required when action is 'whatsapp'."
            )

        # Prepare report content
        report_content = _prepare_report_content(response_record, payload)

        # Send report based on action
        send_result = None

        if payload.action == "email":
            send_result = await _send_email_report(
                recipient_email=payload.recipient_email,
                report_content=report_content,
                patient_name=response_record.full_name or " "
            )
        elif payload.action == "whatsapp":
            send_result = await _send_whatsapp_report(
                phone_number=payload.phone_number,
                report_content=report_content,
                patient_name=response_record.full_name or " "
            )

        # Delete the record after successful sending
        await db.delete(response_record)
        await db.commit()

        logger.info(
            f"Report sent successfully and record deleted for conversation_id: {response_record.conversation_id}")

        return {
            "message": "Report sent successfully",
            "conversation_id": response_record.conversation_id,
            "action": payload.action,
            "status": send_result,
            "success": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_report: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _prepare_report_content(response_record: SymptomCheckerResponse, payload: SendReportRequest) -> Dict[str, Any]:
    """
    Prepare the report content for sending.
    """
    content = {
        "patient_name": response_record.full_name or " ",
        "symptoms": response_record.symptoms,
        "summary": response_record.summary,
        "email": response_record.email,  # Full email content for analysis section
        "severity": response_record.severity,
        "is_emergency": response_record.is_emergency,
        "created_at": response_record.created_at.isoformat() if response_record.created_at else None,
        "conversation_id": response_record.conversation_id,
        # Using full_name as user_id for now
        "user_id": response_record.full_name or "Unknown",
        "custom_message": payload.custom_message,
        # Additional fields for email template
        "duration": response_record.duration or "Not specified",
        "pain_level": response_record.severity_scale or "Not specified",
        "additional_notes": response_record.additional_notes or "None"
    }

    # Include breakdown if available
    if response_record.breakdown:
        content["breakdown"] = response_record.breakdown

    # Include articles if requested and available
    if payload.include_articles and response_record.email:
        # Extract article links from email
        article_links = re.findall(
            r'<a href="([^"]*)"[^>]*>\[(\d+)\]</a>', response_record.email)
        if article_links:
            content["articles"] = [{"url": url, "reference": ref}
                                   for url, ref in article_links]

    # Include vitals if available
    content["vitals"] = {
        "heart_rate": {
            "value": float(response_record.heart_rate) if response_record.heart_rate else None,
            "unit": "bpm",
            "confidence": None  # TODO: Add confidence field if needed
        },
        "respiratory_rate": {
            "value": float(response_record.respiratory_rate) if response_record.respiratory_rate else None,
            "unit": "breaths/min",
            "confidence": None  # TODO: Add confidence field if needed
        }
    }

    return content


async def _send_email_report(recipient_email: str, report_content: Dict[str, Any], patient_name: str) -> str:
    """
    Send medical report via email using Mailgun service.
    """
    try:
        # Initialize email service
        email_service = EmailService()

        # Send the medical report
        success = await email_service.send_medical_report(
            recipient_email=recipient_email,
            report_content=report_content
        )

        logger.info(
            f"Email service returned: {success} (type: {type(success)})")

        if success:
            logger.info(
                f"Medical report sent successfully to {recipient_email}")
            return "email_sent"
        else:
            logger.error(f"Failed to send medical report to {recipient_email}")
            return "email_failed"

    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        return "email_failed"


async def _send_whatsapp_report(phone_number: str, report_content: Dict[str, Any], patient_name: str) -> str:
    """
    Send medical report via WhatsApp.
    """
    try:
        # TODO: Implement actual WhatsApp sending logic
        # This is a placeholder - you'll need to integrate with your WhatsApp service

        whatsapp_service = WhatsAppService()
        
        # Get the breakdown data and ensure it's properly formatted
        breakdown_data = report_content.get('breakdown', {})
        logger.info(f"ContentVariableData: {breakdown_data}")
        
        # Convert breakdown dict to the format expected by WhatsApp template
        # If breakdown is a dict with numbered keys, use it directly
        # If it's a string or other format, convert it appropriately
        # if isinstance(breakdown_data, dict):
        #     template_data = breakdown_data
        # else:
        #     # If breakdown is not a dict, create a simple template data structure
        #     template_data = {"breakdown": str(breakdown_data)}
        
        # success = await whatsapp_service.send_medical_report(phone_number, breakdown_data)
        success = await whatsapp_service.send_template_message(phone_number, breakdown_data);

        logger.info(
            f"Whatsapp service returned: {success} (type: {type(success)})")

        if success:
            logger.info(
                f"Medical report sent successfully to {phone_number}")
            return "whatsapp_sent"
        else:
            logger.error(f"Failed to send medical report to {phone_number}")
            return "whatsapp_failed"

    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}")
        return "whatsapp_failed"
