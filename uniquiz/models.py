from django.db import models

# Create your models here.
class Pergunta(models.Model):
   texto_pergunta = models.TextField(max_length=500)
   nivel = models.TextField(max_length=10)

   def __str__(self):
      return self.texto_pergunta

class Alternativa(models.Model):
   pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE)
   texto_alternativa = models.TextField(max_length=500)
   eh_correta = models.BooleanField(default=False)

   def __str__(self):
      return f"{self.texto_alternativa} ({'Correta' if self.eh_correta else 'Incorreta'})"
