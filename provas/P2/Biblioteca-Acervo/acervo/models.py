from datetime import date
from django.contrib.auth.models import User
from django.db import models

from core.models import DaOrganizacao


class Autor(DaOrganizacao):
    nome = models.CharField(max_length=150)

    def __str__(self):
        return self.nome


class Livro(DaOrganizacao):
    titulo = models.CharField(max_length=200)
    autor = models.ForeignKey(
        Autor, on_delete=models.CASCADE, related_name="livros"
    )
    ano = models.IntegerField()

    def __str__(self):
        return self.titulo

    # MUDOU: percorrem exemplares.all(), que usa o prefetch (sem N+1)
    @property
    def tem_disponivel(self):
        return any(e.status == "disponivel" for e in self.exemplares.all())

    @property
    def tem_emprestado(self):
        return any(e.status == "emprestado" for e in self.exemplares.all())

    @property
    def tem_manutencao(self):
        return any(e.status == "manutencao" for e in self.exemplares.all())


class Membro(DaOrganizacao):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    telefone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.usuario.username


class Exemplar(DaOrganizacao):
    STATUS_CHOICES = [
        ("disponivel", "Disponível"),
        ("emprestado", "Emprestado"),
        ("manutencao", "Em Manutenção"),
    ]
    livro = models.ForeignKey(
        Livro, on_delete=models.CASCADE, related_name="exemplares"
    )
    codigo_patrimonio = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="disponivel"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "codigo_patrimonio"],
                name="codigo_unico_por_org",
            ),
        ]

    def __str__(self):
        return f"{self.livro.titulo} ({self.codigo_patrimonio})"


class Emprestimo(DaOrganizacao):
    VALOR_MULTA_DIARIA = 2.00  # R$ 2,00 por dia de atraso

    exemplar = models.ForeignKey(Exemplar, on_delete=models.CASCADE)
    membro = models.ForeignKey(Membro, on_delete=models.CASCADE)
    data_emprestimo = models.DateField(auto_now_add=True)
    data_prevista_devolucao = models.DateField()
    data_devolucao = models.DateField(null=True, blank=True)
    multa_paga = models.BooleanField(default=False)

    class Meta:  # NOVO: filtros e agrupamentos do dashboard
        indexes = [
            models.Index(fields=["organizacao", "data_emprestimo"], name="emp_org_data_idx"),
            models.Index(fields=["data_emprestimo"], name="emp_data_idx"),
        ]

    @property
    def dias_atraso(self):
        if self.data_devolucao:
            data_fim = self.data_devolucao
        else:
            data_fim = date.today()

        if data_fim > self.data_prevista_devolucao:
            return (data_fim - self.data_prevista_devolucao).days
        return 0

    @property
    def valor_multa(self):
        return self.dias_atraso * self.VALOR_MULTA_DIARIA

    def __str__(self):
        return f"{self.exemplar} - {self.membro}"


class Reserva(DaOrganizacao):
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE)
    membro = models.ForeignKey(Membro, on_delete=models.CASCADE)
    data_reserva = models.DateTimeField(auto_now_add=True)
    atendida = models.BooleanField(default=False)

    class Meta:
        ordering = ["data_reserva"]

    def __str__(self):
        return f"Reserva: {self.livro.titulo} - {self.membro}"