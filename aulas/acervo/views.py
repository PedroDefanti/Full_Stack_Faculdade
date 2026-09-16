from django.shortcuts import render
from .models import Livro,Acervo

def lista_livros(request):
    livros = Livro.objects.all() # busca no banco
    return render(
        request, 'acervo/lista.html',
        {'livros': livros} # envia ao template
    )
    
def novo_livro(request):
    if request.method == 'POST':
        form = LivroForm(request.POST)
        if form.is_valid():
            form.save() # grava no banco
            return redirect('lista')
    else:
        form = LivroForm()
    return render(request, 'acervo/form.html', {'form': form})   


def Acervo(request):
    nome=request.GET.get("busca","")
    tipo=request.GET.get("tipo","")
    categoria=request.GET.get("categoria","")
    
    acervo=Acervo.objects.all()
    
    if nome:
        acervo=acervo.filter(nome__icontains=nome)
        
    if tipo:
        acervo=acervo.filter(tipo_acervo=tipo)
        
    if categoria:
        acervo=acervo.filter(categoria=categoria)
        
    
    context={
        'produto':acervo,
        'nome':nome,
        'tipo':tipo,
        'categoria':categoria
    }
    return render(request,'busca.html',context)