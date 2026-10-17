from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class Usuario(AbstractUser):
    CREDENCIAL = [
        (1, 'Aluno'),
        (2, 'Professor')
    ]
    
    
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    credencial = models.IntegerField(choices=CREDENCIAL, default=1)
    curso = models.CharField(max_length=100, default='Engenharia de Computação')
    pontuacao_total = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

#  banco de questões
class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)

    def __str__(self):
        return self.nome

class Pergunta(models.Model):
    NIVEIS = [
        (1, 'Fácil'),
        (2, 'Médio'),
        (3, 'Difícil')
    ]
    
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    texto_pergunta = models.TextField(max_length=500)
    nivel = models.IntegerField(choices=NIVEIS, default=1)
    pontuacao = models.IntegerField(default=10)

    def __str__(self):
        return self.texto_pergunta

class Alternativa(models.Model):
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE)
    texto = models.CharField(max_length=500)
    correta = models.BooleanField(default=False)

    def __str__(self):
        return self.texto

#  implementa modo individual e 1v1)
class SessaoIndividual(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    pontuacao_final = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='em_andamento') # em_andamento, finalizada, game_over
    data_inicio = models.DateTimeField(auto_now_add=True)

class PartidaCompetitiva(models.Model):
    jogador1 = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='partidas_j1')
    jogador2 = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='partidas_j2', null=True, blank=True)
    vencedor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='vitorias')
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, default='aguardando') # aguardando, em_andamento, finalizada
    data_criacao = models.DateTimeField(auto_now_add=True)

class RespostaLog(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE)
    sessao_individual = models.ForeignKey(SessaoIndividual, on_delete=models.CASCADE, null=True, blank=True)
    partida_competitiva = models.ForeignKey(PartidaCompetitiva, on_delete=models.CASCADE, null=True, blank=True)
    acertou = models.BooleanField()
    tempo_resposta_segundos = models.FloatField()