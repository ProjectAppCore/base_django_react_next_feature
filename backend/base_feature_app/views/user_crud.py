from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from base_feature_app.models import User
from base_feature_app.serializers.user_create_update import UserCreateUpdateSerializer
from base_feature_app.serializers.user_detail import UserDetailSerializer
from base_feature_app.serializers.user_list import UserListSerializer


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def users(request):
    if not request.user.is_authenticated:
        return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET' and not request.user.is_staff:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        queryset = User.objects.all().order_by('-id')
        serializer = UserListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    if not request.user.is_staff:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = UserCreateUpdateSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        detail = UserDetailSerializer(user, context={'request': request})
        return Response(detail.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([AllowAny])
def user_detail(request, user_id: int):
    if not request.user.is_authenticated:
        return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET' and not request.user.is_staff:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = UserDetailSerializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method in {'PUT', 'PATCH', 'DELETE'} and not request.user.is_staff:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method in {'PUT', 'PATCH'}:
        serializer = UserCreateUpdateSerializer(user, data=request.data, partial=(request.method == 'PATCH'))
        if serializer.is_valid():
            user = serializer.save()
            detail = UserDetailSerializer(user, context={'request': request})
            return Response(detail.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
