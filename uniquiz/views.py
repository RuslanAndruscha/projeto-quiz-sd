import random
import time
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import Alternativa, Categoria, Pergunta, RespostaLog, SessaoIndividual, Usuario

CATEGORIAS_PADRAO = [
    'Algoritmos',
    'Estruturas de Dados',
    'Hardware',
    'Matemática',
]


def _redirect_por_credencial(user):
    """Redireciona o usuário autenticado para a tela correspondente ao seu perfil."""
    if user.credencial == 2:
        return redirect('uniquiz:tela-professor')
    return redirect('uniquiz:tela-aluno')


def credencial_requerida(credencial_permitida):
    """Garante autenticação obrigatória, controle de cache e autorização por credencial."""
    def decorator(view_func):
        @never_cache
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, 'Faça login para acessar esta página.')
                login_url = reverse('uniquiz:login')
                if request.method == 'GET':
                    return redirect(f'{login_url}?next={request.get_full_path()}')
                return redirect(login_url)

            if request.user.credencial != credencial_permitida:
                if request.method != 'GET':
                    return HttpResponseForbidden('Acesso restrito ao perfil autorizado.')
                messages.error(request, 'Você não tem permissão para acessar esta área.')
                return _redirect_por_credencial(request.user)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def home(request):
    return render(request, 'uniquiz/home.html')


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return _redirect_por_credencial(request.user)

    if request.method == 'POST':
        identificador = request.POST.get('username', '').strip()
        senha = request.POST.get('password', '')
        next_url = request.POST.get('next') or request.GET.get('next') or ''

        if not identificador or not senha:
            messages.error(request, 'Informe seu e-mail e sua senha.')
            return render(request, 'uniquiz/login.html', {'email_digitado': identificador})

        usuario_alvo = (
            Usuario.objects.filter(email__iexact=identificador).first()
            or Usuario.objects.filter(username__iexact=identificador).first()
        )

        user = None
        if usuario_alvo is not None:
            user = authenticate(request, username=usuario_alvo.username, password=senha)

        if user is not None:
            auth_login(request, user)

            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                rota_aluno = reverse('uniquiz:tela-aluno')
                rota_professor = reverse('uniquiz:tela-professor')
                if (user.credencial == 1 and next_url.startswith(rota_aluno)) or (
                    user.credencial == 2 and next_url.startswith(rota_professor)
                ):
                    return redirect(next_url)

            return _redirect_por_credencial(user)

        messages.error(request, 'E-mail ou senha inválidos.')
        return render(request, 'uniquiz/login.html', {'email_digitado': identificador})

    return render(request, 'uniquiz/login.html')


@require_POST
@never_cache
def logout_view(request):
    auth_logout(request)
    messages.success(request, 'Você saiu da sua conta com segurança.')
    return redirect('uniquiz:login')


@never_cache
def cadastro(request):
    if request.user.is_authenticated:
        return _redirect_por_credencial(request.user)

    if request.method == 'POST':
        primeiro_nome = request.POST.get('primeiro_nome', '').strip()
        ultimo_nome = request.POST.get('ultimo_nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        senha = request.POST.get('senha', '')
        confirmar_senha = request.POST.get('confirmar_senha', '')
        credencial_raw = request.POST.get('credencial', '').strip()

        form_data = {
            'primeiro_nome': primeiro_nome,
            'ultimo_nome': ultimo_nome,
            'email': email,
            'credencial': credencial_raw,
        }

        if not all([primeiro_nome, ultimo_nome, email, senha, confirmar_senha, credencial_raw]):
            messages.error(request, 'Preencha todos os campos obrigatórios.')
            return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Informe um endereço de e-mail válido.')
            return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})

        if len(senha) < 8:
            messages.error(request, 'A senha deve conter no mínimo 8 caracteres.')
            return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})

        if senha != confirmar_senha:
            messages.error(request, 'As senhas informadas não coincidem.')
            return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})

        if credencial_raw not in ('1', '2'):
            messages.error(request, 'Selecione um perfil válido (Aluno ou Professor).')
            return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})

        credencial = int(credencial_raw)

        try:
            with transaction.atomic():
                if Usuario.objects.filter(
                    Q(email__iexact=email) | Q(username__iexact=email)
                ).exists():
                    messages.error(request, 'Já existe uma conta cadastrada com este e-mail.')
                    return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})

                Usuario.objects.create_user(
                    username=email,
                    email=email,
                    password=senha,
                    first_name=primeiro_nome,
                    last_name=ultimo_nome,
                    credencial=credencial,
                )
        except IntegrityError:
            messages.error(request, 'Não foi possível concluir o cadastro: e-mail já utilizado.')
            return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})
        except DatabaseError:
            messages.error(request, 'Erro interno ao salvar o cadastro. Tente novamente.')
            return render(request, 'uniquiz/cadastro.html', {'form_data': form_data})

        messages.success(request, 'Conta criada com sucesso! Faça login para acessar a plataforma.')
        return redirect('uniquiz:login')

    return render(request, 'uniquiz/cadastro.html')


