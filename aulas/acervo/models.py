from django.db import models

class Livro(models.Model):
    titulo = models.CharField(max_length=200)
    autor = models.CharField(max_length=100)
    ano = models.IntegerField()
    disponivel = models.BooleanField(default=True)
    

    def __str__(self):
        return self.titulo


class Acervo(models.Model):
    TIPO_ACERVO_CHOICES=[
        ("Digital","digital"),
        ("Fisico","fisico"),
    ]
    
    CATEGORIA_CHOICES=[
        ("000","'000 – Generalidades e Informação: Obras gerais, enciclopédias, jornais e biblioteconomia.'")
        ("100 ","'100  –  Filosofia e Psicologia: Ética, lógica e investigações sobre a mente humana.'")
        ("200 ","'200  – Religião e Teologia: Mitologia, teologia e estudos sobre crenças e religiões.'")
        ("300 ","'300  – Ciências Sociais e Direito: Política, economia, sociologia, educação e leis.'")
        ("400 ","'400  –  Linguística e Idiomas: Gramáticas, dicionários e estudos de línguas.'")
        ("500 ","'500  –  Ciências Puras (Exatas e Naturais): Matemática, física, química, biologia e astronomia.'")
        ("600 ","'600  – Ciências Aplicadas (Tecnologia): Medicina, engenharia, agricultura e administração.'")
        ("700 ","'700  – Artes e Recreação: Pintura, música, arquitetura, esportes e lazer.'")
        ("800  ","'800   – Literatura: Poesia, romances, contos, crônicas e crítica literária.'")
        ("900  ","'900   –  História e Geografia: Biografias, viagens e acontecimentos históricos'")
    ]
    
    nome=models.CharField(max_length=100)
    tipo=models.CharField(max_length=50,choices=TIPO_ACERVO_CHOICES)
    categoria=models.CharField(max_length=150,choices=CATEGORIA_CHOICES)
    
    def __str__(self):
        return f"Nome: {self.nome} Acervo do tipo {self.tipo} foi selecionado da categoria {self.categoria}"