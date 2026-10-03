"""WhatsApp Business stub. Drafts a farmer notice; never sends."""

from __future__ import annotations


TEMPLATES = {
    "en": "SolarSponge window {when}. Run {name} in this slot. Crop energy need is protected (plan {plan_id}). This is a draft, not a sent message.",
    "hi": "सोलरस्पंज खिड़की {when}। {name} इसी समय चलाएँ। फसल की ऊर्जा सुरक्षित है (योजना {plan_id})। यह केवल ड्राफ्ट है, भेजा नहीं गया।",
    "ta": "சோலார்ஸ்பாஞ்ச் நேரம் {when}. {name} இப்போது இயக்கவும். பயிர் தேவை பாதுகாக்கப்பட்டது (திட்டம் {plan_id}). இது வரைவு மட்டும்; அனுப்பப்படவில்லை.",
}


def draft_notice(name: str, when: str, plan_id: int, lang: str = "en") -> dict:
    tmpl = TEMPLATES.get(lang, TEMPLATES["en"])
    return {
        "channel": "whatsapp",
        "sent": False,
        "lang": lang,
        "to": None,
        "body": tmpl.format(when=when or "see dashboard", name=name, plan_id=plan_id),
    }