@credencial_requerida(1)
def telaAluno(request):
    return render(request, 'uniquiz/tela-aluno.html')


def _perguntas_elegiveis():
    """Retorna perguntas válidas para jogo (ao menos 2 alternativas e ao menos 1 correta)."""
    return (
        Pergunta.objects.annotate(
            total_alternativas=Count('alternativa', distinct=True),
            total_corretas=Count('alternativa', filter=Q(alternativa__correta=True), distinct=True),
        )
        .filter(total_alternativas__gte=2, total_corretas__gte=1)
    )


def _sortear_proxima_pergunta(categoria_id, nivel_atual, respondidas_ids, apenas_nivel_exato=False):
    """Sorteia uma pergunta elegível não respondida respeitando a categoria e a progressão de nível."""
    base_qs = _perguntas_elegiveis().exclude(id__in=respondidas_ids)
    if categoria_id is not None:
        base_qs = base_qs.filter(categoria_id=categoria_id)

    nivel_seguro = max(1, min(int(nivel_atual or 1), 3))

    if apenas_nivel_exato:
        # No início da partida, força obrigatoriamente o Nível 1
        niveis_alvo = [nivel_seguro]
    else:
        # Após acertar, a próxima pergunta vem do nível atual ou de um nível acima (até 3)
        proximo_nivel = min(nivel_seguro + 1, 3)
        niveis_alvo = [nivel_seguro] if proximo_nivel == nivel_seguro else [nivel_seguro, proximo_nivel]

    candidatos = list(base_qs.filter(nivel__in=niveis_alvo).values_list('id', 'nivel'))

    if not candidatos:
        # Fallback: busca qualquer pergunta restante no tema/modo caso o nível alvo não tenha perguntas
        candidatos = list(base_qs.values_list('id', 'nivel'))

    if not candidatos:
        return None, nivel_seguro

    pergunta_id, nivel_sorteado = random.choice(candidatos)
    pergunta = (
        Pergunta.objects.select_related('categoria', 'autor')
        .prefetch_related('alternativa_set')
        .filter(pk=pergunta_id)
        .first()
    )
    return pergunta, nivel_sorteado


@credencial_requerida(1)
def modo_individual(request):
    perguntas_validas = _perguntas_elegiveis()
    total_perguntas_disponiveis = perguntas_validas.count()

    categorias_disponiveis = (
        Categoria.objects.filter(pergunta__in=perguntas_validas)
        .annotate(total_perguntas=Count('pergunta', distinct=True))
        .order_by('nome')
    )

    sessao_ativa = None
    estado_sessao = request.session.get('quiz_individual')
    if estado_sessao and estado_sessao.get('sessao_id'):
        sessao_ativa = (
            SessaoIndividual.objects.filter(
                pk=estado_sessao['sessao_id'],
                usuario=request.user,
                status='em_andamento',
            )
            .first()
        )

    historico_qs = (
        SessaoIndividual.objects.filter(usuario=request.user, status='finalizada')
        .annotate(
            total_respostas=Count('respostalog'),
            total_acertos=Count('respostalog', filter=Q(respostalog__acertou=True)),
        )
        .order_by('-data_inicio')[:5]
    )

    historico = []
    for item in historico_qs:
        taxa = round((item.total_acertos / item.total_respostas) * 100) if item.total_respostas else 0
        historico.append({
            'id': item.id,
            'data_inicio': item.data_inicio,
            'pontuacao_final': item.pontuacao_final,
            'total_acertos': item.total_acertos,
            'total_respostas': item.total_respostas,
            'taxa_acerto': taxa,
        })

    context = {
        'categorias_disponiveis': categorias_disponiveis,
        'total_perguntas_disponiveis': total_perguntas_disponiveis,
        'sessao_ativa': sessao_ativa,
        'historico': historico,
    }
    return render(request, 'uniquiz/modo-individual.html', context)


