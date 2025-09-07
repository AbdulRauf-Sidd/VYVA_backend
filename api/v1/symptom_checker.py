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

logger = logging.getLogger(__name__)

router = APIRouter()


class SymptomCheckRequest(BaseModel):
    symptoms: str
    full_name: Optional[str] = None
    language: Optional[str] = None
    model_type: Optional[str] = "pro"
    followup_count: Optional[int] = 2
    system_prompt: Optional[str] = (
        "Please provide all responses in simple, consumer-friendly language. Avoid medical jargon when possible, "
        "and when medical terms must be used, define them clearly. Keep answers concise, prioritize practical advice. "
        "Limit responses to 3-4 short paragraphs maximum."
    )


class SendReportRequest(BaseModel):
    action: str  # "email" or "whatsapp"
    recipient_email: Optional[str] = None
    phone_number: Optional[str] = None
    include_articles: Optional[bool] = True
    custom_message: Optional[str] = None


def _generate_id(length: int = 32) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


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


async def _call_medisearch_api(symptoms: str, language: str = "en", model_type: str = "pro", 
                              system_prompt: str = None, followup_count: int = 2) -> Dict[str, Any]:
    """
    Call the MediSearch API and process the SSE response.
    Returns processed medical analysis with articles and emergency detection.
    """
    # Generate unique ID
    conversation_id = _generate_id()
    
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
        raise HTTPException(status_code=504, detail="Medical analysis service timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"MediSearch API error: {e.response.status_code}")
        raise HTTPException(status_code=502, detail="Medical analysis service error")
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
                links.append(f'<a href="{articles[idx]["url"]}" target="_blank">[{num}]</a>')
            else:
                links.append(f'[{num}]')
        
        return ', '.join(links)
    
    return re.sub(r'\[(\d+(?:,\s*\d+)*)\]', replace_match, email)


def _create_breakdown(email: str, full_name: str = None) -> Dict[str, str]:
    """
    Break down the medical response into structured format.
    """
    lines = [line.strip() for line in email.split('\n') if line.strip()]
    
    breakdown = {
        "1": full_name or "Patient",
        "2": lines[0] if lines else "",
        "3": lines[1].replace("1.", "").strip() if len(lines) > 1 else "",
        "4": lines[2].replace("2.", "").strip() if len(lines) > 2 else "",
        "5": lines[3].replace("3.", "").strip() if len(lines) > 3 else ""
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
    
    conversation_id = _generate_id()
    
    try:
        # Call MediSearch API
        api_result = await _call_medisearch_api(
            symptoms=payload.symptoms,
            language=payload.language or "en",
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
            email=email,
            summary=summary,
            breakdown=breakdown,
            severity="severe" if is_emergency else "mild",
            is_emergency=is_emergency,
            status="success"
        )
        
        db.add(response_record)
        await db.commit()
        
        logger.info(f"Saved symptom analysis to database with conversation_id: {conversation_id}")
        
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
        # Get the latest analysis record from database (most recent one)
        from sqlalchemy import select, desc
        
        result = await db.execute(
            select(SymptomCheckerResponse)
            .order_by(desc(SymptomCheckerResponse.created_at))
            .limit(1)
        )
        response_record = result.scalar_one_or_none()
        
        if not response_record:
            raise HTTPException(
                status_code=404, 
                detail="No analysis found. Please run symptom analysis first."
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
                patient_name=response_record.full_name or "Patient"
            )
        elif payload.action == "whatsapp":
            send_result = await _send_whatsapp_report(
                phone_number=payload.phone_number,
                report_content=report_content,
                patient_name=response_record.full_name or "Patient"
            )
        
        # Delete the record after successful sending
        await db.delete(response_record)
        await db.commit()
        
        logger.info(f"Report sent successfully and record deleted for conversation_id: {response_record.conversation_id}")
        
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
        "patient_name": response_record.full_name or "Patient",
        "symptoms": response_record.symptoms,
        "summary": response_record.summary,
        "email": response_record.email,  # Full email content for analysis section
        "severity": response_record.severity,
        "is_emergency": response_record.is_emergency,
        "created_at": response_record.created_at.isoformat() if response_record.created_at else None,
        "conversation_id": response_record.conversation_id,
        "user_id": response_record.full_name or "Unknown",  # Using full_name as user_id for now
        "custom_message": payload.custom_message,
        # Additional fields for email template
        "duration": "Not specified",  # TODO: Add duration field to model if needed
        "pain_level": "Not specified",  # TODO: Add pain_level field to model if needed
        "additional_notes": "None"  # TODO: Add additional_notes field to model if needed
    }
    
    # Include breakdown if available
    if response_record.breakdown:
        content["breakdown"] = response_record.breakdown
    
    # Include articles if requested and available
    if payload.include_articles and response_record.email:
        # Extract article links from email
        article_links = re.findall(r'<a href="([^"]*)"[^>]*>\[(\d+)\]</a>', response_record.email)
        if article_links:
            content["articles"] = [{"url": url, "reference": ref} for url, ref in article_links]
    
    # Include vitals if available (placeholder for future implementation)
    # TODO: Add vitals field to SymptomCheckerResponse model
    content["vitals"] = {
        "heart_rate": {
            "value": None,
            "unit": "bpm",
            "confidence": None
        },
        "respiratory_rate": {
            "value": None,
            "unit": "breaths/min",
            "confidence": None
        }
    }
    
    return content


async def _send_email_report(recipient_email: str, report_content: Dict[str, Any], patient_name: str) -> str:
    """
    Send medical report via email using HTML template.
    """
    try:
        # TODO: Implement actual email sending logic
        # This is a placeholder - you'll need to integrate with your email service
        
        # Create email content using HTML template
        emergency_text = "URGENT: " if report_content['is_emergency'] else ""
        email_subject = f"{emergency_text}Your VYVA Health Symptom Assessment"
        
        # Get vitals information if available
        vitals_html = ""
        if report_content.get('vitals'):
            vitals = report_content['vitals']
            vitals_html = """
        <div class="section">
            <div class="section-title">📊 Vital Signs</div>
            <div class="symptom-item">
                <div style="font-weight: bold; color: #d63384;">❤️ Heart Rate</div>
                <div style="font-size: 12px; color: #d63384; margin: 5px 0;">
                    Value: {heart_rate_value} {heart_rate_unit}
                </div>
                <div style="font-size: 12px; color: #d63384;">
                    Confidence: {heart_rate_confidence}%
                </div>
            </div>
            <div class="symptom-item">
                <div style="font-weight: bold; color: #2c5aa0;">🫁 Respiratory Rate</div>
                <div style="font-size: 12px; color: #2c5aa0; margin: 5px 0;">
                    Value: {respiratory_rate_value} {respiratory_rate_unit}
                </div>
                <div style="font-size: 12px; color: #2c5aa0;">
                    Confidence: {respiratory_rate_confidence}%
                </div>
            </div>
        </div>
        """.format(
                heart_rate_value=vitals.get('heart_rate', {}).get('value', '—'),
                heart_rate_unit=vitals.get('heart_rate', {}).get('unit', 'bpm'),
                heart_rate_confidence=f"{(vitals.get('heart_rate', {}).get('confidence', 0) * 100):.1f}" if vitals.get('heart_rate', {}).get('confidence') else "—",
                respiratory_rate_value=vitals.get('respiratory_rate', {}).get('value', '—'),
                respiratory_rate_unit=vitals.get('respiratory_rate', {}).get('unit', 'breaths/min'),
                respiratory_rate_confidence=f"{(vitals.get('respiratory_rate', {}).get('confidence', 0) * 100):.1f}" if vitals.get('respiratory_rate', {}).get('confidence') else "—"
            )
        
        # Get additional symptom details if available
        duration = report_content.get('duration', 'Not specified')
        pain_level = report_content.get('pain_level', 'Not specified')
        additional_notes = report_content.get('additional_notes', 'None')
        
        # Get user ID and record ID
        user_id = report_content.get('user_id', 'Unknown')
        record_id = report_content.get('conversation_id', 'Unknown')
        
        # Format the analysis content (remove HTML tags for email)
        analysis_content = report_content.get('email', report_content.get('summary', ''))
        
        # Create HTML email body
        email_body = f"""<!DOCTYPE html>
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
            <div class="symptom-item"><strong>Symptoms:</strong> {report_content['symptoms']}</div>
            <div class="symptom-item"><strong>Duration:</strong> {duration}</div>
            <div class="symptom-item"><strong>Pain Level:</strong> {pain_level}</div>
            <div class="symptom-item"><strong>Additional Notes:</strong> {additional_notes}</div>
        </div>
        
        {vitals_html}
        
        <div class="section">
            <div class="section-title">🩺 Medical Analysis</div>
            <div class="analysis">{analysis_content}</div>
        </div>
        <div class="section">
            <div class="section-title">⚠️ Severity Assessment</div>
            <div class="severity {'severe' if report_content['severity'] == 'severe' else 'mild'}">
                <strong>Classification:</strong> <span style="text-transform: uppercase;">{report_content['severity']}</span>
            </div>
        </div>
        <div class="disclaimer">
            <strong>⚠️ Important Disclaimer:</strong><br>
            This assessment is for informational purposes only. Please consult with a healthcare professional for proper medical advice.
        </div>
        
        <div style="margin-top: 30px;">
            <p><strong>User ID:</strong> {user_id}</p>
            <p><strong>Record ID:</strong> {record_id}</p>
            <p><strong>Assessment Date:</strong> {report_content.get('created_at', 'Unknown')}</p>
        </div>
    </div>
    <div class="footer">
        <p><strong>Best regards,<br>VYVA Symptom Checker Team</strong></p>
        <p style="font-size: 12px; color: #999;">This email was generated automatically by VYVA Symptom Checker System</p>
    </div>
</body>
</html>"""
        
        # TODO: Replace with actual email sending
        logger.info(f"Email would be sent to {recipient_email}")
        logger.info(f"Subject: {email_subject}")
        logger.info(f"HTML Body length: {len(email_body)} characters")
        
        return "email_sent"
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return "email_failed"


async def _send_whatsapp_report(phone_number: str, report_content: Dict[str, Any], patient_name: str) -> str:
    """
    Send medical report via WhatsApp.
    """
    try:
        # TODO: Implement actual WhatsApp sending logic
        # This is a placeholder - you'll need to integrate with your WhatsApp service
        
        # Create WhatsApp message
        emergency_text = "🚨 URGENT: " if report_content['is_emergency'] else ""
        whatsapp_message = f"""{emergency_text}Medical Report for {patient_name}

📋 SYMPTOMS:
{report_content['symptoms']}

📊 ANALYSIS:
{report_content['summary']}

⚠️ SEVERITY: {report_content['severity'].upper()}
🚨 EMERGENCY: {'YES - SEEK IMMEDIATE MEDICAL ATTENTION' if report_content['is_emergency'] else 'No'}

"""
        
        if report_content.get('breakdown'):
            whatsapp_message += "\n📝 DETAILED BREAKDOWN:\n"
            for key, value in report_content['breakdown'].items():
                if value:
                    whatsapp_message += f"• {value}\n"
        
        if report_content.get('articles'):
            whatsapp_message += "\n📚 REFERENCE ARTICLES:\n"
            for article in report_content['articles']:
                whatsapp_message += f"• {article['url']}\n"
        
        if report_content.get('custom_message'):
            whatsapp_message += f"\n💬 ADDITIONAL MESSAGE:\n{report_content['custom_message']}\n"
        
        whatsapp_message += f"\n📅 Generated: {report_content['created_at'] or 'Unknown'}"
        whatsapp_message += "\n\n⚠️ Please consult with a healthcare professional for proper medical advice."
        
        # TODO: Replace with actual WhatsApp sending
        logger.info(f"WhatsApp message would be sent to {phone_number}")
        logger.info(f"WhatsApp message: {whatsapp_message[:200]}...")
        
        return "whatsapp_sent"
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}")
        return "whatsapp_failed"
