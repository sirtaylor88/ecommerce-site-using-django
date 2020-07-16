from django.shortcuts import render
from .models import Item

# Create your views here.
def home(request):
    template = "home.html"
    context = {
        "items": Item.objects.all()
    }
    return render(request, template, context)

def checkout(request):
    template = "checkout.html"
    return render(request, template)

def products(request):
    template = "products.html"
    context = {
        "items": Item.objects.all()
    }
    return render(request, template, context)