@require_POST
@credencial_requerida(1)
def iniciar_modo_individual(request):
    categoria_id_raw = request.POST.get('categoria', '').strip()
    categoria_id = None

    if categoria_id_raw:
        try:
            categoria_id = int(categoria_id_raw)
        except ValueError:
            messages.error(request, 'Categoria selecionada inválida.')
            return redirect('uniquiz:modo-individual')

        if not Categoria.objects.filter(pk=categoria_id).exists():
            messages.error(request, 'Categoria selecionada inválida.')
            return redirect('uniquiz:modo-individual')

    nivel_inicial = 1
    primeira_pergunta, nivel_sorteado = _sortear_proxima_pergunta(
        categoria_id=categoria_id,
        nivel_atual=nivel_inicial,
        respondidas_ids=[],
        apenas_nivel_exato=True,
    )

    if primeira_pergunta is None:
        messages.warning(
            request,
            'Nenhuma pergunta disponível para o tema selecionado.',
        )
        return redirect('uniquiz:modo-individual')

    try:
        with transaction.atomic():
            SessaoIndividual.objects.select_for_update().filter(
                usuario=request.user,
                status='em_andamento',
            ).update(status='abandonada')

            sessao = SessaoIndividual.objects.create(
                usuario=request.user,
                pontuacao_final=0,
                status='em_andamento',
            )
    except DatabaseError:
        messages.error(request, 'Não foi possível iniciar a sessão do quiz. Tente novamente.')
        return redirect('uniquiz:modo-individual')

    request.session['quiz_individual'] = {
        'sessao_id': sessao.id,
        'categoria_id': categoria_id,
        'nivel_atual': nivel_sorteado,
        'respondidas_ids': [],
        'pergunta_atual_id': primeira_pergunta.id,
        'pergunta_iniciada_em': time.time(),
        'game_over': False,
        'ultimo_feedback': None,
    }
    request.session.modified = True

    return redirect('uniquiz:jogar-individual', sessao_id=sessao.id)


