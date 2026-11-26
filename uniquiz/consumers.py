import asyncio
import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import transaction
from django.db.models import F

from .models import (
    Alternativa,
    PartidaCompetitiva,
    PerguntaPartida,
    RespostaLog,
    SalaCompetitiva,
    Usuario,
)
from .views_competitivo import (
    TEMPO_LIMITE_PERGUNTA_1V1,
    calcular_resultado_1v1,
    montar_payload_resultado,
    nome_exibicao_usuario,
)

logger = logging.getLogger(__name__)

PAUSA_ENTRE_RODADAS_SEGUNDOS = 3

# Estado em memória por partida ativa (usado em ambiente local com InMemoryChannelLayer)
ESTADOS_PARTIDAS = {}


def _obter_ou_criar_estado(partida_id):
    estado = ESTADOS_PARTIDAS.get(partida_id)
    if estado is None:
        estado = {
            'lock': asyncio.Lock(),
            'canais_por_usuario': {},  # {user_id_str: set(channel_names)}
            'iniciada': False,
            'rodadas_concluidas': False,
            'finalizada': False,
            'indice_atual': 0,
            'perguntas': [],
            'rodada_iniciada_em': None,
            'respostas_rodada': {},
            'timer_task': None,
            'tempo_limite': TEMPO_LIMITE_PERGUNTA_1V1,
            'jogador1_id': None,
            'jogador2_id': None,
            'jogadores': {},
        }
        ESTADOS_PARTIDAS[partida_id] = estado
    return estado


def _cancelar_timer_task(estado):
    """Cancela a task de timer apenas se ela não for a própria task em execução."""
    task = estado.get('timer_task')
    current = asyncio.current_task()
    if task and not task.done() and task is not current:
        task.cancel()
    estado['timer_task'] = None


