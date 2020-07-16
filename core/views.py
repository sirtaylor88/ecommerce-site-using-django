from django.shortcuts import render
from django.views.generic import ListView, DetailView
from .models import Item

# Create your views here.
class HomeView(ListView):
    model = Item
    template_name = "home.html"

class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"

def checkout(request):
    template = "checkout.html"
    return render(request, template)

def products(request):
    template = "products.html"
    context = {
        "items": Item.objects.all()
    }
    return render(request, template, context)
