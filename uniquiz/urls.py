from django.urls import path

from . import views

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
]
