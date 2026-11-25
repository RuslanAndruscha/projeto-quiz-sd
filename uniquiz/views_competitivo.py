import random
import secrets
from datetime import timedelta

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Categoria,
    PartidaCompetitiva,
    Pergunta,
    PerguntaPartida,
    RespostaLog,
    SalaCompetitiva,
)
from .views import credencial_requerida

TOTAL_PERGUNTAS_1V1 = 10
TEMPO_LIMITE_PERGUNTA_1V1 = 15
JANELA_FILA_MINUTOS = 15
ALFABETO_CODIGO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def perguntas_elegiveis_1v1():
    """Retorna perguntas válidas para duelo (mínimo 2 alternativas e ao menos 1 correta)."""
    return (
        Pergunta.objects.annotate(
            total_alternativas=Count('alternativa', distinct=True),
            total_corretas=Count(
                'alternativa',
                filter=Q(alternativa__correta=True),
                distinct=True,
            ),
        )
        .filter(total_alternativas__gte=2, total_corretas__gte=1)
    )


def gerar_codigo_sala():
    """Gera um código curto e único para convidar outro aluno (ex.: UQ-7K4M)."""
    for _ in range(30):
        sufixo = ''.join(secrets.choice(ALFABETO_CODIGO) for _ in range(4))
        codigo = f'UQ-{sufixo}'
        if not SalaCompetitiva.objects.filter(codigo=codigo).exists():
            return codigo
    return f'UQ-{secrets.token_hex(3).upper()}'


def nome_exibicao_usuario(usuario):
    if usuario is None:
        return 'Aguardando oponente...'
    nome = f'{usuario.first_name} {usuario.last_name}'.strip()
    return nome or usuario.username


def sortear_e_vincular_perguntas(partida):
    """
    Sorteia até 10 perguntas elegíveis e fixa a mesma ordem para ambos os jogadores.
    Se a categoria escolhida tiver menos de 10 questões, adapta para o máximo disponível.
    """
    qs = perguntas_elegiveis_1v1()
    if partida.categoria_id is not None:
        qs = qs.filter(categoria_id=partida.categoria_id)

    ids_disponiveis = list(qs.values_list('id', flat=True))
    if not ids_disponiveis:
        return 0

    quantidade = min(TOTAL_PERGUNTAS_1V1, len(ids_disponiveis))
    selecionados = random.sample(ids_disponiveis, quantidade)

    PerguntaPartida.objects.filter(partida=partida).delete()
    PerguntaPartida.objects.bulk_create([
        PerguntaPartida(partida=partida, pergunta_id=pid, ordem=ordem)
        for ordem, pid in enumerate(selecionados, start=1)
    ])

    SalaCompetitiva.objects.filter(partida=partida).update(total_perguntas=quantidade)
    return quantidade


