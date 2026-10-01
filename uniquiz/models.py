from django.db import models

import uuid

# Create your models here.
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

class Usuario(models.Model):
   CREDENCIAL = [
         (1, 'Aluno'),
         (2, 'Professor')
      ]

   id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
   primeiro_nome = models.CharField(max_length=100)
   ultimo_nome = models.CharField(max_length=100)
   email = models.CharField(max_length=100, unique=True)
   senha = models.CharField(max_length=50)
   data_criacao = models.DateTimeField(auto_now_add=True, editable=False)
   credencial = models.IntegerField(choices=CREDENCIAL, default=1)

   def __str__(self):
      return self.primeiro_nome

