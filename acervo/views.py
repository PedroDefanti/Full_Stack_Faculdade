from django.shortcuts import render,redirect
from .models import Livro
from django.http import HttpResponse
from .forms import LivroForm
def inicio(request):
    return HttpResponse('Olá, acervo!')
    
    
    
def lista_livros(request):
    livros = Livro.objects.all() 
    return render(request, 'acervo/lista.html',{'livros': livros})



def novo_livro(request):
    if request.method == 'POST':
        form = LivroForm(request.POST)
        if form.is_valid():
            form.save() 
            return redirect('lista')
    else:
        form = LivroForm()
        return render(request, 'acervo/forms.html', {'form': form})

# Create your views here.