def calcular_resultado_1v1(partida, logs=None, motivo=None, vencedor_forcado_id=None):
    """
    Aplica oficialmente as regras da Parte 4:
      - Desconexão: vitória automática para quem permaneceu conectado.
      - 1º Critério: maior número de acertos.
      - 2º Critério (Desempate): menor tempo acumulado nas perguntas que acertou.
    """
    if logs is None:
        logs = list(
            RespostaLog.objects.filter(partida_competitiva=partida)
            .select_related('pergunta')
        )

    jogadores = {}
    for jogador in (partida.jogador1, partida.jogador2):
        if jogador is not None:
            uid = str(jogador.id)
            jogadores[uid] = {
                'id': uid,
                'nome': nome_exibicao_usuario(jogador),
                'acertos': 0,
                'erros': 0,
                'tempo_corretas': 0.0,
                'tempo_total': 0.0,
                'pontos': 0,
            }

    for log in logs:
        uid = str(log.usuario_id)
        if uid not in jogadores:
            continue
        tempo = float(log.tempo_resposta_segundos)
        jogadores[uid]['tempo_total'] += tempo
        if log.acertou:
            jogadores[uid]['acertos'] += 1
            jogadores[uid]['tempo_corretas'] += tempo
            jogadores[uid]['pontos'] += int(log.pergunta.pontuacao)
        else:
            jogadores[uid]['erros'] += 1

    for stats in jogadores.values():
        stats['tempo_corretas'] = round(stats['tempo_corretas'], 2)
        stats['tempo_total'] = round(stats['tempo_total'], 2)

    j1_id = str(partida.jogador1_id) if partida.jogador1_id else None
    j2_id = str(partida.jogador2_id) if partida.jogador2_id else None

    vencedor_id = None
    criterio = 'empate'

    if motivo == 'desconexao' and vencedor_forcado_id:
        vencedor_id = str(vencedor_forcado_id)
        criterio = 'desconexao'
    elif j1_id and j2_id:
        s1 = jogadores[j1_id]
        s2 = jogadores[j2_id]

        if s1['acertos'] > s2['acertos']:
            vencedor_id = j1_id
            criterio = 'acertos'
        elif s2['acertos'] > s1['acertos']:
            vencedor_id = j2_id
            criterio = 'acertos'
        elif s1['acertos'] > 0:
            if s1['tempo_corretas'] < s2['tempo_corretas']:
                vencedor_id = j1_id
                criterio = 'tempo_desempate'
            elif s2['tempo_corretas'] < s1['tempo_corretas']:
                vencedor_id = j2_id
                criterio = 'tempo_desempate'
            else:
                vencedor_id = None
                criterio = 'empate'
        else:
            vencedor_id = None
            criterio = 'empate'

    return {
        'vencedor_id': vencedor_id,
        'criterio': criterio,
        'motivo': motivo or 'normal',
        'jogadores': jogadores,
    }


def montar_payload_resultado(partida):
    """Monta o resumo completo (placar + revisão) de uma partida finalizada."""
    sala = SalaCompetitiva.objects.filter(partida=partida).first()
    motivo = sala.motivo_encerramento if sala else 'normal'

    logs = list(
        RespostaLog.objects.filter(partida_competitiva=partida)
        .select_related('pergunta', 'pergunta__categoria')
        .order_by('id')
    )
    resultado = calcular_resultado_1v1(
        partida,
        logs=logs,
        motivo=motivo,
        vencedor_forcado_id=partida.vencedor_id if motivo == 'desconexao' else None,
    )

    if partida.vencedor_id and not resultado['vencedor_id']:
        resultado['vencedor_id'] = str(partida.vencedor_id)

    logs_por_pergunta_usuario = {
        (log.pergunta_id, str(log.usuario_id)): log
        for log in logs
    }

    perguntas_vinculadas = list(
        PerguntaPartida.objects.filter(partida=partida)
        .select_related('pergunta', 'pergunta__categoria')
        .prefetch_related('pergunta__alternativa_set')
        .order_by('ordem')
    )

    j1_id = str(partida.jogador1_id)
    j2_id = str(partida.jogador2_id) if partida.jogador2_id else None

    revisao = []
    for item in perguntas_vinculadas:
        correta = next(
            (alt.texto for alt in item.pergunta.alternativa_set.all() if alt.correta),
            '—',
        )
        log_j1 = logs_por_pergunta_usuario.get((item.pergunta_id, j1_id))
        log_j2 = logs_por_pergunta_usuario.get((item.pergunta_id, j2_id)) if j2_id else None
        revisao.append({
            'ordem': item.ordem,
            'categoria': item.pergunta.categoria.nome,
            'texto': item.pergunta.texto_pergunta,
            'correta': correta,
            'j1': {
                'acertou': bool(log_j1.acertou) if log_j1 else False,
                'tempo': round(log_j1.tempo_resposta_segundos, 2) if log_j1 else None,
                'respondeu': log_j1 is not None,
            },
            'j2': {
                'acertou': bool(log_j2.acertou) if log_j2 else False,
                'tempo': round(log_j2.tempo_resposta_segundos, 2) if log_j2 else None,
                'respondeu': log_j2 is not None,
            },
        })

    vencedor_nome = None
    if resultado['vencedor_id'] and resultado['vencedor_id'] in resultado['jogadores']:
        vencedor_nome = resultado['jogadores'][resultado['vencedor_id']]['nome']

    return {
        'partida_id': partida.id,
        'motivo': resultado['motivo'],
        'criterio': resultado['criterio'],
        'vencedor_id': resultado['vencedor_id'],
        'vencedor_nome': vencedor_nome,
        'jogador1': resultado['jogadores'].get(j1_id),
        'jogador2': resultado['jogadores'].get(j2_id) if j2_id else None,
        'revisao': revisao,
    }


