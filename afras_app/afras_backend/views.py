# In your views.py
from django.shortcuts import render

def home(request):
    return render(request, 'home.html')  # Should match your template path