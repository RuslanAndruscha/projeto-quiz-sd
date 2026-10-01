from django.contrib import admin
from .models import Pergunta, Alternativa, Categoria, Usuario


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    extra = 0


class PerguntaAdmin(admin.ModelAdmin):
    inlines = [AlternativaInline]


admin.site.register(Pergunta, PerguntaAdmin)
admin.site.register(Alternativa)
admin.site.register(Categoria)
admin.site.register(Usuario)