def _cancelar_salas_aguardando_do_usuario(usuario):
    """Encerra salas antigas que o próprio usuário deixou aguardando sem oponente."""
    partidas_antigas = list(
        PartidaCompetitiva.objects.select_for_update()
        .filter(jogador1=usuario, jogador2__isnull=True, status='aguardando')
        .values_list('id', flat=True)
    )
    if partidas_antigas:
        PartidaCompetitiva.objects.filter(id__in=partidas_antigas).update(status='cancelada')
        SalaCompetitiva.objects.filter(partida_id__in=partidas_antigas).update(
            motivo_encerramento='cancelada'
        )


def _obter_categoria_opcional(categoria_raw):
    if not categoria_raw:
        return None, True
    try:
        cat_id = int(categoria_raw)
    except ValueError:
        return None, False
    categoria = Categoria.objects.filter(pk=cat_id).first()
    if categoria is None:
        return None, False
    return categoria, True


@credencial_requerida(1)
def modo_competitivo(request):
    perguntas_validas = perguntas_elegiveis_1v1()
    total_perguntas_geral = perguntas_validas.count()

    categorias_qs = (
        Categoria.objects.filter(pergunta__in=perguntas_validas)
        .annotate(total_perguntas=Count('pergunta', distinct=True))
        .order_by('nome')
    )
    categorias_disponiveis = [
        {
            'id': cat.id,
            'nome': cat.nome,
            'total_perguntas': cat.total_perguntas,
            'qtd_partida': min(TOTAL_PERGUNTAS_1V1, cat.total_perguntas),
        }
        for cat in categorias_qs
    ]

    partida_ativa = (
        PartidaCompetitiva.objects.filter(
            Q(jogador1=request.user) | Q(jogador2=request.user),
            status__in=['aguardando', 'em_andamento'],
        )
        .select_related('categoria', 'jogador1', 'jogador2')
        .order_by('-data_criacao')
        .first()
    )

    historico_qs = (
        PartidaCompetitiva.objects.filter(
            Q(jogador1=request.user) | Q(jogador2=request.user),
            status='finalizada',
        )
        .select_related('categoria', 'jogador1', 'jogador2', 'vencedor', 'sala')
        .order_by('-data_criacao')[:8]
    )

    vitorias_total = PartidaCompetitiva.objects.filter(
        vencedor=request.user,
        status='finalizada',
    ).count()

    historico = []
    for partida in historico_qs:
        oponente = partida.jogador2 if partida.jogador1_id == request.user.id else partida.jogador1
        if partida.vencedor_id is None:
            desfecho = 'empate'
        elif partida.vencedor_id == request.user.id:
            desfecho = 'vitoria'
        else:
            desfecho = 'derrota'

        sala = getattr(partida, 'sala', None)
        historico.append({
            'id': partida.id,
            'data_criacao': partida.data_criacao,
            'categoria': partida.categoria.nome if partida.categoria else 'Modo Geral',
            'oponente': nome_exibicao_usuario(oponente),
            'desfecho': desfecho,
            'motivo': sala.motivo_encerramento if sala else 'normal',
        })

    context = {
        'categorias_disponiveis': categorias_disponiveis,
        'total_perguntas_geral': total_perguntas_geral,
        'qtd_modo_geral': min(TOTAL_PERGUNTAS_1V1, total_perguntas_geral),
        'tempo_limite': TEMPO_LIMITE_PERGUNTA_1V1,
        'partida_ativa': partida_ativa,
        'vitorias_total': vitorias_total,
        'historico': historico,
    }
    return render(request, 'uniquiz/modo-competitivo.html', context)


