from django.urls import path
from django.views.generic import TemplateView
from .views import (
    home,
    checkout,
    products
)

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("checkout/", checkout, name="checkout"),
    path("products/", products, name="products"),
]
