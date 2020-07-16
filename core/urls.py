from django.urls import path
from django.views.generic import TemplateView
from .views import (
    HomeView,
    checkout,
    ItemDetailView,
    add_to_cart,
    remove_from_cart
)

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("checkout/", checkout, name="checkout"),
    path("product/<slug>/", ItemDetailView.as_view(), name="product"),
    path("add-to-cart/<slug>/", add_to_cart, name="add-to-cart"),
    path("remove-from-cart/<slug>/", remove_from_cart, name="remove-from-cart"),
]
