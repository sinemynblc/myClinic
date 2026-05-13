import threading
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import close_old_connections
from medical.models import MedicalRecord
from medical.serializers import MedicalRecordSerializer
from users.permissions import IsDoctor


class RerunAnalysisView(APIView):
    """
    Allows a doctor to manually retrigger AI analysis on an existing record.
    Useful when: the background task failed, test data was updated, or the
    doctor wants a second AI pass before approving the record.
    """
    permission_classes = [IsDoctor]

    def post(self, request, record_id):
        doctor = request.user.doctor

        try:
            record = MedicalRecord.objects.get(id=record_id, doctor=doctor)
        except MedicalRecord.DoesNotExist:
            return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

        if not record.analysis_data:
            return Response(
                {'error': 'This record has no analysis_data to process.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reset so the frontend knows a fresh analysis is in progress.
        MedicalRecord.objects.filter(id=record_id).update(
            ai_suggestions=None,
            doctor_approved=False,
        )

        def _run_ai(r_id, test_data, test_type):
            close_old_connections()
            try:
                from ai_integration.services import analyze_test_results
                suggestions = analyze_test_results(test_data=test_data, test_type=test_type)
                MedicalRecord.objects.filter(id=r_id).update(ai_suggestions=suggestions)
            finally:
                close_old_connections()

        test_type = (record.analysis_data or {}).get('test_type', 'general')
        threading.Thread(
            target=_run_ai,
            args=(record.id, record.analysis_data, test_type),
            daemon=True,
        ).start()

        return Response(
            {
                'id': str(record.id),
                'status': 'ACCEPTED',
                'detail': 'AI re-analysis started. Poll GET /api/medical/records/<id>/ for results.',
                'poll_url': f'/api/medical/records/{record.id}/',
            },
            status=status.HTTP_202_ACCEPTED,
        )