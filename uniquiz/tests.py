from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from .models import Alternativa, Categoria, Pergunta, Usuario


class AutenticacaoEAcessoTests(TestCase):
    def setUp(self):
        self.aluno = Usuario.objects.create_user(
            username='aluno_seed_123',
            email='aluno@universidade.edu.br',
            password='SenhaSegura123',
            first_name='Ana',
            last_name='Souza',
            credencial=1,
        )
        self.professor = Usuario.objects.create_user(
            username='prof_seed_456',
            email='prof@universidade.edu.br',
            password='SenhaSegura123',
            first_name='Carlos',
            last_name='Lima',
            credencial=2,
        )

    def test_acesso_sem_login_bloqueado(self):
        for url_name in ('uniquiz:tela-aluno', 'uniquiz:tela-professor'):
            url = reverse(url_name)
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('uniquiz:login')}?next={url}")

        res_save = self.client.post(reverse('uniquiz:salvar-pergunta'), {})
        self.assertRedirects(res_save, reverse('uniquiz:login'))
        self.assertEqual(Pergunta.objects.count(), 0)

        res_del = self.client.post(reverse('uniquiz:excluir-pergunta'), {'pergunta_id': 1})
        self.assertRedirects(res_del, reverse('uniquiz:login'))

    def test_cadastro_aluno_e_login_com_email(self):
        response = self.client.post(
            reverse('uniquiz:cadastro'),
            {
                'primeiro_nome': 'João',
                'ultimo_nome': 'Silva',
                'email': 'joao.silva@universidade.edu.br',
                'senha': 'MinhaSenha123',
                'confirmar_senha': 'MinhaSenha123',
                'credencial': '1',
            },
        )
        self.assertRedirects(response, reverse('uniquiz:login'))
        novo = Usuario.objects.get(email='joao.silva@universidade.edu.br')
        self.assertEqual(novo.credencial, 1)
        self.assertNotEqual(novo.password, 'MinhaSenha123')
        self.assertTrue(novo.check_password('MinhaSenha123'))

        login_resp = self.client.post(
            reverse('uniquiz:login'),
            {
                'username': 'joao.silva@universidade.edu.br',
                'password': 'MinhaSenha123',
            },
        )
        self.assertRedirects(login_resp, reverse('uniquiz:tela-aluno'))

    def test_cadastro_rejeita_email_duplicado_e_senhas_divergentes(self):
        total_inicial = Usuario.objects.count()

        res_dup = self.client.post(
            reverse('uniquiz:cadastro'),
            {
                'primeiro_nome': 'Outro',
                'ultimo_nome': 'Aluno',
                'email': 'ALUNO@universidade.edu.br',
                'senha': 'SenhaSegura123',
                'confirmar_senha': 'SenhaSegura123',
                'credencial': '1',
            },
        )
        self.assertEqual(res_dup.status_code, 200)
        self.assertEqual(Usuario.objects.count(), total_inicial)

        res_mismatch = self.client.post(
            reverse('uniquiz:cadastro'),
            {
                'primeiro_nome': 'Maria',
                'ultimo_nome': 'Clara',
                'email': 'maria@universidade.edu.br',
                'senha': 'SenhaSegura123',
                'confirmar_senha': 'OutraSenha123',
                'credencial': '2',
            },
        )
        self.assertEqual(res_mismatch.status_code, 200)
        self.assertEqual(Usuario.objects.count(), total_inicial)

    def test_autorizacao_por_credencial_e_cache_control(self):
        # Login como aluno (inclusive com username != email)
        res = self.client.post(
            reverse('uniquiz:login'),
            {'username': 'aluno@universidade.edu.br', 'password': 'SenhaSegura123'},
        )
        self.assertRedirects(res, reverse('uniquiz:tela-aluno'))

        aluno_page = self.client.get(reverse('uniquiz:tela-aluno'))
        self.assertEqual(aluno_page.status_code, 200)
        self.assertIn('no-store', aluno_page.headers.get('Cache-Control', ''))

        # Aluno tentando acessar tela do professor é redirecionado
        prof_try = self.client.get(reverse('uniquiz:tela-professor'))
        self.assertRedirects(prof_try, reverse('uniquiz:tela-aluno'))

        # Aluno tentando enviar POST para salvar pergunta recebe 403
        post_try = self.client.post(reverse('uniquiz:salvar-pergunta'), {})
        self.assertEqual(post_try.status_code, 403)

        # Logout via GET é bloqueado (405); via POST encerra sessão
        self.assertEqual(self.client.get(reverse('uniquiz:logout')).status_code, 405)
        logout_resp = self.client.post(reverse('uniquiz:logout'))
        self.assertRedirects(logout_resp, reverse('uniquiz:login'))

        # Após logout não acessa mais /aluno/
        after_logout = self.client.get(reverse('uniquiz:tela-aluno'))
        self.assertRedirects(
            after_logout,
            f"{reverse('uniquiz:login')}?next={reverse('uniquiz:tela-aluno')}",
        )

    def test_professor_nao_acessa_tela_aluno(self):
        self.client.post(
            reverse('uniquiz:login'),
            {'username': 'prof@universidade.edu.br', 'password': 'SenhaSegura123'},
        )
        res = self.client.get(reverse('uniquiz:tela-aluno'))
        self.assertRedirects(res, reverse('uniquiz:tela-professor'))


