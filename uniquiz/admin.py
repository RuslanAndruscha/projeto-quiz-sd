from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Pergunta, Alternativa, Categoria, Usuario, SessaoIndividual, PartidaCompetitiva, RespostaLog

class AlternativaInline(admin.TabularInline):
    model = Alternativa
    extra = 0
    min_num = 4
    max_num = 4 

class PerguntaAdmin(admin.ModelAdmin):
    inlines = [AlternativaInline]
    list_display = ('texto_pergunta', 'categoria', 'nivel', 'pontuacao')
    list_filter = ('categoria', 'nivel')


@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Informações do Jogo', {'fields': ('credencial', 'curso', 'pontuacao_total')}),
    )

admin.site.register(Pergunta, PerguntaAdmin)
admin.site.register(Alternativa)
admin.site.register(Categoria)
admin.site.register(SessaoIndividual)
admin.site.register(PartidaCompetitiva)
admin.site.register(RespostaLog)