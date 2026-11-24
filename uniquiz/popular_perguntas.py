import os
import sys
from pathlib import Path

# Permite executar o script diretamente via `python uniquiz/popular_perguntas.py`
if __name__ == '__main__':
    BASE_DIR = Path(__file__).resolve().parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz.settings')
    import django
    django.setup()

from django.db import transaction

from uniquiz.models import Alternativa, Categoria, Pergunta, Usuario

PROFESSORES_FALLBACK = [
    ('Fernanda', 'Costa', 'fernanda.costa@uniquiz.edu.br'),
    ('Ricardo', 'Almeida', 'ricardo.almeida@uniquiz.edu.br'),
    ('Patrícia', 'Moura', 'patricia.moura@uniquiz.edu.br'),
    ('Eduardo', 'Nogueira', 'eduardo.nogueira@uniquiz.edu.br'),
    ('Juliana', 'Ribeiro', 'juliana.ribeiro@uniquiz.edu.br'),
    ('Marcelo', 'Teixeira', 'marcelo.teixeira@uniquiz.edu.br'),
]

BANCO_PERGUNTAS = {
    'Estruturas de Dados': {
        'descricao': 'Pilhas, filas, listas, árvores, tabelas hash e grafos aplicados à computação.',
        'questoes': [
            (
                'Qual estrutura de dados segue rigorosamente a política LIFO (Last In, First Out)?',
                1, 10,
                ['Fila (Queue)', 'Pilha (Stack)', 'Lista Encadeada Circular', 'Tabela Hash'],
                1,
            ),
            (
                'Qual estrutura de dados segue a política FIFO (First In, First Out)?',
                1, 10,
                ['Pilha (Stack)', 'Árvore Binária', 'Fila (Queue)', 'Heap Máximo'],
                2,
            ),
            (
                'Qual é a complexidade de tempo média para busca de uma chave em uma Tabela Hash bem distribuída?',
                1, 10,
                ['O(1)', 'O(log n)', 'O(n)', 'O(n log n)'],
                0,
            ),
            (
                'Em uma Árvore Binária de Busca (BST), qual percurso visita os elementos em ordem crescente?',
                2, 20,
                ['Pré-ordem (Pre-order)', 'Pós-ordem (Post-order)', 'Em-ordem (In-order)', 'Busca em Largura (BFS)'],
                2,
            ),
            (
                'Qual é a principal vantagem de uma Lista Encadeada sobre um vetor (array) estático?',
                2, 20,
                [
                    'Acesso aleatório por índice em O(1)',
                    'Inserções e remoções no início em O(1) sem realocação contígua',
                    'Menor consumo de memória por elemento',
                    'Melhor localidade de cache em todos os casos',
                ],
                1,
            ),
            (
                'Em um Min-Heap binário, onde está localizado o menor elemento da estrutura?',
                2, 20,
                ['Na folha mais à direita', 'Na raiz do heap', 'No meio do vetor', 'Em qualquer nó folha'],
                1,
            ),
            (
                'Qual propriedade garante que uma Árvore AVL permaneça balanceada após inserções e remoções?',
                3, 30,
                [
                    'Todos os nós folhas devem estar no mesmo nível exato',
                    'O fator de balanceamento de cada nó deve estar entre -1, 0 e +1',
                    'Cada nó pode ter no máximo 3 filhos',
                    'As chaves duplicadas são sempre inseridas na subárvore esquerda',
                ],
                1,
            ),
            (
                'Qual representação de grafo é mais eficiente em memória para grafos esparsos (poucas arestas em relação aos vértices)?',
                3, 30,
                ['Matriz de Adjacência', 'Lista de Adjacência', 'Matriz de Incidência completa', 'Vetor de Heap'],
                1,
            ),
        ],
    },
    'Algoritmos': {
        'descricao': 'Análise assintótica, ordenação, busca, grafos e paradigmas de resolução de problemas.',
        'questoes': [
            (
                'Qual pré-condição é obrigatória para aplicar o algoritmo de Busca Binária em um vetor?',
                1, 10,
                [
                    'O vetor deve possuir tamanho potência de 2',
                    'Os elementos devem estar previamente ordenados',
                    'Todos os elementos devem ser números positivos',
                    'O vetor não pode conter números pares',
                ],
                1,
            ),
            (
                'Qual é a complexidade de tempo da Busca Binária no pior caso em um vetor de n elementos?',
                1, 10,
                ['O(1)', 'O(n)', 'O(log n)', 'O(n²)'],
                2,
            ),
            (
                'Qual estrutura auxiliar é tipicamente usada na implementação iterativa da Busca em Largura (BFS)?',
                1, 10,
                ['Pilha', 'Fila', 'Árvore Rubro-Negra', 'Tabela Hash ordenada'],
                1,
            ),
            (
                'Qual algoritmo de ordenação utiliza a estratégia "Dividir e Conquistar" e garante complexidade O(n log n) mesmo no pior caso?',
                2, 20,
                ['Bubble Sort', 'Insertion Sort', 'Merge Sort', 'Selection Sort'],
                2,
            ),
            (
                'Em qual cenário o Quick Sort clássico (pivô sempre no primeiro elemento) degrada para complexidade O(n²)?',
                2, 20,
                [
                    'Quando o vetor possui elementos aleatórios',
                    'Quando o vetor já está ordenado ou inversamente ordenado',
                    'Quando o tamanho do vetor é ímpar',
                    'Quando todos os números são inteiros positivos',
                ],
                1,
            ),
            (
                'Qual algoritmo encontra o caminho mínimo a partir de uma origem em grafos com pesos de aresta não negativos?',
                2, 20,
                ['Algoritmo de Dijkstra', 'Algoritmo de Kruskal', 'Ordenação Topológica', 'Busca em Profundidade (DFS)'],
                0,
            ),
            (
                'Qual característica define um problema adequado para Programação Dinâmica?',
                3, 30,
                [
                    'Subproblemas sobrepostos e subestrutura ótima',
                    'Ausência total de recursão possível',
                    'Complexidade sempre linear O(n)',
                    'Uso exclusivo de escolhas gulosas locais sem revisão',
                ],
                0,
            ),
            (
                'Qual é o objetivo do algoritmo de Kruskal em grafos ponderados conexos?',
                3, 30,
                [
                    'Encontrar componentes fortemente conexos',
                    'Construir uma Árvore Geradora Mínima (MST)',
                    'Detectar o maior fluxo em uma rede',
                    'Colorir o grafo com o número mínimo de cores',
                ],
                1,
            ),
        ],
    },
    'Hardware': {
        'descricao': 'Arquitetura de computadores, organização de memória, processadores e lógica digital.',
        'questoes': [
            (
                'Qual unidade interna do processador executa operações aritméticas e lógicas como soma, subtração e AND?',
                1, 10,
                ['Unidade Lógica e Aritmética (ULA/ALU)', 'Controlador DMA', 'Barramento PCIe', 'Memória ROM'],
                0,
            ),
            (
                'Qual nível da hierarquia de memória possui a menor latência de acesso por estar integrado diretamente ao núcleo da CPU?',
                1, 10,
                ['Registradores da CPU', 'Memória RAM DDR5', 'SSD NVMe', 'Cache L3 compartilhada'],
                0,
            ),
            (
                'Na lógica digital, qual porta lógica retorna saída 1 somente quando TODAS as suas entradas são 1?',
                1, 10,
                ['OR', 'XOR', 'AND', 'NOR'],
                2,
            ),
            (
                'Qual característica central define a Arquitetura de Von Neumann?',
                2, 20,
                [
                    'Instruções e dados compartilham a mesma memória e barramento principal',
                    'Uso obrigatório de múltiplos núcleos físicos',
                    'Separação física permanente entre memória de dados e de instruções',
                    'Execução exclusiva de código interpretado em nuvem',
                ],
                0,
            ),
            (
                'Qual é a função principal da Memória Cache entre a CPU e a memória RAM?',
                2, 20,
                [
                    'Armazenar arquivos permanentemente quando o computador é desligado',
                    'Reduzir o tempo médio de acesso explorando localidade temporal e espacial',
                    'Substituir completamente a necessidade de registradores',
                    'Converter sinais digitais em sinais analógicos',
                ],
                1,
            ),
            (
                'O que significa a técnica de Pipeline em processadores modernos?',
                2, 20,
                [
                    'Compactação automática de arquivos no disco rígido',
                    'Sobreposição da execução de diferentes estágios de múltiplas instruções simultaneamente',
                    'Desligamento de núcleos ociosos para economia de energia',
                    'Criptografia em tempo real da memória RAM',
                ],
                1,
            ),
            (
                'O que ocorre durante um "Page Fault" (falta de página) em um sistema com Memória Virtual?',
                3, 30,
                [
                    'A CPU queima permanentemente um setor da cache L1',
                    'O sistema operacional precisa carregar a página ausente da memória secundária para a RAM',
                    'O barramento de dados entra em curto-circuito lógico',
                    'O compilador recompila o binário em tempo de execução',
                ],
                1,
            ),
            (
                'Qual problema de desempenho em pipelines ocorre quando uma instrução depende do resultado de uma instrução anterior ainda não concluída?',
                3, 30,
                ['Hazard de Dados (Data Hazard)', 'Fragmentação Externa', 'Thrashing de Disco', 'Deadlock de Impressão'],
                0,
            ),
        ],
    },
    'Banco de Dados': {
        'descricao': 'Modelagem relacional, SQL, normalização, índices, transações e propriedades ACID.',
        'questoes': [
            (
                'Na sigla ACID de transações em bancos de dados, o que garante a propriedade de Atomicidade?',
                1, 10,
                [
                    'Os dados são compactados automaticamente em disco',
                    'Todas as operações da transação são concluídas com sucesso ou todas são revertidas (tudo ou nada)',
                    'Múltiplas tabelas compartilham a mesma chave primária',
                    'Consultas SELECT nunca utilizam índices',
                ],
                1,
            ),
            (
                'Qual comando SQL é usado para desfazer todas as alterações feitas na transação corrente em caso de erro?',
                1, 10,
                ['COMMIT', 'ROLLBACK', 'TRUNCATE', 'ALTER'],
                1,
            ),
            (
                'Qual é o papel principal de uma Chave Estrangeira (FOREIGN KEY) em um banco relacional?',
                1, 10,
                [
                    'Ordenar alfabeticamente os resultados de uma consulta',
                    'Garantir integridade referencial entre registros de duas tabelas',
                    'Criptografar senhas de usuários no banco',
                    'Aumentar o limite de caracteres de campos VARCHAR',
                ],
                1,
            ),
            (
                'Qual cláusula SQL é utilizada para filtrar grupos resultantes de uma agregação com GROUP BY?',
                2, 20,
                ['WHERE', 'HAVING', 'ORDER BY', 'DISTINCT'],
                1,
            ),
            (
                'Qual estrutura de dados é a mais amplamente utilizada por SGBDs relacionais para implementar índices ordenados em disco?',
                2, 20,
                ['B-Tree / B+Tree', 'Pilha encadeada', 'Grafo bipartido', 'Fila circular'],
                0,
            ),
            (
                'Uma tabela está na Primeira Forma Normal (1FN) quando:',
                2, 20,
                [
                    'Não possui nenhuma chave estrangeira',
                    'Todos os atributos contêm apenas valores atômicos (indivisíveis), sem grupos repetitivos',
                    'Possui no máximo três colunas',
                    'Todos os campos aceitam valores nulos',
                ],
                1,
            ),
            (
                'Qual anomalia de concorrência ocorre quando uma transação lê dados modificados por outra transação que ainda não realizou COMMIT?',
                3, 30,
                ['Leitura Suja (Dirty Read)', 'Deadlock de Rede', 'Overflow de Buffer', 'Perda de Índice'],
                0,
            ),
            (
                'Qual propriedade ACID assegura que, após o COMMIT confirmado, os dados permanecem preservados mesmo em caso de queda de energia?',
                3, 30,
                ['Isolamento', 'Durabilidade', 'Consistência', 'Atomicidade'],
                1,
            ),
        ],
    },
    'Sistemas Distribuídos': {
        'descricao': 'Concorrência distribuída, tolerância a falhas, consistência, replicação e comunicação em rede.',
        'questoes': [
            (
                'Segundo o Teorema CAP, durante uma partição de rede (P) em um sistema distribuído, qual escolha precisa ser priorizada?',
                1, 10,
                [
                    'Entre Consistência (C) e Disponibilidade (A)',
                    'Entre Criptografia e Compressão',
                    'Entre Latência de CPU e Tamanho de Disco',
                    'Entre HTTP e SMTP',
                ],
                0,
            ),
            (
                'Qual é a função principal de um Balanceador de Carga (Load Balancer) em sistemas distribuídos?',
                1, 10,
                [
                    'Compilar o código-fonte em linguagem de máquina',
                    'Distribuir requisições entre múltiplos servidores para aumentar escalabilidade e disponibilidade',
                    'Substituir o banco de dados relacional por arquivos CSV',
                    'Bloquear permanentemente todo o tráfego HTTPS',
                ],
                1,
            ),
            (
                'O que significa dizer que uma operação distribuída ou endpoint HTTP é idempotente?',
                1, 10,
                [
                    'Só pode ser executado uma única vez na história do sistema',
                    'Executar a operação múltiplas vezes produz o mesmo efeito final de executá-la uma única vez',
                    'Sempre retorna dados diferentes a cada chamada',
                    'Dispensa qualquer tipo de autenticação',
                ],
                1,
            ),
            (
                'Qual protocolo/framework de chamada de procedimento remoto utiliza HTTP/2 e Protocol Buffers para comunicação eficiente entre serviços?',
                2, 20,
                ['gRPC', 'FTP', 'Telnet', 'POP3'],
                0,
            ),
            (
                'Para que servem os Relógios Lógicos de Lamport em sistemas distribuídos?',
                2, 20,
                [
                    'Sincronizar o fuso horário local de monitores',
                    'Estabelecer uma ordenação causal (happened-before) entre eventos sem depender de relógios físicos perfeitos',
                    'Medir a temperatura do processador em nós remotos',
                    'Gerar chaves públicas RSA automaticamente',
                ],
                1,
            ),
            (
                'Qual é o objetivo de algoritmos de consenso como Raft e Paxos?',
                2, 20,
                [
                    'Compactar imagens em servidores de mídia',
                    'Permitir que múltiplos nós concordem sobre um estado ou sequência de valores mesmo diante de falhas',
                    'Renderizar interfaces HTML no navegador do cliente',
                    'Converter consultas SQL em JSON',
                ],
                1,
            ),
            (
                'Qual padrão arquitetural evita falhas em cascata interrompendo temporariamente chamadas a um serviço remoto instável?',
                3, 30,
                ['Circuit Breaker', 'Singleton', 'Observer', 'Builder'],
                0,
            ),
            (
                'Em transações distribuídas envolvendo múltiplos bancos independentes, qual protocolo clássico coordena as fases de "prepare" e "commit"?',
                3, 30,
                ['Two-Phase Commit (2PC)', 'Round-Robin DNS', 'Stop-and-Wait ARQ', 'Token Ring'],
                0,
            ),
        ],
    },
    'Matemática': {
        'descricao': 'Cálculo, álgebra linear, matemática discreta, lógica proposicional e probabilidade.',
        'questoes': [
            (
                'Qual é o valor de log₂(64)?',
                1, 10,
                ['4', '5', '6', '8'],
                2,
            ),
            (
                'Na lógica proposicional, se P é Verdadeiro e Q é Falso, qual é o valor lógico da implicação P → Q?',
                1, 10,
                ['Verdadeiro', 'Falso', 'Indeterminado', 'Equivalente a P ∨ Q'],
                1,
            ),
            (
                'Qual é o resto da divisão (aritmética modular) de 29 mod 6?',
                1, 10,
                ['1', '3', '5', '4'],
                2,
            ),
            (
                'Qual é a derivada de f(x) = 3x² + 5x - 7 em relação a x?',
                2, 20,
                ['6x + 5', '3x + 5', '6x² + 5', 'x³ + 5'],
                0,
            ),
            (
                'De quantas maneiras distintas podemos escolher 2 alunos em um grupo de 6 alunos (sem importar a ordem)?',
                2, 20,
                ['12', '15', '30', '36'],
                1,
            ),
            (
                'Qual é o determinante da matriz 2×2 [[4, 2], [3, 5]]?',
                2, 20,
                ['14', '26', '8', '20'],
                0,
            ),
            (
                'Qual é a negação lógica equivalente à proposição ¬(P ∧ Q) pelas Leis de De Morgan?',
                3, 30,
                ['¬P ∧ ¬Q', '¬P ∨ ¬Q', 'P ∨ ¬Q', 'P → Q'],
                1,
            ),
            (
                'Ao lançar dois dados honestos de 6 faces, qual é a probabilidade de a soma dos resultados ser igual a 7?',
                3, 30,
                ['1/12', '1/6', '1/9', '1/3'],
                1,
            ),
        ],
    },
}


