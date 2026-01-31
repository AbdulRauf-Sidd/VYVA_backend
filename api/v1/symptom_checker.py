from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import os
import httpx
import json
import re
import random
import string
import unicodedata
import asyncio
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from models.symptom_checker import SymptomCheckerResponse
from models.user import User
from services import whatsapp_service
from services.email_service import EmailService
from services.whatsapp_service import WhatsAppService
from repositories.symptom_checker import SymptomCheckerRepository
from schemas.symptom_checker import (
    SymptomCheckerInteractionRead,
    SymptomCheckerListResponse,
    CaregiverDashboardResponse,
    VitalsHistoryResponse
)
from core.config import settings
from json import loads as json_loads
from json import JSONDecodeError

logger = logging.getLogger(__name__)

router = APIRouter()

_OPTIONAL_USER_FIELDS = [
    "full_name",
    "language",
    "model_type",
    "followup_count",
    "heart_rate",
    "severity_scale",
    "duration",
    "respiratory_rate",
    "additional_notes",
]


def _apply_optional_payload_fields(record, payload_data: dict, fields=_OPTIONAL_USER_FIELDS):
    """
    Update only the fields that were explicitly provided in the payload.
    """
    for field in fields:
        if field in payload_data:
            setattr(record, field, payload_data[field])


def _normalize_ai_summary_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed or trimmed.lower() == "null":
            return None
        if len(trimmed) > 200:
            return trimmed[:200]
        return trimmed
    return None


def _build_ai_summary_source(
    summary_text: Optional[str],
    symptoms: Optional[str],
    additional_notes: Optional[str],
    vitals_data: Optional[Dict[str, Any]],
    heart_rate: Optional[str],
    respiratory_rate: Optional[str],
) -> str:
    parts: List[str] = []
    if summary_text:
        parts.append(f"Summary: {summary_text}")
    if symptoms:
        parts.append(f"Symptoms: {symptoms}")
    if additional_notes:
        parts.append(f"Additional notes: {additional_notes}")
    vitals_parts: List[str] = []
    if heart_rate:
        vitals_parts.append(f"heart_rate={heart_rate} bpm")
    if respiratory_rate:
        vitals_parts.append(f"respiratory_rate={respiratory_rate} breaths/min")
    if vitals_data:
        vitals_parts.append(f"vitals_data={json.dumps(vitals_data, ensure_ascii=True)}")
    if vitals_parts:
        parts.append(f"Vitals: {', '.join(vitals_parts)}")
    return "\n".join(parts)


def _derive_fallback_summaries(
    symptoms: Optional[str],
    vitals_data: Optional[Dict[str, Any]],
    heart_rate: Optional[str],
    respiratory_rate: Optional[str],
) -> Dict[str, Optional[str]]:
    vitals_summary: Optional[str] = None
    symptoms_summary: Optional[str] = None

    vitals_bits: List[str] = []
    if heart_rate:
        vitals_bits.append(f"Heart rate: {heart_rate} bpm")
    if respiratory_rate:
        vitals_bits.append(f"Respiratory rate: {respiratory_rate} breaths/min")
    if not vitals_bits and vitals_data:
        heart = vitals_data.get("heart_rate") if isinstance(vitals_data, dict) else None
        resp = vitals_data.get("respiratory_rate") if isinstance(vitals_data, dict) else None
        if isinstance(heart, dict) and "value" in heart:
            vitals_bits.append(f"Heart rate: {heart.get('value')} {heart.get('unit', 'bpm')}")
        if isinstance(resp, dict) and "value" in resp:
            vitals_bits.append(
                f"Respiratory rate: {resp.get('value')} {resp.get('unit', 'breaths/min')}"
            )
    if vitals_bits:
        vitals_summary = ". ".join(vitals_bits)

    if symptoms:
        symptoms_summary = symptoms.strip()
        if len(symptoms_summary) > 200:
            symptoms_summary = symptoms_summary[:200]

    return {
        "vitals_ai_summary": vitals_summary,
        "symptoms_ai_summary": symptoms_summary,
    }


