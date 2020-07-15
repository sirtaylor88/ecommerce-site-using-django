from django.shortcuts import render
from .models import Item

# Create your views here.
def item_list(request):
    template = "home-page.html"
    queryset = Item.objects.all()
    context = {
        "items": queryset
    }
    return render(request, template, context)
