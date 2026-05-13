from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg, Sum, Count, Q
from .models import LeaveRequest
from .serializers import CreateLeaveRequestSerializer, ApproveLeaveSerializer, LeaveRequestSerializer
from users.models import Doctor, Manager
from appointments.models import Appointment


class SubmitLeaveRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response({'error': 'Only doctors can submit leave requests'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CreateLeaveRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        conflicts = Appointment.objects.filter(
            doctor=doctor,
            date_time__date__gte=serializer.validated_data['start_date'],
            date_time__date__lte=serializer.validated_data['end_date'],
            status=Appointment.Status.BOOKED
        ).values_list('id', flat=True)

        leave_request = LeaveRequest.objects.create(
            doctor=doctor,
            start_date=serializer.validated_data['start_date'],
            end_date=serializer.validated_data['end_date'],
            reason=serializer.validated_data['reason'],
            leave_type=serializer.validated_data['leave_type'],
            status=LeaveRequest.Status.PENDING,
        )

        response_data = LeaveRequestSerializer(leave_request).data
        if conflicts:
            response_data['warning'] = f"You have {len(conflicts)} booked appointment(s) during this period."

        return Response(response_data, status=status.HTTP_201_CREATED)


class ListLeaveRequestsView(APIView):
    """
    GET for doctors: returns their own leave requests.
    GET for managers: returns all PENDING leave requests awaiting action.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if hasattr(user, 'doctor'):
            leaves = LeaveRequest.objects.filter(doctor=user.doctor).order_by('-created_at')
            return Response(LeaveRequestSerializer(leaves, many=True).data)

        if hasattr(user, 'manager'):
            leaves = LeaveRequest.objects.filter(
                status=LeaveRequest.Status.PENDING
            ).order_by('created_at')
            return Response(LeaveRequestSerializer(leaves, many=True).data)

        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)


class ApproveLeaveRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, leave_id):
        try:
            manager = Manager.objects.get(user=request.user)
        except Manager.DoesNotExist:
            return Response({'error': 'Only managers can approve leave requests'}, status=status.HTTP_403_FORBIDDEN)

        try:
            leave_request = LeaveRequest.objects.get(id=leave_id)
        except LeaveRequest.DoesNotExist:
            return Response({'error': 'Leave request not found'}, status=status.HTTP_404_NOT_FOUND)

        # Only PENDING requests can be actioned; prevent overwriting a final decision.
        if leave_request.status != LeaveRequest.Status.PENDING:
            return Response(
                {'error': f'This request is already {leave_request.status}.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ApproveLeaveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        leave_request.status = serializer.validated_data['status']
        leave_request.manager = manager
        leave_request.save()

        return Response(LeaveRequestSerializer(leave_request).data)


class AnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            Manager.objects.get(user=request.user)
        except Manager.DoesNotExist:
            return Response({'error': 'Only managers can view analytics'}, status=status.HTTP_403_FORBIDDEN)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_filter = Q(
            appointments__date_time__date__gte=start_date,
            appointments__date_time__date__lte=end_date,
        )

        appointments = Appointment.objects.filter(
            date_time__date__gte=start_date,
            date_time__date__lte=end_date,
        )

        completed = appointments.filter(status=Appointment.Status.COMPLETED)
        total_revenue = completed.aggregate(total=Sum('calculated_fee'))['total'] or 0
        avg_satisfaction = completed.aggregate(avg=Avg('patient_rating'))['avg']

        total_slots = appointments.count()
        booked_slots = appointments.filter(status=Appointment.Status.BOOKED).count()
        vacancy_rate = 1 - (booked_slots / total_slots) if total_slots > 0 else 1

        doctor_performance = Doctor.objects.annotate(
            appointment_count=Count('appointments', filter=date_filter),
            avg_rating=Avg('appointments__patient_rating', filter=date_filter),
        ).values('user__id', 'full_name', 'appointment_count', 'avg_rating')

        return Response({
            'period': {'start_date': start_date, 'end_date': end_date},
            'total_appointments': appointments.count(),
            'total_revenue': float(total_revenue),
            'vacancy_rate': round(vacancy_rate, 2),
            'avg_satisfaction_score': round(avg_satisfaction, 2) if avg_satisfaction else None,
            'doctor_performance': list(doctor_performance),
        })