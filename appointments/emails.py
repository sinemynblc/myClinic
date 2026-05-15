import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

CLINIC   = getattr(settings, 'CLINIC_NAME', 'myClinic')
FROM     = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@myclinic.com')
DIVIDER  = '─' * 42


def _fmt(appointment):
    """Return a dict of shared formatted values for email templates."""
    dt = appointment.date_time
    return {
        'patient_name':  appointment.patient.full_name or appointment.patient.user.email,
        'patient_email': appointment.patient.user.email,
        'doctor_name':   f"Dr. {appointment.doctor.full_name}",
        'doctor_email':  appointment.doctor.user.email,
        'specialty':     appointment.doctor.specialty,
        'date':          dt.strftime('%A, %d %B %Y'),
        'time':          dt.strftime('%H:%M'),
        'fee':           f"{appointment.calculated_fee:.0f} TRY" if appointment.calculated_fee else 'TBD',
    }


def send_booking_confirmation(appointment):
    """Instant confirmation email → Patient."""
    try:
        f = _fmt(appointment)
        subject = f"[{CLINIC}] Appointment Confirmed – {f['date']} at {f['time']}"
        body = f"""Dear {f['patient_name']},

Your appointment has been successfully confirmed.

{DIVIDER}
  APPOINTMENT CONFIRMATION
{DIVIDER}
  Clinic     :  {CLINIC}
  Doctor     :  {f['doctor_name']} ({f['specialty']})
  Date       :  {f['date']}
  Time       :  {f['time']}
  Fee        :  {f['fee']}
  Status     :  ✔ Confirmed
{DIVIDER}

Please arrive 10 minutes before your appointment.
To cancel, log in to {CLINIC} at least 24 hours in advance.

Best regards,
{CLINIC} Team
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=FROM,
            recipient_list=[f['patient_email']],
            fail_silently=True,
        )
        logger.info("[email] Booking confirmation → %s", f['patient_email'])
    except Exception as exc:
        logger.warning("[email] Confirmation failed: %s", exc)


def send_doctor_notification(appointment):
    """New appointment alert → Doctor."""
    try:
        f = _fmt(appointment)
        subject = f"[{CLINIC}] New Appointment – {f['patient_name']} on {f['date']}"
        body = f"""Dear {f['doctor_name']},

A new appointment has been scheduled with you.

{DIVIDER}
  NEW APPOINTMENT ALERT
{DIVIDER}
  Clinic     :  {CLINIC}
  Patient    :  {f['patient_name']}
  Date       :  {f['date']}
  Time       :  {f['time']}
  Fee        :  {f['fee']}
{DIVIDER}

Please log in to {CLINIC} to view full patient details.

Best regards,
{CLINIC} System
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=FROM,
            recipient_list=[f['doctor_email']],
            fail_silently=True,
        )
        logger.info("[email] Doctor notification → %s", f['doctor_email'])
    except Exception as exc:
        logger.warning("[email] Doctor notification failed: %s", exc)


def send_followup_reminder(appointment):
    """
    Simulated 24-hour follow-up reminder → Patient.

    [DEMO PLACEHOLDER] In production this is triggered by a scheduled task
    (e.g. Celery beat) 24 hours before the appointment date_time.
    For the demo it is called immediately after booking to show the email format.
    """
    try:
        f = _fmt(appointment)
        subject = f"[{CLINIC}] Reminder – Your appointment tomorrow at {f['time']}"
        body = f"""Dear {f['patient_name']},

This is your 24-hour reminder for an upcoming appointment.

{DIVIDER}
  APPOINTMENT REMINDER
{DIVIDER}
  Clinic     :  {CLINIC}
  Doctor     :  {f['doctor_name']} ({f['specialty']})
  Date       :  {f['date']}
  Time       :  {f['time']}
{DIVIDER}

━━ DEMO NOTE ━━━━━━━━━━━━━━━━━━━━━━━━━━
In production this email is sent automatically
24 hours before the appointment via a
scheduled background task (Celery / cron).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{CLINIC} Team
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=FROM,
            recipient_list=[f['patient_email']],
            fail_silently=True,
        )
        logger.info("[email] Follow-up reminder (DEMO) → %s", f['patient_email'])
    except Exception as exc:
        logger.warning("[email] Follow-up reminder failed: %s", exc)