@credencial_requerida(1)
def jogar_individual(request, sessao_id):
    sessao = get_object_or_404(SessaoIndividual, pk=sessao_id)
    if sessao.usuario_id != request.user.id:
        return HttpResponseForbidden('Você não tem permissão para acessar esta sessão.')

    if sessao.status == 'abandonada':
        messages.warning(request, 'Esta sessão foi encerrada antes de ser concluída.')
        return redirect('uniquiz:modo-individual')

    estado = request.session.get('quiz_individual')
    estado_valido = isinstance(estado, dict) and estado.get('sessao_id') == sessao.id

    # 1. Exibir feedback imediato da pergunta recém-respondida
    if estado_valido and estado.get('ultimo_feedback'):
        feedback = estado['ultimo_feedback']
        pergunta = get_object_or_404(
            Pergunta.objects.select_related('categoria', 'autor').prefetch_related('alternativa_set'),
            pk=feedback['pergunta_id'],
        )
        alternativas = list(pergunta.alternativa_set.all().order_by('id'))
        numero_atual = feedback.get('numero_atual', 1)

        context = {
            'modo': 'feedback',
            'sessao': sessao,
            'pergunta': pergunta,
            'alternativas': alternativas,
            'feedback': feedback,
            'game_over': bool(feedback.get('game_over')),
            'nivel_atual': estado.get('nivel_atual', 1),
            'numero_atual': numero_atual,
            'total_perguntas': numero_atual,
            'progresso_percentual': 100 if feedback.get('game_over') else 0,
        }
        return render(request, 'uniquiz/quiz-individual.html', context)

    # 2. Exibir resultado final quando a sessão foi concluída (ou Game Over)
    if sessao.status == 'finalizada':
        game_over = bool(estado_valido and estado.get('game_over'))
        if estado_valido:
            request.session.pop('quiz_individual', None)
            request.session.modified = True

        logs = list(
            RespostaLog.objects.filter(sessao_individual=sessao)
            .select_related('pergunta', 'pergunta__categoria')
            .prefetch_related('pergunta__alternativa_set')
            .order_by('id')
        )
        total_respostas = len(logs)
        total_acertos = sum(1 for log in logs if log.acertou)
        total_erros = total_respostas - total_acertos
        if not game_over and total_erros > 0:
            game_over = True

        taxa_acerto = round((total_acertos / total_respostas) * 100) if total_respostas else 0
        tempo_medio = (
            round(sum(log.tempo_resposta_segundos for log in logs) / total_respostas, 1)
            if total_respostas
            else 0.0
        )

        revisao = []
        for idx, log in enumerate(logs, start=1):
            correta = next(
                (alt.texto for alt in log.pergunta.alternativa_set.all() if alt.correta),
                '—',
            )
            revisao.append({
                'numero': idx,
                'pergunta': log.pergunta,
                'acertou': log.acertou,
                'tempo': round(log.tempo_resposta_segundos, 1),
                'resposta_correta': correta,
            })

        context = {
            'modo': 'resultado',
            'sessao': sessao,
            'game_over': game_over,
            'pontuacao_acumulada_perfil': request.user.pontuacao_total,
            'total_respostas': total_respostas,
            'total_acertos': total_acertos,
            'total_erros': total_erros,
            'taxa_acerto': taxa_acerto,
            'tempo_medio': tempo_medio,
            'revisao': revisao,
        }
        return render(request, 'uniquiz/quiz-individual.html', context)

    # 3. Sessão em andamento: carregar pergunta atual ou sortear a próxima dinamicamente
    if not estado_valido:
        with transaction.atomic():
            sessao_lock = SessaoIndividual.objects.select_for_update().get(pk=sessao.pk)
            if RespostaLog.objects.filter(sessao_individual=sessao_lock).exists():
                sessao_lock.status = 'finalizada'
            else:
                sessao_lock.status = 'abandonada'
            sessao_lock.save()
        return redirect('uniquiz:jogar-individual', sessao_id=sessao.id)

    respondidas_ids = list(
        RespostaLog.objects.filter(sessao_individual=sessao).values_list('pergunta_id', flat=True)
    )
    categoria_id = estado.get('categoria_id')
    nivel_atual = estado.get('nivel_atual', 1)
    pergunta_atual_id = estado.get('pergunta_atual_id')

    pergunta = None
    if pergunta_atual_id and pergunta_atual_id not in respondidas_ids:
        pergunta = (
            Pergunta.objects.select_related('categoria', 'autor')
            .prefetch_related('alternativa_set')
            .filter(pk=pergunta_atual_id)
            .first()
        )

    if pergunta is None:
        pergunta, nivel_sorteado = _sortear_proxima_pergunta(
            categoria_id=categoria_id,
            nivel_atual=nivel_atual,
            respondidas_ids=respondidas_ids,
        )
        if pergunta is None:
            with transaction.atomic():
                SessaoIndividual.objects.select_for_update().filter(
                    pk=sessao.pk
                ).update(status='finalizada')
            return redirect('uniquiz:jogar-individual', sessao_id=sessao.id)

        estado['nivel_atual'] = nivel_sorteado
        estado['pergunta_atual_id'] = pergunta.id
        estado['pergunta_iniciada_em'] = time.time()
        request.session.modified = True
    elif not estado.get('pergunta_iniciada_em'):
        estado['pergunta_iniciada_em'] = time.time()
        request.session.modified = True

    alternativas = list(pergunta.alternativa_set.all().order_by('id'))
    numero_atual = len(respondidas_ids) + 1

    context = {
        'modo': 'pergunta',
        'sessao': sessao,
        'pergunta': pergunta,
        'alternativas': alternativas,
        'nivel_atual': estado.get('nivel_atual', pergunta.nivel),
        'numero_atual': numero_atual,
        'total_perguntas': numero_atual,
        'progresso_percentual': 0,
    }
    return render(request, 'uniquiz/quiz-individual.html', context)


