from django.contrib import admin

from .models import Pergunta, Alternativa, Categoria
# Register your models here.

admin.site.register(Pergunta)
admin. site.register(Alternativa)
admin. site.register(Categoria)