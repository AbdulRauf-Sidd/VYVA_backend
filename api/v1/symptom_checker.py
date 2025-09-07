from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import os
import httpx
import json
import re
import random
import string

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


@router.post("/check_symptoms", status_code=status.HTTP_200_OK)
async def check_symptoms(payload: SymptomCheckRequest) -> Dict[str, Any]:
    try:
        SSE_ENDPOINT = "https://api.backend.medisearch.io/sse/medichat"
        api_key = os.getenv("MEDISEARCH_API_KEY", "3d667019-0187-4793-b3a5-e6a14f078d40")
        request_payload = {
            "conversation": [payload.symptoms],
            "key": api_key,
            "id": _generate_id(),
            "settings": {
                # "language": payload.language or "English",
                "model_type": payload.model_type or "pro",
                "system_prompt": payload.system_prompt,
                "followup_count": payload.followup_count,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Connection": "keep-alive",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(SSE_ENDPOINT, headers=headers, content=json.dumps(request_payload))
            resp.raise_for_status()
            raw_sse = resp.text

        # Parse SSE
        chunks = re.split(r"\r?\n\r?\n", raw_sse)
        email: str = ""
        articles: List[Dict[str, Any]] = []

        for chunk in chunks:
            if not chunk.startswith("data:"):
                continue
            data_line = re.sub(r"^data:\s*", "", chunk).strip()
            if data_line == "[DONE]":
                break
            try:
                obj = json.loads(data_line)
            except Exception:
                continue

            if obj.get("event") == "articles" and isinstance(obj.get("data"), list):
                articles = obj["data"]
                continue

            if obj.get("event") == "error":
                return {"email": obj.get("data"), "breakdown": {}, "severity": "mild"}

            if obj.get("event") == "llm_response" and isinstance(obj.get("data"), str):
                email = obj["data"]

        # Replace reference markers [1, 2]
        if articles and email:
            def _replace_refs(match: re.Match) -> str:
                nums = match.group(1)
                parts = [p.strip() for p in nums.split(",")]
                anchors = []
                for p in parts:
                    try:
                        idx = int(p) - 1
                        art = articles[idx] if 0 <= idx < len(articles) else None
                        url = (art or {}).get("url") if isinstance(art, dict) else None
                        anchors.append(f"<a href=\"{url}\" target=\"_blank\">[{p}]</a>" if url else f"[{p}]")
                    except Exception:
                        anchors.append(f"[{p}]")
                return ", ".join(anchors)

            email = re.sub(r"\[(\d+(?:,\s*\d+)*)\]", _replace_refs, email)

        # Build breakdown
        lines = [ln for ln in (email or "").split("\n") if ln.strip()]
        breakdown = {
            1: payload.full_name or "",
            2: lines[0] if len(lines) > 0 else "",
            3: (lines[1] if len(lines) > 1 else "").lstrip().removeprefix("1.").strip(),
            4: (lines[2] if len(lines) > 2 else "").lstrip().removeprefix("2.").strip(),
            5: (lines[3] if len(lines) > 3 else "").lstrip().removeprefix("3.").strip(),
        }

        severity = "severe" if _is_emergency(email or payload.symptoms or "") else "mild"
        return {"email": email, "breakdown": breakdown, "severity": severity}

    except httpx.HTTPStatusError as e:
        logger.exception(f"Medisearch API error: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream medisearch error")
    except Exception as e:
        logger.exception(f"Error checking symptoms: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error checking symptoms")