async def _extract_ai_summaries(
    summary_text: str,
    fallback: Optional[Dict[str, Optional[str]]] = None
) -> Dict[str, Optional[str]]:
    """
    Use OpenAI to extract vitals_ai_summary and symptoms_ai_summary from text.
    Returns dict with keys 'vitals_ai_summary' and 'symptoms_ai_summary' when successful.
    """
    result: Dict[str, Optional[str]] = {
        "vitals_ai_summary": None,
        "symptoms_ai_summary": None,
    }
    if fallback:
        result.update(fallback)

    if not summary_text:
        return result

    if not settings.OPENAI_API_KEY:
        logger.info("OPENAI_API_KEY not configured; skipping AI summary extraction.")
        return result

    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError:
        logger.warning("OpenAI SDK not installed; skipping AI summary extraction.")
        return result

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    model_name = settings.OPENAI_MODEL or "gpt-4o-mini"
    prompt = (
        "You will receive a short medical call summary. Extract two concise, user-friendly sentences:\n"
        "1) vitals_ai_summary: what the vitals indicate (heart rate, respiratory rate, other vitals if present). "
        "If no vitals are mentioned, respond with null.\n"
        "2) symptoms_ai_summary: what symptoms or issues the patient reports and key findings. "
        "If insufficient info, respond with null.\n\n"
        "Return a JSON object with exactly these keys: "
        '{"vitals_ai_summary": "... or null", "symptoms_ai_summary": "... or null"}.\n'
        "Keep each summary under 200 characters. Do not fabricate data."
    )

    # Trim overly long text to reduce tokens
    text = summary_text.strip()
    if len(text) > 4000:
        text = text[:4000]

    try:
        completion = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.2,
        )
        content = completion.choices[0].message.content if completion and completion.choices else None
        if content:
            try:
                parsed = json_loads(content)
                result["vitals_ai_summary"] = _normalize_ai_summary_value(
                    parsed.get("vitals_ai_summary")
                )
                result["symptoms_ai_summary"] = _normalize_ai_summary_value(
                    parsed.get("symptoms_ai_summary")
                )
            except (JSONDecodeError, AttributeError) as parse_err:
                logger.warning("Failed to parse AI summaries JSON: %s", parse_err)
    except Exception as exc:
        logger.warning("AI summary extraction failed: %s", exc)

    return result


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
    user_id: int  # Required - to fetch preferred reports channel
    conversation_id: str  # Required - to identify the specific report
    action: Optional[str] = None  # Deprecated: use preferred_reports_channel
    recipient_email: Optional[str] = None  # Deprecated: use user's email
    phone_number: Optional[str] = None  # Deprecated: use user's phone_number
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
        "emergency", "urgent", "immediate", "serious", "grave", "severe", "critical",
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
            "language" : "Spanish",
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
    payload_data = payload.model_dump(exclude_unset=True)

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
            # Save or update error response to database (upsert by conversation_id)
            result = await db.execute(
                select(SymptomCheckerResponse).where(
                    SymptomCheckerResponse.conversation_id == conversation_id
                )
            )
            existing_record = result.scalar_one_or_none()

            if existing_record:
                existing_record.symptoms = payload.symptoms
                _apply_optional_payload_fields(existing_record, payload_data)
                existing_record.email = ""
                existing_record.summary = ""
                existing_record.breakdown = {}
                existing_record.severity = "unknown"
                existing_record.is_emergency = False
                existing_record.status = "error"
            else:
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

        # Extract AI summaries (vitals/symptoms) from summary text using OpenAI
        ai_summary_source = _build_ai_summary_source(
            summary_text=summary,
            symptoms=payload.symptoms,
            additional_notes=payload.additional_notes,
            vitals_data=None,
            heart_rate=payload.heart_rate,
            respiratory_rate=payload.respiratory_rate,
        )
        fallback_summaries = _derive_fallback_summaries(
            symptoms=payload.symptoms,
            vitals_data=None,
            heart_rate=payload.heart_rate,
            respiratory_rate=payload.respiratory_rate,
        )
        ai_summaries = await _extract_ai_summaries(ai_summary_source, fallback=fallback_summaries)
        vitals_ai_summary = ai_summaries.get("vitals_ai_summary")
        symptoms_ai_summary = ai_summaries.get("symptoms_ai_summary")

        # Save complete response to database (upsert by conversation_id)
        result = await db.execute(
            select(SymptomCheckerResponse).where(
                SymptomCheckerResponse.conversation_id == conversation_id
            )
        )
        existing_record = result.scalar_one_or_none()

        if existing_record:
            existing_record.symptoms = payload.symptoms
            _apply_optional_payload_fields(existing_record, payload_data)
            existing_record.email = email
            existing_record.summary = summary
            existing_record.breakdown = breakdown
            if vitals_ai_summary is not None:
                existing_record.vitals_ai_summary = vitals_ai_summary
            if symptoms_ai_summary is not None:
                existing_record.symptoms_ai_summary = symptoms_ai_summary
            existing_record.severity = "grave" if is_emergency else "leve"
            existing_record.is_emergency = is_emergency
            existing_record.status = "success"
        else:
            base_data = {
                "conversation_id": conversation_id,
                "symptoms": payload.symptoms,
                "email": email,
                "summary": summary,
                "breakdown": breakdown,
                "severity": "grave" if is_emergency else "leve",
                "is_emergency": is_emergency,
                "status": "success",
            }
            for field in _OPTIONAL_USER_FIELDS:
                if field in payload_data:
                    base_data[field] = payload_data[field]
            if vitals_ai_summary is not None:
                base_data["vitals_ai_summary"] = vitals_ai_summary
            if symptoms_ai_summary is not None:
                base_data["symptoms_ai_summary"] = symptoms_ai_summary
            response_record = SymptomCheckerResponse(**base_data)
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
            await db.rollback()
            result = await db.execute(
                select(SymptomCheckerResponse).where(
                    SymptomCheckerResponse.conversation_id == conversation_id
                )
            )
            existing_record = result.scalar_one_or_none()

            if existing_record:
                existing_record.symptoms = payload.symptoms
                _apply_optional_payload_fields(existing_record, payload_data)
                existing_record.email = ""
                existing_record.summary = ""
                existing_record.breakdown = {}
                if "vitals_ai_summary" in payload_data:
                    existing_record.vitals_ai_summary = payload_data["vitals_ai_summary"]
                if "symptoms_ai_summary" in payload_data:
                    existing_record.symptoms_ai_summary = payload_data["symptoms_ai_summary"]
                existing_record.severity = "unknown"
                existing_record.is_emergency = False
                existing_record.status = "error"
            else:
                base_data = {
                    "conversation_id": conversation_id,
                    "symptoms": payload.symptoms,
                    "email": "",
                    "summary": "",
                    "breakdown": {},
                    "severity": "unknown",
                    "is_emergency": False,
                    "status": "error",
                }
                for field in _OPTIONAL_USER_FIELDS:
                    if field in payload_data:
                        base_data[field] = payload_data[field]
                if "vitals_ai_summary" in payload_data:
                    base_data["vitals_ai_summary"] = payload_data["vitals_ai_summary"]
                if "symptoms_ai_summary" in payload_data:
                    base_data["symptoms_ai_summary"] = payload_data["symptoms_ai_summary"]
                error_response = SymptomCheckerResponse(**base_data)
                db.add(error_response)

            await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to save error to database: {str(db_error)}")

        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/send-report", status_code=status.HTTP_200_OK)
