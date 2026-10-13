# api/auth.py — login por token para o front
from rest_framework import permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer


class LoginView(ObtainAuthToken):
    """POST usuário e senha → devolve o token. Limitado a 10 tentativas/min (anti força bruta)."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        operation_id='auth_login', auth=[],
        tags=['auth'],
        summary='Login: troca usuário e senha por um token',
        request=inline_serializer('LoginRequest', {
            'username': serializers.CharField(),
            'password': serializers.CharField(),
        }),
        responses={200: inline_serializer('TokenResponse', {'token': serializers.CharField()}),
                   400: None, 429: None},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class MeView(APIView):
    """Quem está logado — o front usa para saber se o token ainda vale."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id='auth_me', tags=['auth'], summary='Dados do usuário logado',
        responses=inline_serializer('MeResponse', {
            'username': serializers.CharField(),
            'email': serializers.CharField(),
            'is_staff': serializers.BooleanField(),
        }),
    )
    def get(self, request):
        u = request.user
        return Response({'username': u.get_username(), 'email': u.email, 'is_staff': u.is_staff})


class LogoutView(APIView):
    """Apaga o token do usuário (o próximo login gera outro)."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(operation_id='auth_logout', tags=['auth'],
                   summary='Logout: invalida o token', request=None,
                   responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)