@require_POST
@credencial_requerida(1)
def responder_individual(request, sessao_id):
    pergunta_id_raw = request.POST.get('pergunta_id', '').strip()
    alternativa_id_raw = request.POST.get('alternativa_id', '').strip()

    try:
        pergunta_id = int(pergunta_id_raw)
        alternativa_id = int(alternativa_id_raw)
    except ValueError:
        messages.error(request, 'Selecione uma alternativa válida antes de confirmar.')
        return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)

    estado = request.session.get('quiz_individual')
    if not isinstance(estado, dict) or estado.get('sessao_id') != sessao_id:
        messages.warning(request, 'Sessão de quiz expirada ou inválida.')
        return redirect('uniquiz:modo-individual')

    if estado.get('pergunta_atual_id') != pergunta_id:
        messages.error(request, 'Pergunta não corresponde à etapa atual da sessão.')
        return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)

    inicio_ts = estado.get('pergunta_iniciada_em')
    if isinstance(inicio_ts, (int, float)):
        tempo_resposta = round(max(0.1, min(3600.0, time.time() - inicio_ts)), 2)
    else:
        tempo_resposta = 1.0

    try:
        with transaction.atomic():
            sessao = (
                SessaoIndividual.objects.select_for_update()
                .filter(pk=sessao_id)
                .first()
            )
            if sessao is None:
                messages.error(request, 'Sessão não encontrada.')
                return redirect('uniquiz:modo-individual')

            if sessao.usuario_id != request.user.id:
                return HttpResponseForbidden('Você não tem permissão para responder nesta sessão.')

            if sessao.status != 'em_andamento':
                return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)

            # Idempotência: evita pontuação duplicada por clique duplo ou reenvio
            if RespostaLog.objects.filter(
                sessao_individual=sessao,
                pergunta_id=pergunta_id,
            ).exists():
                return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)

            alternativa = (
                Alternativa.objects.select_related('pergunta')
                .filter(pk=alternativa_id, pergunta_id=pergunta_id)
                .first()
            )
            if alternativa is None:
                messages.error(request, 'Alternativa inválida para a pergunta atual.')
                return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)

            pergunta = alternativa.pergunta
            acertou = bool(alternativa.correta)
            pontos_ganhos = pergunta.pontuacao if acertou else 0

            RespostaLog.objects.create(
                usuario=request.user,
                pergunta=pergunta,
                sessao_individual=sessao,
                acertou=acertou,
                tempo_resposta_segundos=tempo_resposta,
            )

            game_over = False
            sessao_concluida = False
            nivel_base = max(int(estado.get('nivel_atual', 1)), pergunta.nivel)

            if acertou:
                SessaoIndividual.objects.filter(pk=sessao.pk).update(
                    pontuacao_final=F('pontuacao_final') + pontos_ganhos
                )
                Usuario.objects.select_for_update().filter(pk=request.user.pk).update(
                    pontuacao_total=F('pontuacao_total') + pontos_ganhos
                )
                respondidas_ids = list(
                    RespostaLog.objects.filter(sessao_individual=sessao).values_list('pergunta_id', flat=True)
                )
                # Ao acertar, a próxima pergunta vem do mesmo nível ou de um nível acima
                proxima_pergunta, nivel_sorteado = _sortear_proxima_pergunta(
                    categoria_id=estado.get('categoria_id'),
                    nivel_atual=nivel_base,
                    respondidas_ids=respondidas_ids,
                    apenas_nivel_exato=False,
                )
                if proxima_pergunta is None:
                    SessaoIndividual.objects.filter(pk=sessao.pk).update(status='finalizada')
                    sessao_concluida = True
                    estado['pergunta_atual_id'] = None
                else:
                    estado['nivel_atual'] = nivel_sorteado
                    estado['pergunta_atual_id'] = proxima_pergunta.id
            else:
                # Erro encerra a sessão imediatamente em Game Over
                game_over = True
                sessao_concluida = True
                estado['game_over'] = True
                estado['pergunta_atual_id'] = None
                SessaoIndividual.objects.filter(pk=sessao.pk).update(status='finalizada')

            total_respondidas = RespostaLog.objects.filter(sessao_individual=sessao).count()
            correta_obj = Alternativa.objects.filter(pergunta=pergunta, correta=True).first()
    except DatabaseError:
        messages.error(request, 'Erro ao registrar sua resposta. A operação foi revertida.')
        return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)

    estado['pergunta_iniciada_em'] = None
    estado['ultimo_feedback'] = {
        'pergunta_id': pergunta_id,
        'alternativa_escolhida_id': alternativa_id,
        'alternativa_correta_id': correta_obj.id if correta_obj else None,
        'alternativa_correta_texto': correta_obj.texto if correta_obj else '',
        'acertou': acertou,
        'game_over': game_over,
        'pontos_ganhos': pontos_ganhos,
        'tempo_resposta': tempo_resposta,
        'numero_atual': total_respondidas,
        'sessao_concluida': sessao_concluida,
    }
    request.session.modified = True

    return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)