async def send_report(payload: SendReportRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Send a medical report via the user's preferred reports channel.
    """
    logger.info("=== SEND REPORT ENDPOINT CALLED ===")
    logger.info(f"Received payload: {payload.model_dump()}")

    try:
        # Get the specific analysis record by conversation_id
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

        # Get user and preferred reports channel
        user_result = await db.execute(
            select(User).where(User.id == payload.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User not found for user_id: {payload.user_id}"
            )

        if response_record.user_id and response_record.user_id != user.id:
            raise HTTPException(
                status_code=400,
                detail="User does not match the requested report."
            )

        preferred_reports_channel = (user.preferred_reports_channel or "").strip().lower()
        if preferred_reports_channel not in ["email", "whatsapp"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid preferred reports channel. Must be 'email' or 'whatsapp'."
            )

        recipient_email = (user.email or "").strip()
        phone_number = (user.phone_number or "").strip()

        if preferred_reports_channel == "email" and not recipient_email:
            raise HTTPException(
                status_code=400,
                detail="User email is required to send report via email."
            )

        if preferred_reports_channel == "whatsapp" and not phone_number:
            raise HTTPException(
                status_code=400,
                detail="User phone_number is required to send report via WhatsApp."
            )

        # Prepare report content
        report_content = _prepare_report_content(response_record, payload)

        # Send report based on action
        send_result = None
        caregiver_results = {"email": None, "whatsapp": None}

        if preferred_reports_channel == "email":
            send_result = await _send_email_report(
                recipient_email=recipient_email,
                report_content=report_content,
                patient_name=response_record.full_name or " "
            )
        elif preferred_reports_channel == "whatsapp":
            send_result = await _send_whatsapp_report(
                phone_number=phone_number,
                report_content=report_content,
                patient_name=response_record.full_name or " "
            )

        # Send report to caregiver/caretaker if available
        # caretaker = user.caretaker
        # if caretaker:
        #     caretaker_email = (caretaker.email or "").strip()
        #     caretaker_phone = (caretaker.phone_number or "").strip()

        #     if caretaker_email:
        #         caregiver_results["email"] = await _send_email_report(
        #             recipient_email=caretaker_email,
        #             report_content=report_content,
        #             patient_name=response_record.full_name or " "
        #         )

        #     if caretaker_phone:
        #         caregiver_results["whatsapp"] = await _send_whatsapp_report(
        #             phone_number=caretaker_phone,
        #             report_content=report_content,
        #             patient_name=response_record.full_name or " "
        #         )

        # Send report to doctor if symptoms are severe
        is_severe = (response_record.severity or "").strip().lower() == "severe"
        # if is_severe:
        #     doctor_email = ""  # TODO: Provide doctor email from client
        #     if doctor_email:
        #         doctor_result = await _send_email_report(
        #             recipient_email=doctor_email,
        #             report_content=report_content,
        #             patient_name=response_record.full_name or " "
        #         )
        #     else:
        #         doctor_result = "doctor_email_missing"

        logger.info(
            f"Report sent successfully for conversation_id: {response_record.conversation_id}")

        return {
            "message": "Report sent successfully",
            "conversation_id": response_record.conversation_id,
            "action": preferred_reports_channel,
            "status": send_result,
            "caregiver_status": caregiver_results,
            "doctor_status": "pending" if is_severe else "not_applicable",
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
        "user_id": response_record.user_id or payload.user_id,
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


@router.post(
    "/backfill-ai-summaries",
    summary="Backfill AI summaries for symptom records",
    description="Generate missing vitals_ai_summary and symptoms_ai_summary for existing records"
)
async def backfill_ai_summaries(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records to process"),
    start_date: Optional[datetime] = Query(None, description="Filter records from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter records until this date"),
    dry_run: bool = Query(False, description="If true, do not persist changes"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    try:
        query = select(SymptomCheckerResponse).where(
            or_(
                SymptomCheckerResponse.vitals_ai_summary.is_(None),
                SymptomCheckerResponse.symptoms_ai_summary.is_(None)
            )
        )

        if start_date:
            query = query.where(SymptomCheckerResponse.created_at >= start_date)
        if end_date:
            query = query.where(SymptomCheckerResponse.created_at <= end_date)

        query = query.order_by(SymptomCheckerResponse.created_at.desc()).limit(limit)
        result = await db.execute(query)
        records = result.scalars().all()

        updated = 0
        processed = 0

        for record in records:
            processed += 1
            ai_summary_source = _build_ai_summary_source(
                summary_text=record.summary,
                symptoms=record.symptoms,
                additional_notes=record.additional_notes,
                vitals_data=record.vitals_data,
                heart_rate=record.heart_rate,
                respiratory_rate=record.respiratory_rate,
            )
            fallback_summaries = _derive_fallback_summaries(
                symptoms=record.symptoms,
                vitals_data=record.vitals_data,
                heart_rate=record.heart_rate,
                respiratory_rate=record.respiratory_rate,
            )
            ai_summaries = await _extract_ai_summaries(
                ai_summary_source,
                fallback=fallback_summaries
            )

            vitals_ai_summary = ai_summaries.get("vitals_ai_summary")
            symptoms_ai_summary = ai_summaries.get("symptoms_ai_summary")

            if not dry_run:
                changed = False
                if record.vitals_ai_summary is None and vitals_ai_summary is not None:
                    record.vitals_ai_summary = vitals_ai_summary
                    changed = True
                if record.symptoms_ai_summary is None and symptoms_ai_summary is not None:
                    record.symptoms_ai_summary = symptoms_ai_summary
                    changed = True
                if changed:
                    updated += 1

        if not dry_run:
            await db.commit()

        return {
            "processed": processed,
            "updated": updated,
            "dry_run": dry_run
        }

    except Exception as e:
        logger.error(f"Backfill failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backfill failed: {str(e)}"
        )


# ============================================================================
# CAREGIVER DASHBOARD ENDPOINTS
# ============================================================================

@router.get(
    "/interactions/user/{user_id}",
    response_model=SymptomCheckerListResponse,
    summary="Get all interactions for a user",
    description="Retrieve all symptom checker interactions for a specific user with pagination"
)
async def get_user_interactions(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db)
) -> SymptomCheckerListResponse:
    """
    Get all symptom checker interactions for a specific user.
    
    - **user_id**: The ID of the user
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 100)
    """
    try:
        repo = SymptomCheckerRepository(db)
        
        # Get interactions
        interactions = await repo.get_by_user_id(user_id, skip=skip, limit=limit)
        
        # Get total count for pagination
        total = await repo.count_by_user_id(user_id)
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        current_page = (skip // limit) + 1 if limit > 0 else 1
        
        return SymptomCheckerListResponse(
            items=interactions,
            total=total,
            page=current_page,
            page_size=limit,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error getting user interactions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve interactions: {str(e)}"
        )


@router.get(
    "/interactions/user/{user_id}/latest",
    response_model=SymptomCheckerInteractionRead,
    summary="Get latest interaction for a user",
    description="Retrieve the most recent symptom checker interaction for a specific user"
)
async def get_latest_user_interaction(
    user_id: int,
    db: AsyncSession = Depends(get_db)
) -> SymptomCheckerInteractionRead:
    try:
        repo = SymptomCheckerRepository(db)
        interactions = await repo.get_recent_interactions(limit=1, user_id=user_id)
        if not interactions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No interactions found for user_id {user_id}"
            )
        return interactions[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest user interaction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve latest interaction: {str(e)}"
        )


@router.get(
    "/interactions/caretaker/{caretaker_id}",
    response_model=SymptomCheckerListResponse,
    summary="Get interactions for caretaker's users",
    description="Retrieve all symptom checker interactions for users assigned to a caretaker"
)
async def get_caretaker_interactions(
    caretaker_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    user_id: Optional[int] = Query(None, description="Optional filter by specific user ID"),
    start_date: Optional[datetime] = Query(None, description="Filter interactions from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter interactions until this date"),
    db: AsyncSession = Depends(get_db)
) -> SymptomCheckerListResponse:
    """
    Get all symptom checker interactions for users assigned to a caretaker.
    
    - **caretaker_id**: The ID of the caretaker
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 100)
    - **user_id**: Optional filter for a specific user
    - **start_date**: Optional start date filter (ISO format)
    - **end_date**: Optional end date filter (ISO format)
    """
    try:
        repo = SymptomCheckerRepository(db)
        
        # Get interactions
        interactions = await repo.get_by_caretaker(
            caretaker_id=caretaker_id,
            skip=skip,
            limit=limit,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get total count for pagination
        total = await repo.count_by_caretaker(caretaker_id, user_id=user_id)
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        current_page = (skip // limit) + 1 if limit > 0 else 1
        
        return SymptomCheckerListResponse(
            items=interactions,
            total=total,
            page=current_page,
            page_size=limit,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error getting caretaker interactions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve interactions: {str(e)}"
        )


@router.get(
    "/interactions/{interaction_id}",
    response_model=SymptomCheckerInteractionRead,
    summary="Get a specific interaction",
    description="Retrieve detailed information about a single symptom checker interaction"
)
async def get_interaction(
    interaction_id: int,
    db: AsyncSession = Depends(get_db)
) -> SymptomCheckerInteractionRead:
    """
    Get a specific symptom checker interaction by ID.
    
    - **interaction_id**: The ID of the interaction
    """
    try:
        repo = SymptomCheckerRepository(db)
        interaction = await repo.get_by_id(interaction_id)
        
        if not interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interaction with ID {interaction_id} not found"
            )
        
        return interaction
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting interaction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve interaction: {str(e)}"
        )


@router.get(
    "/interactions/conversation/{conversation_id}",
    response_model=SymptomCheckerInteractionRead,
    summary="Get interaction by conversation ID",
    description="Retrieve detailed information about a symptom checker interaction by conversation_id"
)
async def get_interaction_by_conversation_id(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
) -> SymptomCheckerInteractionRead:
    """
    Get a specific symptom checker interaction by conversation_id.
    
    - **conversation_id**: The conversation ID of the interaction
    """
    try:
        repo = SymptomCheckerRepository(db)
        interaction = await repo.get_by_conversation_id(conversation_id)
        
        if not interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interaction with conversation_id '{conversation_id}' not found"
            )
        
        return interaction
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting interaction by conversation_id: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve interaction: {str(e)}"
        )


@router.get(
    "/dashboard/caretaker/{caretaker_id}",
    response_model=CaregiverDashboardResponse,
    summary="Get aggregated dashboard view for caretaker",
    description="Get summary statistics and recent interactions for a caretaker's dashboard"
)
async def get_caretaker_dashboard(
    caretaker_id: int,
    recent_limit: int = Query(5, ge=1, le=20, description="Number of recent interactions to return"),
    db: AsyncSession = Depends(get_db)
) -> CaregiverDashboardResponse:
    """
    Get aggregated dashboard view for a caretaker.
    
    Returns summary statistics including:
    - Total interactions
    - Recent interactions
    - Emergency count
    - Average vitals (heart rate, respiratory rate)
    - Last interaction date
    
    - **caretaker_id**: The ID of the caretaker
    - **recent_limit**: Number of recent interactions to include (default: 5)
    """
    try:
        repo = SymptomCheckerRepository(db)
        
        # Get total count
        total_interactions = await repo.count_by_caretaker(caretaker_id)
        
        # Get recent interactions
        recent_interactions = await repo.get_by_caretaker(
            caretaker_id=caretaker_id,
            skip=0,
            limit=recent_limit
        )
        
        # Calculate emergency count
        emergency_count = sum(1 for interaction in recent_interactions if interaction.is_emergency)
        
        # Calculate average vitals from interactions with vitals_data
        heart_rates = []
        respiratory_rates = []
        
        for interaction in recent_interactions:
            if interaction.vitals_data:
                hr = interaction.vitals_data.get("heart_rate", {})
                rr = interaction.vitals_data.get("respiratory_rate", {})
                
                if hr and "value" in hr:
                    try:
                        heart_rates.append(float(hr["value"]))
                    except (ValueError, TypeError):
                        pass
                
                if rr and "value" in rr:
                    try:
                        respiratory_rates.append(float(rr["value"]))
                    except (ValueError, TypeError):
                        pass
        
        average_heart_rate = sum(heart_rates) / len(heart_rates) if heart_rates else None
        average_respiratory_rate = sum(respiratory_rates) / len(respiratory_rates) if respiratory_rates else None
        
        # Get last interaction date
        last_interaction_date = None
        if recent_interactions:
            last_interaction = recent_interactions[0]
            last_interaction_date = last_interaction.call_timestamp or last_interaction.created_at
        
        return CaregiverDashboardResponse(
            total_interactions=total_interactions,
            recent_interactions=recent_interactions,
            emergency_count=emergency_count,
            average_heart_rate=round(average_heart_rate, 2) if average_heart_rate else None,
            average_respiratory_rate=round(average_respiratory_rate, 2) if average_respiratory_rate else None,
            last_interaction_date=last_interaction_date
        )
        
    except Exception as e:
        logger.error(f"Error getting caretaker dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard data: {str(e)}"
        )


@router.get(
    "/vitals/user/{user_id}",
    response_model=VitalsHistoryResponse,
    summary="Get vitals history for a user",
    description="Retrieve time-series vitals data (heart rate, respiratory rate) for a user"
)
async def get_user_vitals_history(
    user_id: int,
    start_date: Optional[datetime] = Query(None, description="Filter vitals from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter vitals until this date"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db)
) -> VitalsHistoryResponse:
    """
    Get vitals history for a user.
    
    Returns time-series data of vitals measurements including:
    - Heart rate values with timestamps
    - Respiratory rate values with timestamps
    
    - **user_id**: The ID of the user
    - **start_date**: Optional start date filter (ISO format)
    - **end_date**: Optional end date filter (ISO format)
    - **limit**: Maximum number of records to return (max 200)
    """
    try:
        repo = SymptomCheckerRepository(db)
        
        # Get interactions with vitals data
        if start_date and end_date:
            interactions = await repo.get_interactions_by_date_range(
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
                skip=0,
                limit=limit
            )
        else:
            interactions = await repo.get_by_user_id(user_id, skip=0, limit=limit)
        
        # Extract vitals records
        vitals_records = []
        for interaction in interactions:
            if interaction.vitals_data:
                record = {
                    "timestamp": interaction.call_timestamp.isoformat() if interaction.call_timestamp else interaction.created_at.isoformat(),
                    "interaction_id": interaction.id,
                    "conversation_id": interaction.conversation_id
                }
                
                # Add heart rate if available
                if "heart_rate" in interaction.vitals_data:
                    record["heart_rate"] = interaction.vitals_data["heart_rate"]
                
                # Add respiratory rate if available
                if "respiratory_rate" in interaction.vitals_data:
                    record["respiratory_rate"] = interaction.vitals_data["respiratory_rate"]
                
                vitals_records.append(record)
        
        return VitalsHistoryResponse(
            user_id=user_id,
            vitals_records=vitals_records
        )
        
    except Exception as e:
        logger.error(f"Error getting vitals history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve vitals history: {str(e)}"
        )
