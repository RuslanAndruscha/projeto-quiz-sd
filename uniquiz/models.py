from django.db import models

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