@require_POST
@credencial_requerida(1)
def avancar_individual(request, sessao_id):
    sessao = get_object_or_404(SessaoIndividual, pk=sessao_id)
    if sessao.usuario_id != request.user.id:
        return HttpResponseForbidden('Você não tem permissão para acessar esta sessão.')

    estado = request.session.get('quiz_individual')
    if isinstance(estado, dict) and estado.get('sessao_id') == sessao.id:
        estado['ultimo_feedback'] = None
        estado['pergunta_iniciada_em'] = time.time()
        request.session.modified = True

    return redirect('uniquiz:jogar-individual', sessao_id=sessao.id)


@require_POST
@credencial_requerida(1)
def encerrar_individual(request, sessao_id):
    destino = 'uniquiz:modo-individual'
    try:
        with transaction.atomic():
            sessao = (
                SessaoIndividual.objects.select_for_update()
                .filter(pk=sessao_id)
                .first()
            )
            if sessao is None:
                return redirect('uniquiz:modo-individual')

            if sessao.usuario_id != request.user.id:
                return HttpResponseForbidden('Você não tem permissão para encerrar esta sessão.')

            if sessao.status == 'em_andamento':
                tem_respostas = RespostaLog.objects.filter(sessao_individual=sessao).exists()
                if tem_respostas:
                    sessao.status = 'finalizada'
                    sessao.save()
                    destino = 'uniquiz:jogar-individual'
                else:
                    sessao.status = 'abandonada'
                    sessao.save()
                    messages.info(request, 'Sessão encerrada sem respostas registradas.')
    except DatabaseError:
        messages.error(request, 'Não foi possível encerrar a sessão. Tente novamente.')
        return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)

    estado = request.session.get('quiz_individual')
    if isinstance(estado, dict) and estado.get('sessao_id') == sessao_id:
        request.session.pop('quiz_individual', None)
        request.session.modified = True

    if destino == 'uniquiz:jogar-individual':
        return redirect('uniquiz:jogar-individual', sessao_id=sessao_id)
    return redirect('uniquiz:modo-individual')


@credencial_requerida(2)
def telaProfessor(request):
    perguntas = (
        Pergunta.objects.filter(autor=request.user)
        .select_related('categoria', 'autor')
        .prefetch_related('alternativa_set')
        .order_by('-id')
    )
    categorias_professor = list(
        Categoria.objects.filter(pergunta__autor=request.user).distinct().order_by('nome')
    )
    nomes_db = list(Categoria.objects.values_list('nome', flat=True))
    categorias_opcoes = sorted(set(CATEGORIAS_PADRAO + nomes_db))

    context = {
        'perguntas': perguntas,
        'categorias': categorias_professor,
        'categorias_opcoes': categorias_opcoes,
    }
    return render(request, 'uniquiz/tela-professor.html', context)


