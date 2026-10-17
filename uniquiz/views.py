from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def home(request):
    return HttpResponse('Página principal.')

def login(request):
    return HttpResponse('Página de Login.')

def cadastro(request):
    return HttpResponse('Página de Cadastro.')