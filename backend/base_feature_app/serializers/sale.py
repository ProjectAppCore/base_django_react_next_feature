from django.db import transaction
from rest_framework import serializers
from base_feature_app.models import Sale, SoldProduct, Product
from base_feature_app.serializers.product import ProductSerializer

class SoldProductSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)
    product = ProductSerializer(read_only=True)

    class Meta:
        model = SoldProduct
        fields = ['product_id', 'product', 'quantity']

    def validate_product_id(self, value):
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Product does not exist.')
        return value

class SaleSerializer(serializers.ModelSerializer):
    sold_products = SoldProductSerializer(many=True)

    class Meta:
        model = Sale
        fields = '__all__'

    @transaction.atomic
    def create(self, validated_data):
        sold_products_data = validated_data.pop('sold_products')
        sale = Sale.objects.create(**validated_data)
        for sold_product_data in sold_products_data:
            product_id = sold_product_data.pop('product_id')
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist as exc:
                raise serializers.ValidationError({
                    'sold_products': ['One or more products no longer exist.'],
                }) from exc
            sold_product = SoldProduct.objects.create(product=product, **sold_product_data)
            sale.sold_products.add(sold_product)
        return sale