@require_POST
@credencial_requerida(2)
def salvar_pergunta(request):
    pergunta_id_raw = request.POST.get('pergunta_id', '').strip()
    texto_pergunta = request.POST.get('texto_pergunta', '').strip()
    categoria_nome = request.POST.get('categoria', '').strip()
    nivel_raw = request.POST.get('nivel', '').strip()
    pontuacao_raw = request.POST.get('pontuacao', '').strip()
    correta_raw = request.POST.get('alternativa_correta', '').strip()
    alternativas_textos = [
        request.POST.get('alternativa_a', '').strip(),
        request.POST.get('alternativa_b', '').strip(),
        request.POST.get('alternativa_c', '').strip(),
        request.POST.get('alternativa_d', '').strip(),
    ]

    if not texto_pergunta or len(texto_pergunta) > 500:
        messages.error(request, 'O enunciado da pergunta é obrigatório e deve ter no máximo 500 caracteres.')
        return redirect('uniquiz:tela-professor')

    if not categoria_nome or len(categoria_nome) > 100:
        messages.error(request, 'Selecione uma categoria válida.')
        return redirect('uniquiz:tela-professor')

    if nivel_raw not in ('1', '2', '3'):
        messages.error(request, 'Selecione um nível de dificuldade válido.')
        return redirect('uniquiz:tela-professor')

    try:
        pontuacao = int(pontuacao_raw)
        if pontuacao < 1 or pontuacao > 1000:
            raise ValueError
    except ValueError:
        messages.error(request, 'A pontuação deve ser um número inteiro entre 1 e 1000.')
        return redirect('uniquiz:tela-professor')

    if any(not texto or len(texto) > 500 for texto in alternativas_textos):
        messages.error(request, 'Preencha todas as 4 alternativas (máximo de 500 caracteres cada).')
        return redirect('uniquiz:tela-professor')

    if correta_raw not in ('0', '1', '2', '3'):
        messages.error(request, 'Selecione qual alternativa é a resposta correta.')
        return redirect('uniquiz:tela-professor')

    nivel = int(nivel_raw)
    correta_idx = int(correta_raw)

    try:
        with transaction.atomic():
            if pergunta_id_raw:
                try:
                    pergunta_pk = int(pergunta_id_raw)
                except ValueError:
                    messages.error(request, 'Identificador de pergunta inválido.')
                    return redirect('uniquiz:tela-professor')

                pergunta = (
                    Pergunta.objects.select_for_update()
                    .filter(pk=pergunta_pk)
                    .first()
                )
                if pergunta is None:
                    messages.error(request, 'A pergunta que você tentou editar não foi encontrada.')
                    return redirect('uniquiz:tela-professor')

                if pergunta.autor_id != request.user.id:
                    return HttpResponseForbidden(
                        'Você só tem permissão para alterar perguntas criadas por você.'
                    )

                categoria_obj, _ = Categoria.objects.get_or_create(nome=categoria_nome)
                pergunta.categoria = categoria_obj
                pergunta.texto_pergunta = texto_pergunta
                pergunta.nivel = nivel
                pergunta.pontuacao = pontuacao
                pergunta.save()

                existentes = list(
                    Alternativa.objects.select_for_update()
                    .filter(pergunta=pergunta)
                    .order_by('id')
                )
                if len(existentes) == 4:
                    for idx, alt in enumerate(existentes):
                        alt.texto = alternativas_textos[idx]
                        alt.correta = idx == correta_idx
                        alt.save()
                else:
                    Alternativa.objects.filter(pergunta=pergunta).delete()
                    Alternativa.objects.bulk_create([
                        Alternativa(
                            pergunta=pergunta,
                            texto=texto,
                            correta=(idx == correta_idx),
                        )
                        for idx, texto in enumerate(alternativas_textos)
                    ])

                messages.success(request, 'Pergunta e respostas atualizadas com sucesso!')
            else:
                categoria_obj, _ = Categoria.objects.get_or_create(nome=categoria_nome)
                pergunta = Pergunta.objects.create(
                    categoria=categoria_obj,
                    autor=request.user,
                    texto_pergunta=texto_pergunta,
                    nivel=nivel,
                    pontuacao=pontuacao,
                )
                Alternativa.objects.bulk_create([
                    Alternativa(
                        pergunta=pergunta,
                        texto=texto,
                        correta=(idx == correta_idx),
                    )
                    for idx, texto in enumerate(alternativas_textos)
                ])
                messages.success(request, 'Nova pergunta cadastrada com sucesso!')
    except DatabaseError:
        messages.error(request, 'Não foi possível salvar a pergunta. A operação foi revertida.')

    return redirect('uniquiz:tela-professor')


@require_POST
@credencial_requerida(2)
def excluir_pergunta(request):
    pergunta_id_raw = request.POST.get('pergunta_id', '').strip()
    try:
        pergunta_pk = int(pergunta_id_raw)
    except ValueError:
        messages.error(request, 'Identificador de pergunta inválido.')
        return redirect('uniquiz:tela-professor')

    try:
        with transaction.atomic():
            pergunta = (
                Pergunta.objects.select_for_update()
                .filter(pk=pergunta_pk)
                .first()
            )
            if pergunta is None:
                messages.error(request, 'Pergunta não encontrada ou já removida.')
                return redirect('uniquiz:tela-professor')

            if pergunta.autor_id != request.user.id:
                return HttpResponseForbidden(
                    'Você só tem permissão para excluir perguntas criadas por você.'
                )

            pergunta.delete()
            messages.success(request, 'Pergunta removida do banco de dados com sucesso.')
    except DatabaseError:
        messages.error(request, 'Erro ao excluir a pergunta. A operação foi revertida.')

    return redirect('uniquiz:tela-professor')