import os
import re
import json
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _call_gemini(prompt):
    api_key = os.getenv('GEMINI_API_KEY')
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.0-flash:generateContent?key={api_key}"
    )
    response = requests.post(
        url,
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()['candidates'][0]['content']['parts'][0]['text']


def _extract_json(text):
    """
    Robustly extract a JSON object from a Gemini response.
    Handles bare JSON, ```json ... ``` fences, and leading/trailing prose.
    """
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON object found in response: {text[:200]}")


def calculate_dynamic_fee(doctor_id, base_fee, booked_slots, total_slots, avg_patient_rating):
    """
    Dynamic Pricing AI module.
    Returns the calculated fee as a float. Falls back to base_fee on any error.
    """
    try:
        occupancy_pct = round((booked_slots / total_slots) * 100) if total_slots else 0
        rating_text = f"{avg_patient_rating:.1f}/5" if avg_patient_rating else "no ratings yet"

        prompt = f"""You are a clinic dynamic pricing engine. Calculate a fair consultation fee.

Inputs:
- Base fee: {base_fee} TRY
- Today's occupancy: {booked_slots}/{total_slots} slots booked ({occupancy_pct}%)
- Doctor average patient rating: {rating_text}

Pricing rules (apply both multipliers on top of base fee):
- Occupancy above 70% → add up to +30% (proportional)
- Rating above 4.0/5 → add up to +20% (proportional)
- Final fee must never be lower than the base fee
- Round to nearest 0.50 TRY

Respond with ONLY a valid JSON object, no explanation outside it:
{{"calculated_fee": <number>, "reasoning": "<one sentence explaining the adjustments>"}}"""

        text = _call_gemini(prompt).strip()
        result = _extract_json(text)

        fee = float(result['calculated_fee'])
        reasoning = result.get('reasoning', '')
        logger.info("Dynamic fee for doctor %s: %.2f TRY (%s)", doctor_id, fee, reasoning)
        return fee

    except Exception as e:
        logger.warning("Dynamic pricing failed for doctor %s: %s: %s", doctor_id, type(e).__name__, e)
        return float(base_fee)


def analyze_test_results(test_data, test_type):
    """
    Medical Test Analysis AI module.
    Returns a structured dict written into MedicalRecord.ai_suggestions.

    Output schema:
    {
        "test_type": str,
        "anomalies": [{"parameter": str, "value": str, "reference": str, "severity": "low|moderate|high"}],
        "summary": str,
        "suggestions": str,
        "disclaimer": str
    }
    """
    try:
        prompt = f"""You are a medical AI assistant helping a licensed doctor review lab results.
Your output will be stored and reviewed by the doctor before any clinical use.

Test type: {test_type}
Test data: {json.dumps(test_data) if isinstance(test_data, dict) else test_data}

Instructions:
- Identify parameters that fall outside normal reference ranges
- For each anomaly, state the parameter name, measured value, normal reference range, and severity (low / moderate / high)
- Write a brief clinical summary (2-3 sentences)
- Suggest follow-up actions for the doctor to consider
- Always include the disclaimer

Respond with ONLY a valid JSON object, no explanation outside it:
{{
  "test_type": "{test_type}",
  "anomalies": [
    {{"parameter": "<name>", "value": "<measured>", "reference": "<normal range>", "severity": "<low|moderate|high>"}}
  ],
  "summary": "<2-3 sentence clinical summary>",
  "suggestions": "<recommended follow-up actions for the doctor>",
  "disclaimer": "This AI analysis is advisory only. A licensed physician must review all findings before any clinical decision."
}}"""

        text = _call_gemini(prompt).strip()
        result = _extract_json(text)
        logger.info(
            "AI analysis completed for test_type=%s, anomalies found: %d",
            test_type, len(result.get('anomalies', []))
        )
        return result

    except Exception as e:
        logger.warning("AI analysis failed for test_type=%s: %s: %s", test_type, type(e).__name__, e)
        return {
            "test_type": test_type,
            "anomalies": [],
            "summary": "AI analysis could not be completed.",
            "suggestions": "Please review the raw test data manually.",
            "disclaimer": "This AI analysis is advisory only. A licensed physician must review all findings before any clinical decision.",
            "fallback": True,
        }