@require_POST
@credencial_requerida(1)
def buscar_partida(request):
    categoria, valido = _obter_categoria_opcional(request.POST.get('categoria', '').strip())
    if not valido:
        messages.error(request, 'Categoria selecionada inválida.')
        return redirect('uniquiz:modo-competitivo')

    qs_elegiveis = perguntas_elegiveis_1v1()
    if categoria is not None:
        qs_elegiveis = qs_elegiveis.filter(categoria=categoria)

    total_disponivel = qs_elegiveis.count()
    if total_disponivel == 0:
        messages.warning(request, 'Nenhuma pergunta disponível para o tema selecionado.')
        return redirect('uniquiz:modo-competitivo')

    limite_fila = timezone.now() - timedelta(minutes=JANELA_FILA_MINUTOS)

    try:
        with transaction.atomic():
            _cancelar_salas_aguardando_do_usuario(request.user)

            filtro_sala = Q(
                privada=False,
                partida__status='aguardando',
                partida__jogador2__isnull=True,
                partida__data_criacao__gte=limite_fila,
            )
            if categoria is None:
                filtro_sala &= Q(partida__categoria__isnull=True)
            else:
                filtro_sala &= Q(partida__categoria=categoria)

            sala_aberta = (
                SalaCompetitiva.objects.select_for_update()
                .select_related('partida')
                .filter(filtro_sala)
                .exclude(partida__jogador1=request.user)
                .order_by('partida__data_criacao')
                .first()
            )

            if sala_aberta is not None:
                partida = sala_aberta.partida
                partida.jogador2 = request.user
                partida.status = 'em_andamento'
                partida.save(update_fields=['jogador2', 'status'])

                qtd = sortear_e_vincular_perguntas(partida)
                if qtd == 0:
                    raise DatabaseError('Sem perguntas elegíveis ao iniciar partida.')
            else:
                partida = PartidaCompetitiva.objects.create(
                    jogador1=request.user,
                    categoria=categoria,
                    status='aguardando',
                )
                SalaCompetitiva.objects.create(
                    partida=partida,
                    codigo=gerar_codigo_sala(),
                    privada=False,
                    total_perguntas=min(TOTAL_PERGUNTAS_1V1, total_disponivel),
                    tempo_limite_segundos=TEMPO_LIMITE_PERGUNTA_1V1,
                )
    except DatabaseError:
        messages.error(request, 'Não foi possível iniciar a busca por partida. Tente novamente.')
        return redirect('uniquiz:modo-competitivo')

    return redirect('uniquiz:sala-partida-1v1', partida_id=partida.id)


@require_POST
@credencial_requerida(1)
def criar_sala_privada(request):
    categoria, valido = _obter_categoria_opcional(request.POST.get('categoria', '').strip())
    if not valido:
        messages.error(request, 'Categoria selecionada inválida.')
        return redirect('uniquiz:modo-competitivo')

    qs_elegiveis = perguntas_elegiveis_1v1()
    if categoria is not None:
        qs_elegiveis = qs_elegiveis.filter(categoria=categoria)

    total_disponivel = qs_elegiveis.count()
    if total_disponivel == 0:
        messages.warning(request, 'Nenhuma pergunta disponível para o tema selecionado.')
        return redirect('uniquiz:modo-competitivo')

    try:
        with transaction.atomic():
            _cancelar_salas_aguardando_do_usuario(request.user)

            partida = PartidaCompetitiva.objects.create(
                jogador1=request.user,
                categoria=categoria,
                status='aguardando',
            )
            SalaCompetitiva.objects.create(
                partida=partida,
                codigo=gerar_codigo_sala(),
                privada=True,
                total_perguntas=min(TOTAL_PERGUNTAS_1V1, total_disponivel),
                tempo_limite_segundos=TEMPO_LIMITE_PERGUNTA_1V1,
            )
    except DatabaseError:
        messages.error(request, 'Não foi possível criar a sala privada. Tente novamente.')
        return redirect('uniquiz:modo-competitivo')

    return redirect('uniquiz:sala-partida-1v1', partida_id=partida.id)


