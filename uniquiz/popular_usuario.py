from faker import Faker
from random import randint
from .models import Usuario

fake = Faker('pt_BR')

def popular_usuario():
    Usuario.objects.filter(is_superuser=False).delete()

    for i in range(50): 
        primeiro = fake.first_name()
        ultimo = fake.last_name()
        username = f"{primeiro.lower()}_{ultimo.lower()}_{randint(100,999)}"
        
        Usuario.objects.create_user(
            username=username,
            first_name=primeiro,
            last_name=ultimo,
            email=fake.unique.email(),
            password="senha123Padrao", 
            credencial=randint(1, 2),
            curso="Engenharia de Computação"
        )

    print('Usuários criados com sucesso e com senhas seguras!')