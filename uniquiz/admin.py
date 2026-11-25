from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import Pergunta, Alternativa, Categoria, Usuario, SessaoIndividual, PartidaCompetitiva, RespostaLog

class AlternativaInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        total_corretas = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            if form.cleaned_data.get('correta'):
                total_corretas += 1

        if total_corretas == 0:
            raise ValidationError('Marque exatamente uma alternativa como correta (nenhuma foi marcada).')
        if total_corretas > 1:
            raise ValidationError('Marque apenas uma alternativa como correta (mais de uma foi marcada).')


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    formset = AlternativaInlineFormSet
    extra = 0
    min_num = 4
    max_num = 4

class PerguntaAdmin(admin.ModelAdmin):
    inlines = [AlternativaInline]
    list_display = ('texto_pergunta', 'categoria', 'autor', 'nivel', 'pontuacao')
    list_filter = ('categoria', 'nivel', 'autor')


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

