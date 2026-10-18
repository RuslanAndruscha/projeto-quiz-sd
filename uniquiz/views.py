from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model

Usuario = get_user_model()


def home(request):
    return render(request, 'uniquiz/home.html')


def login(request):
    return render(request, 'uniquiz/login.html')


def cadastro(request):
    if request.method == 'POST':
        nome = request.POST.get('primeiro_nome', '').strip()
        sobrenome = request.POST.get('ultimo_nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        senha = request.POST.get('senha', '')
        confirmar_senha = request.POST.get('confirmar_senha', '')
        credencial = request.POST.get('credencial', '')

        valores = {
            'primeiro_nome': nome,
            'ultimo_nome': sobrenome,
            'email': email,
            'credencial': credencial,
        }

        erro = None

        if not nome or not sobrenome or not email or not senha or not confirmar_senha:
            erro = 'Preencha todos os campos.'
        elif senha != confirmar_senha:
            erro = 'As senhas não coincidem.'
        elif len(senha) < 8:
            erro = 'A senha precisa ter pelo menos 8 caracteres.'
        elif credencial not in ('1', '2'):
            erro = 'Selecione um perfil válido.'
        elif Usuario.objects.filter(email__iexact=email).exists():
            erro = 'Este e-mail já está cadastrado.'

        if erro:
            request.session['cadastro_valores'] = valores
            request.session['cadastro_erro'] = erro
            return redirect('uniquiz:cadastro')

        username = email

        if Usuario.objects.filter(username__iexact=username).exists():
            messages.error(request, 'Já existe uma conta com este e-mail.')
            return redirect('uniquiz:cadastro')

        Usuario.objects.create_user(
            username=username,
            first_name=nome,
            last_name=sobrenome,
            email=email,
            password=senha,
            credencial=int(credencial),
        )

        messages.success(request, 'Cadastro realizado com sucesso!')
        return redirect('uniquiz:cadastro')

    valores = request.session.pop('cadastro_valores', {})
    erro = request.session.pop('cadastro_erro', None)

    if erro:
        messages.error(request, erro)

    return render(request, 'uniquiz/cadastro.html', {'valores': valores})