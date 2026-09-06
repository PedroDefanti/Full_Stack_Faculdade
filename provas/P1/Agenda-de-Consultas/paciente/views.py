from django.shortcuts import render,redirect

from .forms import PacienteForm


def register(request):
    if request.method== "POST":
        form = PacienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = PacienteForm()
        
    return render(request,'register.html',{'form':form})




# Create your views here.
