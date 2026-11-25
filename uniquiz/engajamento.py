import random
from django.db.models import Count, Q

from .models import Categoria, RespostaLog, Usuario

JANELA_RECENTE_POR_CATEGORIA = 10
BONUS_VITORIA_1V1 = 50


def calcular_pesos_categorias(usuario, janela_por_categoria=JANELA_RECENTE_POR_CATEGORIA):
    """
    Calcula o peso de priorizacao de cada categoria com base no historico recente do aluno.
    Categorias com maior taxa de erro recente recebem peso maior (de 1.0 ate 4.0).
    """
    if usuario is None or not getattr(usuario, 'is_authenticated', False):
        return {}

    logs = (
        RespostaLog.objects.filter(usuario=usuario)
        .values_list('pergunta__categoria_id', 'acertou')
        .order_by('-id')
    )

    historico_recente = {}
    for categoria_id, acertou in logs:
        if categoria_id is None:
            continue
        lista = historico_recente.setdefault(categoria_id, [])
        if len(lista) < janela_por_categoria:
            lista.append(bool(acertou))

    pesos = {}
    for categoria_id, respostas in historico_recente.items():
        total = len(respostas)
        if total == 0:
            pesos[categoria_id] = 1.0
            continue
        erros = sum(1 for acertou in respostas if not acertou)
        taxa_erro = erros / total
        pesos[categoria_id] = round(1.0 + (taxa_erro * 3.0), 4)

    return pesos


def escolher_candidato_priorizado(candidatos, usuario=None, janela_por_categoria=JANELA_RECENTE_POR_CATEGORIA):
    """
    Recebe lista de tuplas (pergunta_id, nivel, categoria_id).
    Quando ha mais de uma categoria disponivel (Modo Geral), sorteia primeiro a categoria
    com probabilidade proporcional a taxa de erros recentes do aluno, depois sorteia a pergunta.
    """
    if not candidatos:
        return None

    if usuario is None or not getattr(usuario, 'is_authenticated', False):
        return random.choice(candidatos)

    por_categoria = {}
    for item in candidatos:
        cat_id = item[2]
        por_categoria.setdefault(cat_id, []).append(item)

    if len(por_categoria) <= 1:
        return random.choice(candidatos)

    pesos_por_categoria = calcular_pesos_categorias(
        usuario=usuario,
        janela_por_categoria=janela_por_categoria,
    )
    categorias_ids = list(por_categoria.keys())
    pesos = [pesos_por_categoria.get(cid, 1.0) for cid in categorias_ids]

    categoria_escolhida = random.choices(categorias_ids, weights=pesos, k=1)[0]
    return random.choice(por_categoria[categoria_escolhida])


def obter_estatisticas_categorias(usuario, janela_por_categoria=JANELA_RECENTE_POR_CATEGORIA):
    """
    Retorna a taxa de acerto/erro recente e o nivel de prioridade por categoria
    para exibicao no painel de desempenho do aluno.
    """
    categorias = list(
        Categoria.objects.annotate(total_perguntas=Count('pergunta', distinct=True))
        .filter(total_perguntas__gt=0)
        .order_by('nome')
    )

    logs = (
        RespostaLog.objects.filter(usuario=usuario)
        .values_list('pergunta__categoria_id', 'acertou')
        .order_by('-id')
    )

    recente_por_cat = {}
    for categoria_id, acertou in logs:
        if categoria_id is None:
            continue
        lista = recente_por_cat.setdefault(categoria_id, [])
        if len(lista) < janela_por_categoria:
            lista.append(bool(acertou))

    estatisticas = []
    for cat in categorias:
        respostas = recente_por_cat.get(cat.id, [])
        total = len(respostas)
        acertos = sum(1 for a in respostas if a)
        erros = total - acertos

        if total > 0:
            taxa_acerto = round((acertos / total) * 100)
            taxa_erro = 100 - taxa_acerto
            peso = round(1.0 + ((erros / total) * 3.0), 2)
            if taxa_erro >= 50:
                prioridade_label = 'Alta prioridade na revisão'
                prioridade_classe = 'alta'
            elif taxa_erro >= 25:
                prioridade_label = 'Prioridade média'
                prioridade_classe = 'media'
            else:
                prioridade_label = 'Bom desempenho'
                prioridade_classe = 'baixa'
        else:
            taxa_acerto = 0
            taxa_erro = 0
            peso = 1.0
            prioridade_label = 'Sem histórico recente'
            prioridade_classe = 'neutro'

        estatisticas.append({
            'categoria_id': cat.id,
            'nome': cat.nome,
            'total_recente': total,
            'acertos': acertos,
            'erros': erros,
            'taxa_acerto': taxa_acerto,
            'taxa_erro': taxa_erro,
            'peso': peso,
            'prioridade_label': prioridade_label,
            'prioridade_classe': prioridade_classe,
        })

    estatisticas.sort(key=lambda item: (-item['peso'], -item['erros'], item['nome'].lower()))
    return estatisticas


def obter_ranking_global(limite=50):
    """
    Calcula o ranking global dos alunos com base no total de pontos acumulados
    e no numero de vitorias no modo competitivo 1v1.
    """
    alunos = (
        Usuario.objects.filter(credencial=1)
        .annotate(
            vitorias_1v1=Count(
                'vitorias',
                filter=Q(vitorias__status='finalizada'),
                distinct=True,
            )
        )
    )

    ranking = []
    for aluno in alunos:
        pontos = int(aluno.pontuacao_total or 0)
        vitorias = int(aluno.vitorias_1v1 or 0)
        pontuacao_ranking = pontos + (vitorias * BONUS_VITORIA_1V1)
        nome = f"{aluno.first_name} {aluno.last_name}".strip() or aluno.username

        ranking.append({
            'usuario_id': str(aluno.id),
            'nome': nome,
            'username': aluno.username,
            'curso': aluno.curso or '—',
            'pontuacao_total': pontos,
            'vitorias_1v1': vitorias,
            'pontuacao_ranking': pontuacao_ranking,
        })

    ranking.sort(
        key=lambda item: (
            -item['pontuacao_ranking'],
            -item['vitorias_1v1'],
            -item['pontuacao_total'],
            item['nome'].lower(),
        )
    )

    for posicao, item in enumerate(ranking, start=1):
        item['posicao'] = posicao

    if limite is not None:
        return ranking[:limite]
    return ranking