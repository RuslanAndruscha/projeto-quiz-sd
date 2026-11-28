from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import Pergunta, Alternativa, Categoria, Usuario, SessaoIndividual, PartidaCompetitiva, RespostaLog

MIN_ALTERNATIVAS = 4
MAX_ALTERNATIVAS = 4
MAX_ALTERNATIVAS_CORRETAS = 1

class AlternativaInlineFormSet(BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        total_corretas = 0
        total_alternativas = 0

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            if form.cleaned_data.get('correta'):
                total_corretas += 1

            total_alternativas += 1
        if total_corretas != MAX_ALTERNATIVAS_CORRETAS:
            raise ValidationError(f'Marque exatamente {MAX_ALTERNATIVAS_CORRETAS} alternativa(s) como correta(s).')
        if total_alternativas < MIN_ALTERNATIVAS or total_alternativas > MAX_ALTERNATIVAS:
            if MIN_ALTERNATIVAS == MAX_ALTERNATIVAS:
                mensagem = f'A pergunta deve ter exatamente {MIN_ALTERNATIVAS} alternativas.'
            else:
                mensagem = (f'A pergunta deve ter entre {MIN_ALTERNATIVAS} e ' f'{MAX_ALTERNATIVAS} alternativas.')
            raise ValidationError(mensagem)


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    formset = AlternativaInlineFormSet
    extra = 0
    min_num = MIN_ALTERNATIVAS
    max_num = MAX_ALTERNATIVAS + 1 # Permite 5 alternativas durante a edicao apenas

class PerguntaAdmin(admin.ModelAdmin):
    inlines = [AlternativaInline]
    list_display = ('texto_pergunta', 'categoria', 'autor', 'nivel', 'pontuacao')
    list_filter = ('categoria', 'nivel', 'autor')

    class Media:
        js = ('uniquiz/admin_alternativas.js',)
        css = {'all': ('uniquiz/admin_alternativas.css',)}


@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    list_filter = ('credencial',) + UserAdmin.list_filter
    fieldsets = UserAdmin.fieldsets + (
        ('Informações do Jogo', {'fields': ('credencial', 'curso', 'pontuacao_total')}),
    )

admin.site.register(Pergunta, PerguntaAdmin)
admin.site.register(Alternativa)
admin.site.register(Categoria)
admin.site.register(SessaoIndividual)
admin.site.register(PartidaCompetitiva)
admin.site.register(RespostaLog)