@require_POST
@credencial_requerida(1)
def entrar_por_codigo(request):
    codigo = request.POST.get('codigo', '').strip().upper()
    if not codigo:
        messages.error(request, 'Informe o código da sala para entrar no duelo.')
        return redirect('uniquiz:modo-competitivo')

    if not codigo.startswith('UQ-') and len(codigo) == 4:
        codigo = f'UQ-{codigo}'

    try:
        with transaction.atomic():
            sala = (
                SalaCompetitiva.objects.select_for_update()
                .select_related('partida')
                .filter(codigo__iexact=codigo)
                .first()
            )
            if sala is None:
                messages.error(request, 'Código de sala não encontrado.')
                return redirect('uniquiz:modo-competitivo')

            partida = sala.partida
            if partida.jogador1_id == request.user.id:
                messages.warning(request, 'Você já é o criador desta sala. Compartilhe o código com um colega.')
                return redirect('uniquiz:sala-partida-1v1', partida_id=partida.id)

            if partida.status != 'aguardando' or partida.jogador2_id is not None:
                messages.error(request, 'Esta sala não está mais disponível para entrada.')
                return redirect('uniquiz:modo-competitivo')

            _cancelar_salas_aguardando_do_usuario(request.user)

            partida.jogador2 = request.user
            partida.status = 'em_andamento'
            partida.save(update_fields=['jogador2', 'status'])

            qtd = sortear_e_vincular_perguntas(partida)
            if qtd == 0:
                raise DatabaseError('Nenhuma pergunta disponível para esta sala.')
    except DatabaseError:
        messages.error(request, 'Não foi possível entrar na sala. Tente novamente.')
        return redirect('uniquiz:modo-competitivo')

    return redirect('uniquiz:sala-partida-1v1', partida_id=partida.id)


@credencial_requerida(1)
def sala_partida_1v1(request, partida_id):
    partida = get_object_or_404(
        PartidaCompetitiva.objects.select_related('categoria', 'jogador1', 'jogador2', 'vencedor'),
        pk=partida_id,
    )
    if request.user.id not in (partida.jogador1_id, partida.jogador2_id):
        return HttpResponseForbidden('Você não participa desta partida competitiva.')

    if partida.status == 'cancelada':
        messages.info(request, 'Esta partida foi cancelada antes de começar.')
        return redirect('uniquiz:modo-competitivo')

    sala = SalaCompetitiva.objects.filter(partida=partida).first()
    resultado_final = montar_payload_resultado(partida) if partida.status == 'finalizada' else None

    context = {
        'partida': partida,
        'sala': sala,
        'usuario_id_str': str(request.user.id),
        'jogador1_nome': nome_exibicao_usuario(partida.jogador1),
        'jogador2_nome': nome_exibicao_usuario(partida.jogador2),
        'categoria_nome': partida.categoria.nome if partida.categoria else 'Modo Geral',
        'total_perguntas': sala.total_perguntas if sala else TOTAL_PERGUNTAS_1V1,
        'tempo_limite': sala.tempo_limite_segundos if sala else TEMPO_LIMITE_PERGUNTA_1V1,
        'resultado_final': resultado_final,
    }
    return render(request, 'uniquiz/partida-1v1.html', context)


@require_POST
@credencial_requerida(1)
def cancelar_partida_1v1(request, partida_id):
    try:
        with transaction.atomic():
            partida = (
                PartidaCompetitiva.objects.select_for_update()
                .filter(pk=partida_id)
                .first()
            )
            if partida is None:
                return redirect('uniquiz:modo-competitivo')

            if partida.jogador1_id != request.user.id:
                return HttpResponseForbidden('Apenas o criador pode cancelar a sala aguardando.')

            if partida.status == 'aguardando' and partida.jogador2_id is None:
                partida.status = 'cancelada'
                partida.save(update_fields=['status'])
                SalaCompetitiva.objects.filter(partida=partida).update(
                    motivo_encerramento='cancelada'
                )
                messages.info(request, 'Busca/sala cancelada com sucesso.')
            else:
                return redirect('uniquiz:sala-partida-1v1', partida_id=partida.id)
    except DatabaseError:
        messages.error(request, 'Erro ao cancelar a sala. Tente novamente.')
        return redirect('uniquiz:sala-partida-1v1', partida_id=partida_id)

    return redirect('uniquiz:modo-competitivo')