class ProfessorCrudAcidTests(TestCase):
    def setUp(self):
        self.professor = Usuario.objects.create_user(
            username='prof@universidade.edu.br',
            email='prof@universidade.edu.br',
            password='SenhaSegura123',
            first_name='Beatriz',
            last_name='Mendes',
            credencial=2,
        )
        self.client.force_login(self.professor)

    def test_criar_editar_e_excluir_pergunta_com_transacao(self):
        # 1. Criar pergunta + 4 alternativas atomicamente
        create_resp = self.client.post(
            reverse('uniquiz:salvar-pergunta'),
            {
                'texto_pergunta': 'Qual estrutura segue LIFO?',
                'categoria': 'Estruturas de Dados',
                'nivel': '2',
                'pontuacao': '20',
                'alternativa_a': 'Fila',
                'alternativa_b': 'Pilha',
                'alternativa_c': 'Lista',
                'alternativa_d': 'Grafo',
                'alternativa_correta': '1',
            },
        )
        self.assertRedirects(create_resp, reverse('uniquiz:tela-professor'))
        self.assertEqual(Categoria.objects.count(), 1)
        self.assertEqual(Pergunta.objects.count(), 1)
        self.assertEqual(Alternativa.objects.count(), 4)

        pergunta = Pergunta.objects.first()
        self.assertEqual(pergunta.autor, self.professor)
        alternativas = list(pergunta.alternativa_set.order_by('id'))
        self.assertEqual([a.correta for a in alternativas], [False, True, False, False])

        # 2. Editar pergunta e alterar resposta correta
        edit_resp = self.client.post(
            reverse('uniquiz:salvar-pergunta'),
            {
                'pergunta_id': str(pergunta.id),
                'texto_pergunta': 'Qual estrutura segue FIFO?',
                'categoria': 'Algoritmos',
                'nivel': '1',
                'pontuacao': '10',
                'alternativa_a': 'Fila',
                'alternativa_b': 'Pilha',
                'alternativa_c': 'Heap',
                'alternativa_d': 'Árvore',
                'alternativa_correta': '0',
            },
        )
        self.assertRedirects(edit_resp, reverse('uniquiz:tela-professor'))
        pergunta.refresh_from_db()
        self.assertEqual(pergunta.texto_pergunta, 'Qual estrutura segue FIFO?')
        self.assertEqual(pergunta.categoria.nome, 'Algoritmos')
        self.assertEqual(pergunta.nivel, 1)
        self.assertEqual(pergunta.pontuacao, 10)
        alternativas_atualizadas = list(pergunta.alternativa_set.order_by('id'))
        self.assertEqual([a.correta for a in alternativas_atualizadas], [True, False, False, False])

        # 3. Excluir pergunta (remove em cascata as 4 alternativas)
        del_resp = self.client.post(
            reverse('uniquiz:excluir-pergunta'),
            {'pergunta_id': str(pergunta.id)},
        )
        self.assertRedirects(del_resp, reverse('uniquiz:tela-professor'))
        self.assertEqual(Pergunta.objects.count(), 0)
        self.assertEqual(Alternativa.objects.count(), 0)

    def test_atomicidade_rollback_quando_falha_ao_criar_alternativas(self):
        with patch.object(Alternativa.objects, 'bulk_create', side_effect=DatabaseError('Falha simulada')):
            resp = self.client.post(
                reverse('uniquiz:salvar-pergunta'),
                {
                    'texto_pergunta': 'Pergunta que deve sofrer rollback',
                    'categoria': 'Hardware',
                    'nivel': '3',
                    'pontuacao': '30',
                    'alternativa_a': 'A',
                    'alternativa_b': 'B',
                    'alternativa_c': 'C',
                    'alternativa_d': 'D',
                    'alternativa_correta': '2',
                },
            )
        self.assertRedirects(resp, reverse('uniquiz:tela-professor'))
        # Garante atomicidade: nem categoria nem pergunta órfã foram persistidas
        self.assertEqual(Categoria.objects.count(), 0)
        self.assertEqual(Pergunta.objects.count(), 0)
        self.assertEqual(Alternativa.objects.count(), 0)

    def test_professor_so_visualiza_e_altera_proprias_perguntas(self):
        outro_prof = Usuario.objects.create_user(
            username='outro.prof@universidade.edu.br',
            email='outro.prof@universidade.edu.br',
            password='SenhaSegura123',
            first_name='Helena',
            last_name='Rocha',
            credencial=2,
        )
        cat = Categoria.objects.create(nome='Algoritmos')
        p_minha = Pergunta.objects.create(
            categoria=cat,
            autor=self.professor,
            texto_pergunta='Pergunta da Beatriz',
            nivel=1,
            pontuacao=10,
        )
        p_outra = Pergunta.objects.create(
            categoria=cat,
            autor=outro_prof,
            texto_pergunta='Pergunta da Helena',
            nivel=2,
            pontuacao=20,
        )
        for p in (p_minha, p_outra):
            Alternativa.objects.bulk_create([
                Alternativa(pergunta=p, texto='A', correta=True),
                Alternativa(pergunta=p, texto='B', correta=False),
                Alternativa(pergunta=p, texto='C', correta=False),
                Alternativa(pergunta=p, texto='D', correta=False),
            ])

        # Beatriz vê apenas a própria pergunta na tela do professor
        page = self.client.get(reverse('uniquiz:tela-professor'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Pergunta da Beatriz')
        self.assertNotContains(page, 'Pergunta da Helena')

        # Beatriz não pode editar pergunta de Helena (403 Forbidden e sem alteração no banco)
        edit_resp = self.client.post(
            reverse('uniquiz:salvar-pergunta'),
            {
                'pergunta_id': str(p_outra.id),
                'texto_pergunta': 'Tentativa indevida de edição',
                'categoria': 'Nova Categoria Indevida',
                'nivel': '1',
                'pontuacao': '10',
                'alternativa_a': 'X',
                'alternativa_b': 'Y',
                'alternativa_c': 'Z',
                'alternativa_d': 'W',
                'alternativa_correta': '0',
            },
        )
        self.assertEqual(edit_resp.status_code, 403)
        p_outra.refresh_from_db()
        self.assertEqual(p_outra.texto_pergunta, 'Pergunta da Helena')
        self.assertFalse(Categoria.objects.filter(nome='Nova Categoria Indevida').exists())

        # Beatriz não pode excluir pergunta de Helena (403 Forbidden)
        del_resp = self.client.post(
            reverse('uniquiz:excluir-pergunta'),
            {'pergunta_id': str(p_outra.id)},
        )
        self.assertEqual(del_resp.status_code, 403)
        self.assertTrue(Pergunta.objects.filter(pk=p_outra.id).exists())


class ModoIndividualTests(TestCase):
    def setUp(self):
        from .models import RespostaLog, SessaoIndividual
        self.RespostaLog = RespostaLog
        self.SessaoIndividual = SessaoIndividual

        self.aluno = Usuario.objects.create_user(
            username='aluno1@uni.edu.br',
            email='aluno1@uni.edu.br',
            password='SenhaSegura123',
            first_name='Lucas',
            last_name='Alves',
            credencial=1,
        )
        self.outro_aluno = Usuario.objects.create_user(
            username='aluno2@uni.edu.br',
            email='aluno2@uni.edu.br',
            password='SenhaSegura123',
            first_name='Carla',
            last_name='Dias',
            credencial=1,
        )
        self.professor = Usuario.objects.create_user(
            username='prof1@uni.edu.br',
            email='prof1@uni.edu.br',
            password='SenhaSegura123',
            first_name='Marcos',
            last_name='Silva',
            credencial=2,
        )

        self.cat = Categoria.objects.create(nome='Matemática')
        self.outra_cat = Categoria.objects.create(nome='Algoritmos')

        self.p1 = Pergunta.objects.create(
            categoria=self.cat,
            texto_pergunta='Quanto é 2 + 2?',
            nivel=1,
            pontuacao=10,
        )
        self.p1_errada = Alternativa.objects.create(pergunta=self.p1, texto='3', correta=False)
        self.p1_correta = Alternativa.objects.create(pergunta=self.p1, texto='4', correta=True)
        Alternativa.objects.create(pergunta=self.p1, texto='5', correta=False)
        Alternativa.objects.create(pergunta=self.p1, texto='6', correta=False)

        self.p2 = Pergunta.objects.create(
            categoria=self.cat,
            texto_pergunta='Quanto é 5 × 4?',
            nivel=2,
            pontuacao=20,
        )
        self.p2_errada = Alternativa.objects.create(pergunta=self.p2, texto='15', correta=False)
        self.p2_correta = Alternativa.objects.create(pergunta=self.p2, texto='20', correta=True)
        Alternativa.objects.create(pergunta=self.p2, texto='25', correta=False)
        Alternativa.objects.create(pergunta=self.p2, texto='10', correta=False)

        self.p_nivel3_only = Pergunta.objects.create(
            categoria=self.outra_cat,
            texto_pergunta='Complexidade da busca binária ordenada?',
            nivel=3,
            pontuacao=30,
        )
        Alternativa.objects.create(pergunta=self.p_nivel3_only, texto='O(log n)', correta=True)
        Alternativa.objects.create(pergunta=self.p_nivel3_only, texto='O(n)', correta=False)
        Alternativa.objects.create(pergunta=self.p_nivel3_only, texto='O(n²)', correta=False)
        Alternativa.objects.create(pergunta=self.p_nivel3_only, texto='O(1)', correta=False)

    def test_modo_individual_exige_login_e_credencial_aluno(self):
        resp_anon = self.client.get(reverse('uniquiz:modo-individual'))
        self.assertRedirects(
            resp_anon,
            f"{reverse('uniquiz:login')}?next={reverse('uniquiz:modo-individual')}",
        )

        self.client.force_login(self.professor)
        resp_prof = self.client.get(reverse('uniquiz:modo-individual'))
        self.assertRedirects(resp_prof, reverse('uniquiz:tela-professor'))

    def test_sessao_sempre_comeca_no_nivel_1_e_encerra_em_game_over_ao_errar(self):
        self.client.force_login(self.aluno)

        # Categoria sem perguntas de nível 1 inicia com fallback para o nível disponível
        resp_fallback = self.client.post(
            reverse('uniquiz:iniciar-individual'),
            {'categoria': str(self.outra_cat.id)},
        )
        sessao_fallback = self.SessaoIndividual.objects.get(usuario=self.aluno)
        self.assertRedirects(
            resp_fallback,
            reverse('uniquiz:jogar-individual', args=[sessao_fallback.id]),
        )
        page_fallback = self.client.get(reverse('uniquiz:jogar-individual', args=[sessao_fallback.id]))
        self.assertEqual(page_fallback.context['pergunta'].id, self.p_nivel3_only.id)

        # Inicia sessão na categoria Matemática -> primeira pergunta deve ser nível 1
        start_resp = self.client.post(
            reverse('uniquiz:iniciar-individual'),
            {'categoria': str(self.cat.id)},
        )
        sessao_fallback.refresh_from_db()
        self.assertEqual(sessao_fallback.status, 'abandonada')

        sessao = self.SessaoIndividual.objects.get(usuario=self.aluno, status='em_andamento')
        self.assertRedirects(
            start_resp,
            reverse('uniquiz:jogar-individual', args=[sessao.id]),
        )

        page1 = self.client.get(reverse('uniquiz:jogar-individual', args=[sessao.id]))
        self.assertEqual(page1.context['modo'], 'pergunta')
        pergunta1 = page1.context['pergunta']
        self.assertEqual(pergunta1.categoria_id, self.cat.id)
        self.assertEqual(pergunta1.nivel, 1)

        alt1_correta = pergunta1.alternativa_set.get(correta=True)

        # Acerta a primeira pergunta e testa idempotência em reenvio
        self.client.post(
            reverse('uniquiz:responder-individual', args=[sessao.id]),
            {'pergunta_id': str(pergunta1.id), 'alternativa_id': str(alt1_correta.id)},
        )
        self.client.post(
            reverse('uniquiz:responder-individual', args=[sessao.id]),
            {'pergunta_id': str(pergunta1.id), 'alternativa_id': str(alt1_correta.id)},
        )

        sessao.refresh_from_db()
        self.aluno.refresh_from_db()
        self.assertEqual(sessao.pontuacao_final, pergunta1.pontuacao)
        self.assertEqual(self.aluno.pontuacao_total, pergunta1.pontuacao)
        self.assertEqual(sessao.status, 'em_andamento')

        # Avança para a próxima pergunta não respondida
        self.client.post(reverse('uniquiz:avancar-individual', args=[sessao.id]))
        page2 = self.client.get(reverse('uniquiz:jogar-individual', args=[sessao.id]))
        self.assertEqual(page2.context['modo'], 'pergunta')
        pergunta2 = page2.context['pergunta']
        self.assertNotEqual(pergunta2.id, pergunta1.id)

        alt2_errada = pergunta2.alternativa_set.filter(correta=False).first()

        # Erra a segunda pergunta -> entra imediatamente em Game Over e encerra a sessão
        self.client.post(
            reverse('uniquiz:responder-individual', args=[sessao.id]),
            {'pergunta_id': str(pergunta2.id), 'alternativa_id': str(alt2_errada.id)},
        )
        fb_page = self.client.get(reverse('uniquiz:jogar-individual', args=[sessao.id]))
        self.assertEqual(fb_page.context['modo'], 'feedback')
        self.assertTrue(fb_page.context['game_over'])

        self.client.post(reverse('uniquiz:avancar-individual', args=[sessao.id]))
        result_page = self.client.get(reverse('uniquiz:jogar-individual', args=[sessao.id]))
        self.assertEqual(result_page.context['modo'], 'resultado')
        self.assertTrue(result_page.context['game_over'])
        self.assertEqual(result_page.context['total_respostas'], 2)
        self.assertEqual(result_page.context['total_acertos'], 1)
        self.assertEqual(result_page.context['total_erros'], 1)

        sessao.refresh_from_db()
        self.aluno.refresh_from_db()
        self.assertEqual(sessao.status, 'finalizada')
        self.assertEqual(sessao.pontuacao_final, pergunta1.pontuacao)
        self.assertEqual(self.aluno.pontuacao_total, pergunta1.pontuacao)
        self.assertEqual(self.RespostaLog.objects.filter(sessao_individual=sessao).count(), 2)


    def test_modo_geral_sorteia_nivel_1_sem_filtrar_categoria(self):
        self.client.force_login(self.aluno)
        start_resp = self.client.post(
            reverse('uniquiz:iniciar-individual'),
            {'categoria': ''},
        )
        sessao = self.SessaoIndividual.objects.get(usuario=self.aluno)
        self.assertRedirects(
            start_resp,
            reverse('uniquiz:jogar-individual', args=[sessao.id]),
        )

        page = self.client.get(reverse('uniquiz:jogar-individual', args=[sessao.id]))
        self.assertEqual(page.context['pergunta'].nivel, 1)
    def test_isolamento_de_sessao_entre_alunos_e_rollback_acid(self):
        self.client.force_login(self.aluno)
        self.client.post(
            reverse('uniquiz:iniciar-individual'),
            {'categoria': ''},
        )
        sessao = self.SessaoIndividual.objects.get(usuario=self.aluno)

        # Simula falha no banco ao atualizar pontuação -> rollback remove RespostaLog também
        page = self.client.get(reverse('uniquiz:jogar-individual', args=[sessao.id]))
        pergunta_atual = page.context['pergunta']
        correta = Alternativa.objects.get(pergunta=pergunta_atual, correta=True)
        with patch.object(self.SessaoIndividual.objects, 'filter', side_effect=DatabaseError('Erro simulado')):
            self.client.post(
                reverse('uniquiz:responder-individual', args=[sessao.id]),
                {'pergunta_id': str(pergunta_atual.id), 'alternativa_id': str(correta.id)},
            )
        self.aluno.refresh_from_db()
        self.assertEqual(self.RespostaLog.objects.filter(sessao_individual=sessao).count(), 0)
        self.assertEqual(self.aluno.pontuacao_total, 0)

        # Outro aluno não pode acessar nem encerrar a sessão do primeiro aluno
        self.client.force_login(self.outro_aluno)
        self.assertEqual(
            self.client.get(reverse('uniquiz:jogar-individual', args=[sessao.id])).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('uniquiz:encerrar-individual', args=[sessao.id])).status_code,
            403,
        )

