from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from base_feature_app.models import Sale
from base_feature_app.serializers.sale_detail import SaleDetailSerializer
from base_feature_app.serializers.sale_list import SaleListSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def sales(request):
    if not request.user.is_authenticated:
        return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

    if not request.user.is_staff:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    queryset = Sale.objects.all().order_by('-id')
    serializer = SaleListSerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def sale_detail(request, sale_id: int):
    if not request.user.is_authenticated:
        return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

    if not request.user.is_staff:
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        sale = Sale.objects.get(id=sale_id)
    except Sale.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = SaleDetailSerializer(sale, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)
