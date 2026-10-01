from faker import Faker
from random import randint

from .models import Usuario


fake = Faker('pt_BR')


def popular_usuario():

   for i in range(1000):

      Usuario.objects.create(
         primeiro_nome=fake.first_name(),
         ultimo_nome=fake.last_name(),
         email=fake.unique.email(),
         senha=fake.password(length=10),
         credencial=randint(1, 2)
      )

   print('1000 usuarios criados com sucesso!')