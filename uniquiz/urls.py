from django.urls import path

from . import views, views_competitivo

app_name = 'uniquiz'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cadastro/', views.cadastro, name='cadastro'),
    path('aluno/', views.telaAluno, name='tela-aluno'),
    path('aluno/individual/', views.modo_individual, name='modo-individual'),
    path('aluno/individual/iniciar/', views.iniciar_modo_individual, name='iniciar-individual'),
    path('aluno/individual/sessao/<int:sessao_id>/', views.jogar_individual, name='jogar-individual'),
    path('aluno/individual/sessao/<int:sessao_id>/responder/', views.responder_individual, name='responder-individual'),
    path('aluno/individual/sessao/<int:sessao_id>/proxima/', views.avancar_individual, name='avancar-individual'),
    path('aluno/individual/sessao/<int:sessao_id>/encerrar/', views.encerrar_individual, name='encerrar-individual'),
    path('professor/', views.telaProfessor, name='tela-professor'),
    path('professor/perguntas/salvar/', views.salvar_pergunta, name='salvar-pergunta'),
    path('professor/perguntas/excluir/', views.excluir_pergunta, name='excluir-pergunta'),
    path('aluno/competitivo/', views_competitivo.modo_competitivo, name='modo-competitivo'),
    path('aluno/competitivo/buscar/', views_competitivo.buscar_partida, name='buscar-partida-1v1'),
    path('aluno/competitivo/criar-sala/', views_competitivo.criar_sala_privada, name='criar-sala-1v1'),
    path('aluno/competitivo/entrar-codigo/', views_competitivo.entrar_por_codigo, name='entrar-codigo-1v1'),
    path('aluno/competitivo/partida/<int:partida_id>/', views_competitivo.sala_partida_1v1, name='sala-partida-1v1'),
    path('aluno/competitivo/partida/<int:partida_id>/cancelar/', views_competitivo.cancelar_partida_1v1, name='cancelar-partida-1v1'),
]
