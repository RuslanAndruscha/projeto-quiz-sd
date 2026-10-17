from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def home(request):
    return render(request, 'uniquiz/home.html')

def login(request):
    return render(request, 'uniquiz/login.html')

def cadastro(request):
    return render(request , 'uniquiz/cadastro.html')