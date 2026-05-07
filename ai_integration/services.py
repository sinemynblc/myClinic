import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def _call_gemini(prompt):
    api_key = os.getenv('GEMINI_API_KEY')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    response = requests.post(
        url,
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=10
    )
    data = response.json()
    print(f"Gemini response: {data}")  # tam response'u görmek için
    return data['candidates'][0]['content']['parts'][0]['text']


def calculate_dynamic_fee(doctor_id, base_fee, booked_slots, total_slots, avg_patient_rating):
    try:
        rating_text = f"{avg_patient_rating:.1f}/5" if avg_patient_rating else "no ratings yet"
        prompt = f"""You are a clinic pricing engine. Calculate a fair appointment fee.
Input:
- Base fee: {base_fee} TRY
- Booked slots today: {booked_slots}/{total_slots}
- Doctor avg rating: {rating_text}
Rules:
- Higher occupancy = higher fee (max +30%)
- Higher rating = higher fee (max +20%)
- Never go below base fee
Respond with ONLY: {{"calculated_fee": 550.00}}"""

        text = _call_gemini(prompt).strip()
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return float(json.loads(text)['calculated_fee'])
    except Exception as e:
        print(f"AI pricing failed: {type(e).__name__}: {e}")
        return float(base_fee)


def analyze_test_results(test_data, test_type):
    try:
        prompt = f"""You are a medical AI assistant. Analyze these test results.
Test type: {test_type}
Data: {test_data}
Respond with ONLY:
{{"anomalies": ["finding1"], "suggestions": "brief suggestion", "disclaimer": "AI analysis is advisory only."}}"""

        text = _call_gemini(prompt).strip()
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"AI analysis failed: {type(e).__name__}: {e}")
        return {
            "anomalies": [],
            "suggestions": "AI service unavailable.",
            "disclaimer": "AI analysis is advisory only.",
            "fallback": True
        }