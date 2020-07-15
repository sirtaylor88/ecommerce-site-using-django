from django.urls import path
from django.views.generic import TemplateView
from .views import (
    item_list
)

app_name = "core"

urlpatterns = [
    path("", item_list, name="item-index"),
    path("checkout/", TemplateView.as_view(template_name='checkout-page.html'), name="order-checkout"),
]
