import random

from .models import Categoria, Pergunta, Alternativa


def criar_alternativas(pergunta, resposta_correta):
    alternativas = {resposta_correta}

    while len(alternativas) < 4:
        variacao = random.randint(-10, 10)
        alternativa = resposta_correta + variacao

        if alternativa >= 0:
            alternativas.add(alternativa)

    alternativas = list(alternativas)
    random.shuffle(alternativas)

    for valor in alternativas:
        Alternativa.objects.create(
            pergunta=pergunta,
            texto=str(valor),
            correta=(valor == resposta_correta)
        )


def criar_adicao(categoria):
    a = random.randint(1, 100)
    b = random.randint(1, 100)

    resposta = a + b

    pergunta = Pergunta.objects.create(
        categoria=categoria,
        texto_pergunta=f"Quanto é {a} + {b}?",
        nivel=1,
        pontuacao=10
    )

    criar_alternativas(pergunta, resposta)


def criar_subtracao(categoria):
    a = random.randint(1, 100)
    b = random.randint(1, a)

    resposta = a - b

    pergunta = Pergunta.objects.create(
        categoria=categoria,
        texto_pergunta=f"Quanto é {a} - {b}?",
        nivel=1,
        pontuacao=10
    )

    criar_alternativas(pergunta, resposta)


def criar_multiplicacao(categoria):
    a = random.randint(1, 20)
    b = random.randint(1, 20)

    resposta = a * b

    pergunta = Pergunta.objects.create(
        categoria=categoria,
        texto_pergunta=f"Quanto é {a} × {b}?",
        nivel=2,
        pontuacao=20
    )

    criar_alternativas(pergunta, resposta)


def criar_divisao(categoria):
    divisor = random.randint(1, 20)
    resposta = random.randint(1, 20)

    dividendo = divisor * resposta

    pergunta = Pergunta.objects.create(
        categoria=categoria,
        texto_pergunta=f"Quanto é {dividendo} ÷ {divisor}?",
        nivel=2,
        pontuacao=20
    )

    criar_alternativas(pergunta, resposta)


def popular_perguntas(quantidade=1000):
    categoria, criada = Categoria.objects.get_or_create(
        nome="Matemática",
        defaults={
            "descricao": "Questões de matemática envolvendo as quatro operações básicas."
        }
    )

    operacoes = [
        criar_adicao,
        criar_subtracao,
        criar_multiplicacao,
        criar_divisao
    ]

    for i in range(quantidade):
        operacao = random.choice(operacoes)
        operacao(categoria)

    print(f"{quantidade} perguntas criadas com sucesso!")