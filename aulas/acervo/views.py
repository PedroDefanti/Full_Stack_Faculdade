from django.shortcuts import render, redirect
from .models import Livro
from .forms import LivroForm

def lista_livros(request):
    livros = Livro.objects.all()
    return render(request, 'lista.html', {'livros': livros})
    
def novo_livro(request):
    if request.method == 'POST':
        form = LivroForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista')
    else:
        form = LivroForm()
    return render(request, 'forms.html', {'form': form}) 

def buscar_acervo(request):
    nome = request.GET.get("busca", "")
    tipo = request.GET.get("tipo", "")
    categoria = request.GET.get("categoria", "")
    
 
    livros = Livro.objects.all()
    
    if nome:
        livros = livros.filter(titulo__icontains=nome) 
        
    if tipo:
        livros = livros.filter(tipo=tipo) 
        
    if categoria:
        livros = livros.filter(categoria=categoria)
        
    context = {
        'acervos': livros, 
        'nome': nome,
        'tipo_selecionado': tipo,
        'categoria_selecionada': categoria,
        'tipos_choices': Livro.TIPO_ACERVO_CHOICES,        
        'categorias_choices': Livro.CATEGORIA_CHOICES     
    }
    return render(request, 'busca.html', context)