def _obter_professores():
    """Retorna professores existentes no banco (credencial=2) ou cria um conjunto inicial."""
    professores = list(Usuario.objects.filter(credencial=2).order_by('date_joined', 'id'))
    if professores:
        return professores

    criados = []
    for primeiro, ultimo, email in PROFESSORES_FALLBACK:
        prof, _ = Usuario.objects.get_or_create(
            username=email,
            defaults={
                'email': email,
                'first_name': primeiro,
                'last_name': ultimo,
                'credencial': 2,
                'curso': 'Engenharia de Computação',
            },
        )
        if not prof.has_usable_password():
            prof.set_password('ProfQuiz123!')
            prof.save()
        criados.append(prof)
    return criados


def popular_perguntas():
    """Popula categorias, perguntas e alternativas de forma idempotente e atômica (ACID)."""
    criadas = 0
    existentes = 0
    autores_usados = set()

    with transaction.atomic():
        professores = _obter_professores()
        indice_prof = 0

        for nome_categoria, dados in BANCO_PERGUNTAS.items():
            categoria, _ = Categoria.objects.get_or_create(
                nome=nome_categoria,
                defaults={'descricao': dados['descricao']},
            )

            for texto, nivel, pontuacao, alternativas, correta_idx in dados['questoes']:
                autor = professores[indice_prof % len(professores)]
                indice_prof += 1

                pergunta_existente = Pergunta.objects.filter(
                    categoria=categoria,
                    texto_pergunta=texto,
                ).first()

                if pergunta_existente is not None:
                    if pergunta_existente.autor_id is None:
                        pergunta_existente.autor = autor
                        pergunta_existente.save(update_fields=['autor'])
                    existentes += 1
                    autores_usados.add(pergunta_existente.autor_id)
                    continue

                pergunta = Pergunta.objects.create(
                    categoria=categoria,
                    autor=autor,
                    texto_pergunta=texto,
                    nivel=nivel,
                    pontuacao=pontuacao,
                )

                Alternativa.objects.bulk_create([
                    Alternativa(
                        pergunta=pergunta,
                        texto=alt_texto,
                        correta=(idx == correta_idx),
                    )
                    for idx, alt_texto in enumerate(alternativas)
                ])

                criadas += 1
                autores_usados.add(autor.id)

    resumo = {
        'criadas': criadas,
        'existentes': existentes,
        'total_perguntas': Pergunta.objects.count(),
        'total_alternativas': Alternativa.objects.count(),
        'total_categorias': Categoria.objects.count(),
        'total_professores_autores': len(autores_usados),
    }
    print(
        f"População concluída! {resumo['criadas']} perguntas criadas "
        f"({resumo['existentes']} já existentes) em {resumo['total_categorias']} categorias, "
        f"distribuídas entre {resumo['total_professores_autores']} professores diferentes "
        f"({resumo['total_alternativas']} alternativas no total)."
    )
    return resumo


if __name__ == '__main__':
    popular_perguntas()
