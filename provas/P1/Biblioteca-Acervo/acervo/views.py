from django.shortcuts import render,redirect,get_object_or_404
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
    
    
    
def editar_livro(request,id):
    livro =get_object_or_404(Livro,id=id)
    if request.method =="POST":
        form = LivroForm(request.POST,instance=livro)
        if form.is_valid():
            form.save()
            return(redirect('lista'))
        else:
            form = LivroForm(instance=livro)
        return render(request,'editar.html',{"form":form})
    
    
def remover_livro(request,id):
    livro=get_object_or_404(Livro,id=id)
    if request.method=="POST":
        livro.delete()
        return(redirect("lista",{"livro":livro}))
# Create your views here.