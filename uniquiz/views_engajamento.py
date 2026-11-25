from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .engajamento import (
    BONUS_VITORIA_1V1,
    JANELA_RECENTE_POR_CATEGORIA,
    obter_estatisticas_categorias,
    obter_ranking_global,
)


@login_required(login_url='uniquiz:login')
def ranking_global(request):
    ranking_completo = obter_ranking_global(limite=None)
    usuario_id_str = str(request.user.id)

    meu_resumo = next(
        (item for item in ranking_completo if item['usuario_id'] == usuario_id_str),
        None,
    )
    ranking_exibido = ranking_completo[:50]

    estatisticas_categorias = []
    if request.user.credencial == 1:
        estatisticas_categorias = obter_estatisticas_categorias(
            usuario=request.user,
            janela_por_categoria=JANELA_RECENTE_POR_CATEGORIA,
        )

    context = {
        'ranking': ranking_exibido,
        'total_alunos_ranking': len(ranking_completo),
        'meu_resumo': meu_resumo,
        'usuario_id_str': usuario_id_str,
        'bonus_vitoria_1v1': BONUS_VITORIA_1V1,
        'janela_recente': JANELA_RECENTE_POR_CATEGORIA,
        'estatisticas_categorias': estatisticas_categorias,
    }
    return render(request, 'uniquiz/ranking.html', context)