class Partida1v1Consumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated or getattr(user, 'credencial', None) != 1:
            await self.close(code=4003)
            return

        self.partida_id = int(self.scope['url_route']['kwargs']['partida_id'])
        self.user_id = str(user.id)
        self.group_name = f'partida_1v1_{self.partida_id}'

        dados_partida = await self._carregar_dados_partida()
        if dados_partida is None:
            await self.close(code=4004)
            return

        if self.user_id not in (dados_partida['jogador1_id'], dados_partida['jogador2_id']):
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        if dados_partida['status'] == 'cancelada':
            await self.send(text_data=json.dumps({'tipo': 'partida_cancelada'}))
            await self.close()
            return

        if dados_partida['status'] == 'finalizada':
            resultado = await self._obter_resultado_final_db()
            await self.send(text_data=json.dumps({
                'tipo': 'partida_finalizada',
                'resultado': resultado,
            }))
            return

        estado = _obter_ou_criar_estado(self.partida_id)
        payloads_para_enviar = []
        payload_privado = None

        async with estado['lock']:
            canais = estado['canais_por_usuario'].setdefault(self.user_id, set())
            canais.add(self.channel_name)
            estado['tempo_limite'] = dados_partida['tempo_limite']
            estado['jogador1_id'] = dados_partida['jogador1_id']
            estado['jogador2_id'] = dados_partida['jogador2_id']

            if dados_partida['status'] == 'aguardando':
                payload_privado = {
                    'tipo': 'aguardando_oponente',
                    'codigo': dados_partida['codigo'],
                    'privada': dados_partida['privada'],
                    'categoria': dados_partida['categoria'],
                    'total_perguntas': dados_partida['total_perguntas'],
                    'tempo_limite': dados_partida['tempo_limite'],
                    'jogador1_nome': dados_partida['jogador1_nome'],
                }
            elif dados_partida['status'] == 'em_andamento':
                j1_id = dados_partida['jogador1_id']
                j2_id = dados_partida['jogador2_id']

                if not estado['jogadores']:
                    estado['jogadores'] = {
                        j1_id: {
                            'id': j1_id,
                            'nome': dados_partida['jogador1_nome'],
                            'acertos': 0,
                            'tempo_corretas': 0.0,
                            'pontos': 0,
                        },
                        j2_id: {
                            'id': j2_id,
                            'nome': dados_partida['jogador2_nome'],
                            'acertos': 0,
                            'tempo_corretas': 0.0,
                            'pontos': 0,
                        },
                    }

                j1_conectado = bool(estado['canais_por_usuario'].get(j1_id))
                j2_conectado = bool(estado['canais_por_usuario'].get(j2_id))

                if not estado['iniciada'] and j1_conectado and j2_conectado:
                    perguntas = await self._carregar_perguntas_partida()
                    estado['perguntas'] = perguntas
                    progresso = await self._carregar_progresso_partida_db(perguntas, j1_id, j2_id)
                    for uid, stats in progresso['jogadores'].items():
                        if uid in estado['jogadores']:
                            estado['jogadores'][uid].update(stats)

                    indice_inicial = progresso['indice_inicial']
                    estado['iniciada'] = True

                    if indice_inicial >= len(perguntas):
                        estado['rodadas_concluidas'] = True
                        payload_final = await self._finalizar_partida_locked(estado, motivo='normal')
                        if payload_final:
                            payloads_para_enviar.append(payload_final)
                    else:
                        payloads_para_enviar.append({
                            'tipo': 'partida_iniciada',
                            'categoria': dados_partida['categoria'],
                            'total_perguntas': len(perguntas),
                            'tempo_limite': estado['tempo_limite'],
                            'jogadores': estado['jogadores'],
                        })
                        payload_rodada = await self._preparar_rodada_locked(estado, indice_inicial)
                        if progresso['respostas_rodada_inicial']:
                            estado['respostas_rodada'].update(progresso['respostas_rodada_inicial'])
                        if payload_rodada:
                            payloads_para_enviar.append(payload_rodada)
                elif not estado['iniciada']:
                    payload_privado = {
                        'tipo': 'aguardando_conexao',
                        'mensagem': 'Oponente encontrado! Aguardando sincronização...',
                        'jogadores': estado['jogadores'],
                    }
                elif not estado['finalizada']:
                    # Reenvia estado atual caso o jogador já esteja em partida ativa
                    q = estado['perguntas'][estado['indice_atual']]
                    decorrido = time.monotonic() - (estado['rodada_iniciada_em'] or time.monotonic())
                    restante = max(1, int(estado['tempo_limite'] - decorrido))
                    payload_privado = {
                        'tipo': 'nova_pergunta',
                        'numero': estado['indice_atual'] + 1,
                        'total': len(estado['perguntas']),
                        'tempo_limite': restante,
                        'tempo_limite_total': estado['tempo_limite'],
                        'jogadores': estado['jogadores'],
                        'pergunta': self._serializar_pergunta_publica(q),
                    }
                else:
                    resultado = await self._obter_resultado_final_db()
                    payload_privado = {
                        'tipo': 'partida_finalizada',
                        'resultado': resultado,
                    }

        if payload_privado:
            await self.send(text_data=json.dumps(payload_privado))

        for payload in payloads_para_enviar:
            await self._broadcast(payload)

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if not hasattr(self, 'partida_id'):
            return

        estado = ESTADOS_PARTIDAS.get(self.partida_id)
        if estado is None:
            return

        payload_final = None
        async with estado['lock']:
            canais = estado['canais_por_usuario'].get(self.user_id)
            if canais:
                canais.discard(self.channel_name)
                if not canais:
                    estado['canais_por_usuario'].pop(self.user_id, None)

            ainda_conectado = bool(estado['canais_por_usuario'].get(self.user_id))
            if estado['iniciada'] and not estado['finalizada'] and not ainda_conectado:
                if estado.get('rodadas_concluidas'):
                    payload_final = await self._finalizar_partida_locked(
                        estado,
                        motivo='normal',
                    )
                else:
                    vencedor_id = (
                        estado['jogador2_id']
                        if self.user_id == estado['jogador1_id']
                        else estado['jogador1_id']
                    )
                    payload_final = await self._finalizar_partida_locked(
                        estado,
                        motivo='desconexao',
                        vencedor_forcado_id=vencedor_id,
                    )

            if not estado['canais_por_usuario'] and (not estado['iniciada'] or estado['finalizada']):
                ESTADOS_PARTIDAS.pop(self.partida_id, None)

        if payload_final:
            await self._broadcast(payload_final)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get('acao') != 'responder':
            return

        try:
            pergunta_id = int(data.get('pergunta_id'))
            alternativa_id = int(data.get('alternativa_id'))
        except (TypeError, ValueError):
            return

        estado = ESTADOS_PARTIDAS.get(self.partida_id)
        if estado is None:
            return

        payload_privado = None
        payloads_broadcast = []

        async with estado['lock']:
            if not estado['iniciada'] or estado['finalizada']:
                return

            if estado['indice_atual'] >= len(estado['perguntas']):
                return

            pergunta_atual = estado['perguntas'][estado['indice_atual']]
            if pergunta_atual['id'] != pergunta_id:
                return

            if self.user_id in estado['respostas_rodada']:
                return

            decorrido = time.monotonic() - (estado['rodada_iniciada_em'] or time.monotonic())
            tempo_resposta = round(
                min(float(estado['tempo_limite']), max(0.05, decorrido)),
                2,
            )

            registro = await self._registrar_resposta_db(
                user_id=self.user_id,
                pergunta_id=pergunta_id,
                alternativa_id=alternativa_id,
                tempo_resposta=tempo_resposta,
            )
            if registro is None:
                return

            acertou = registro['acertou']
            pontos = registro['pontos']

            estado['respostas_rodada'][self.user_id] = {
                'acertou': acertou,
                'tempo': tempo_resposta,
                'alternativa_id': alternativa_id,
                'timeout': False,
            }

            jogador = estado['jogadores'][self.user_id]
            if acertou:
                jogador['acertos'] += 1
                jogador['tempo_corretas'] = round(jogador['tempo_corretas'] + tempo_resposta, 2)
                jogador['pontos'] += pontos

            payload_privado = {
                'tipo': 'resposta_registrada',
                'pergunta_id': pergunta_id,
                'alternativa_id': alternativa_id,
                'tempo': tempo_resposta,
            }
            payloads_broadcast.append({
                'tipo': 'jogador_respondeu',
                'usuario_id': self.user_id,
            })

            if len(estado['respostas_rodada']) >= 2:
                _cancelar_timer_task(estado)
                payload_rodada = await self._encerrar_rodada_locked(
                    estado,
                    estado['indice_atual'],
                )
                if payload_rodada:
                    payloads_broadcast.append(payload_rodada)

        if payload_privado:
            await self.send(text_data=json.dumps(payload_privado))

        for payload in payloads_broadcast:
            await self._broadcast(payload)

    async def evento_partida(self, event):
        await self.send(text_data=json.dumps(event['payload']))

    async def _broadcast(self, payload):
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'evento_partida',
                'payload': payload,
            },
        )

    def _serializar_pergunta_publica(self, q):
        return {
            'id': q['id'],
            'texto': q['texto'],
            'categoria': q['categoria'],
            'nivel': q['nivel'],
            'nivel_display': q['nivel_display'],
            'pontuacao': q['pontuacao'],
            'alternativas': [
                {'id': alt['id'], 'texto': alt['texto']}
                for alt in q['alternativas']
            ],
        }

    async def _preparar_rodada_locked(self, estado, indice):
        if estado['finalizada']:
            return None

        if indice >= len(estado['perguntas']):
            return await self._finalizar_partida_locked(estado, motivo='normal')

        estado['indice_atual'] = indice
        estado['respostas_rodada'] = {}
        estado['rodada_iniciada_em'] = time.monotonic()

        _cancelar_timer_task(estado)

        estado['timer_task'] = asyncio.create_task(
            self._temporizador_rodada(self.partida_id, indice, estado['tempo_limite'])
        )

        q = estado['perguntas'][indice]
        return {
            'tipo': 'nova_pergunta',
            'numero': indice + 1,
            'total': len(estado['perguntas']),
            'tempo_limite': estado['tempo_limite'],
            'tempo_limite_total': estado['tempo_limite'],
            'jogadores': estado['jogadores'],
            'pergunta': self._serializar_pergunta_publica(q),
        }

    async def _temporizador_rodada(self, partida_id, indice_esperado, tempo_limite):
        try:
            await asyncio.sleep(tempo_limite)
        except asyncio.CancelledError:
            return

        estado = ESTADOS_PARTIDAS.get(partida_id)
        if estado is None:
            return

        payload_rodada = None
        try:
            async with estado['lock']:
                if estado['finalizada'] or estado['indice_atual'] != indice_esperado:
                    return
                payload_rodada = await self._encerrar_rodada_locked(estado, indice_esperado)

            if payload_rodada:
                await self._broadcast(payload_rodada)
        except Exception:
            logger.exception('Erro no temporizador da rodada %s da partida %s', indice_esperado, partida_id)

    async def _encerrar_rodada_locked(self, estado, indice_esperado):
        if estado['finalizada'] or estado['indice_atual'] != indice_esperado:
            return None

        q = estado['perguntas'][indice_esperado]
        tempo_limite = float(estado['tempo_limite'])

        for uid in (estado['jogador1_id'], estado['jogador2_id']):
            if uid and uid not in estado['respostas_rodada']:
                await self._registrar_timeout_db(
                    user_id=uid,
                    pergunta_id=q['id'],
                    tempo_limite=tempo_limite,
                )
                estado['respostas_rodada'][uid] = {
                    'acertou': False,
                    'tempo': tempo_limite,
                    'alternativa_id': None,
                    'timeout': True,
                }

        ultima_rodada = (indice_esperado + 1) >= len(estado['perguntas'])
        if ultima_rodada:
            estado['rodadas_concluidas'] = True

        _cancelar_timer_task(estado)
        estado['timer_task'] = asyncio.create_task(
            self._avancar_apos_pausa(self.partida_id, indice_esperado + 1)
        )

        return {
            'tipo': 'resultado_rodada',
            'numero': indice_esperado + 1,
            'total': len(estado['perguntas']),
            'alternativa_correta_id': q['correta_id'],
            'alternativa_correta_texto': q['correta_texto'],
            'respostas': estado['respostas_rodada'],
            'jogadores': estado['jogadores'],
            'ultima_rodada': ultima_rodada,
            'pausa_segundos': PAUSA_ENTRE_RODADAS_SEGUNDOS,
        }

    async def _avancar_apos_pausa(self, partida_id, proximo_indice):
        try:
            await asyncio.sleep(PAUSA_ENTRE_RODADAS_SEGUNDOS)
        except asyncio.CancelledError:
            return

        estado = ESTADOS_PARTIDAS.get(partida_id)
        if estado is None:
            return

        payload = None
        try:
            async with estado['lock']:
                if estado['finalizada']:
                    return
                payload = await self._preparar_rodada_locked(estado, proximo_indice)

            if payload:
                await self._broadcast(payload)
        except Exception:
            logger.exception('Erro ao avançar/finalizar partida %s no índice %s', partida_id, proximo_indice)

    async def _finalizar_partida_locked(self, estado, motivo='normal', vencedor_forcado_id=None):
        if estado['finalizada']:
            return None

        estado['finalizada'] = True
        _cancelar_timer_task(estado)

        try:
            resultado = await self._persistir_finalizacao_db(
                motivo=motivo,
                vencedor_forcado_id=vencedor_forcado_id,
            )
        except Exception:
            estado['finalizada'] = False
            logger.exception('Erro ao persistir finalização da partida %s', self.partida_id)
            raise

        return {
            'tipo': 'partida_finalizada',
            'resultado': resultado,
        }

    @database_sync_to_async
    def _carregar_dados_partida(self):
        partida = (
            PartidaCompetitiva.objects.select_related('categoria', 'jogador1', 'jogador2')
            .filter(pk=self.partida_id)
            .first()
        )
        if partida is None:
            return None

        sala = SalaCompetitiva.objects.filter(partida=partida).first()
        return {
            'status': partida.status,
            'jogador1_id': str(partida.jogador1_id),
            'jogador2_id': str(partida.jogador2_id) if partida.jogador2_id else None,
            'jogador1_nome': nome_exibicao_usuario(partida.jogador1),
            'jogador2_nome': nome_exibicao_usuario(partida.jogador2),
            'categoria': partida.categoria.nome if partida.categoria else 'Modo Geral',
            'codigo': sala.codigo if sala else '',
            'privada': sala.privada if sala else False,
            'total_perguntas': sala.total_perguntas if sala else 10,
            'tempo_limite': sala.tempo_limite_segundos if sala else TEMPO_LIMITE_PERGUNTA_1V1,
        }

    @database_sync_to_async
    def _carregar_perguntas_partida(self):
        vinculos = list(
            PerguntaPartida.objects.filter(partida_id=self.partida_id)
            .select_related('pergunta', 'pergunta__categoria')
            .prefetch_related('pergunta__alternativa_set')
            .order_by('ordem')
        )
        resultado = []
        for item in vinculos:
            alts = list(item.pergunta.alternativa_set.all().order_by('id'))
            correta = next((a for a in alts if a.correta), None)
            resultado.append({
                'id': item.pergunta_id,
                'texto': item.pergunta.texto_pergunta,
                'categoria': item.pergunta.categoria.nome,
                'nivel': item.pergunta.nivel,
                'nivel_display': item.pergunta.get_nivel_display(),
                'pontuacao': item.pergunta.pontuacao,
                'correta_id': correta.id if correta else None,
                'correta_texto': correta.texto if correta else '',
                'alternativas': [
                    {'id': a.id, 'texto': a.texto}
                    for a in alts
                ],
            })
        return resultado

    @database_sync_to_async
    def _registrar_resposta_db(self, user_id, pergunta_id, alternativa_id, tempo_resposta):
        with transaction.atomic():
            partida = (
                PartidaCompetitiva.objects.select_for_update()
                .filter(pk=self.partida_id, status='em_andamento')
                .first()
            )
            if partida is None:
                return None

            if RespostaLog.objects.filter(
                partida_competitiva=partida,
                usuario_id=user_id,
                pergunta_id=pergunta_id,
            ).exists():
                return None

            alternativa = (
                Alternativa.objects.select_related('pergunta')
                .filter(pk=alternativa_id, pergunta_id=pergunta_id)
                .first()
            )
            if alternativa is None:
                return None

            acertou = bool(alternativa.correta)
            pontos = int(alternativa.pergunta.pontuacao) if acertou else 0

            RespostaLog.objects.create(
                usuario_id=user_id,
                pergunta_id=pergunta_id,
                partida_competitiva=partida,
                acertou=acertou,
                tempo_resposta_segundos=tempo_resposta,
            )

            return {'acertou': acertou, 'pontos': pontos}

    @database_sync_to_async
    def _registrar_timeout_db(self, user_id, pergunta_id, tempo_limite):
        with transaction.atomic():
            partida = (
                PartidaCompetitiva.objects.select_for_update()
                .filter(pk=self.partida_id, status='em_andamento')
                .first()
            )
            if partida is None:
                return

            if not RespostaLog.objects.filter(
                partida_competitiva=partida,
                usuario_id=user_id,
                pergunta_id=pergunta_id,
            ).exists():
                RespostaLog.objects.create(
                    usuario_id=user_id,
                    pergunta_id=pergunta_id,
                    partida_competitiva=partida,
                    acertou=False,
                    tempo_resposta_segundos=tempo_limite,
                )

    @database_sync_to_async
    def _carregar_progresso_partida_db(self, perguntas, j1_id, j2_id):
        logs = list(
            RespostaLog.objects.filter(partida_competitiva_id=self.partida_id)
            .select_related('pergunta')
        )
        jogadores = {
            uid: {'acertos': 0, 'tempo_corretas': 0.0, 'pontos': 0}
            for uid in (j1_id, j2_id)
            if uid
        }
        respostas_por_pergunta = {}
        for log in logs:
            uid = str(log.usuario_id)
            respostas_por_pergunta.setdefault(log.pergunta_id, {})[uid] = {
                'acertou': bool(log.acertou),
                'tempo': round(float(log.tempo_resposta_segundos), 2),
                'alternativa_id': None,
                'timeout': False,
            }
            if uid in jogadores and log.acertou:
                jogadores[uid]['acertos'] += 1
                jogadores[uid]['tempo_corretas'] = round(
                    jogadores[uid]['tempo_corretas'] + float(log.tempo_resposta_segundos),
                    2,
                )
                jogadores[uid]['pontos'] += int(log.pergunta.pontuacao)

        jogadores_esperados = {uid for uid in (j1_id, j2_id) if uid}
        indice_inicial = len(perguntas)
        respostas_rodada_inicial = {}
        for idx, q in enumerate(perguntas):
            respostas_q = respostas_por_pergunta.get(q['id'], {})
            if not jogadores_esperados.issubset(respostas_q.keys()):
                indice_inicial = idx
                respostas_rodada_inicial = respostas_q
                break

        return {
            'jogadores': jogadores,
            'indice_inicial': indice_inicial,
            'respostas_rodada_inicial': respostas_rodada_inicial,
        }

    @database_sync_to_async
    def _persistir_finalizacao_db(self, motivo='normal', vencedor_forcado_id=None):
        with transaction.atomic():
            partida = (
                PartidaCompetitiva.objects.select_for_update(of=('self',))
                .select_related('categoria', 'jogador1', 'jogador2')
                .get(pk=self.partida_id)
            )
            if partida.status != 'finalizada':
                logs = list(
                    RespostaLog.objects.filter(partida_competitiva=partida)
                    .select_related('pergunta')
                )
                calculo = calcular_resultado_1v1(
                    partida,
                    logs=logs,
                    motivo=motivo,
                    vencedor_forcado_id=vencedor_forcado_id,
                )
                partida.vencedor_id = calculo['vencedor_id']
                partida.status = 'finalizada'
                partida.save(update_fields=['vencedor', 'status'])

                SalaCompetitiva.objects.filter(partida=partida).update(
                    motivo_encerramento=motivo
                )

                # Soma os pontos dos acertos da partida à pontuação acumulada de cada jogador
                for uid, stats in calculo['jogadores'].items():
                    if stats['pontos'] > 0:
                        Usuario.objects.filter(pk=uid).update(
                            pontuacao_total=F('pontuacao_total') + stats['pontos']
                        )

            return montar_payload_resultado(partida)

    @database_sync_to_async
    def _obter_resultado_final_db(self):
        partida = (
            PartidaCompetitiva.objects.select_related('categoria', 'jogador1', 'jogador2', 'vencedor')
            .get(pk=self.partida_id)
        )
        return montar_payload_resultado(partida)