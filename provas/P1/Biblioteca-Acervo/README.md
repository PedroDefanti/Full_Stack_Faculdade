## 🚀 Como Executar o Projeto Localmente

### 1. Acessar a Pasta do Projeto

```bash
cd provas
cd P1
cd Biblioteca-Acervo
```

### 2. Criar e Ativar o Ambiente Virtual (venv)

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar as Dependências

```bash
pip install -r requirements.txt
```

### 4. Executar as Migrações do Banco de Dados

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Criar um Usuário Administrador (Opcional)

```bash
python manage.py createsuperuser
```

### 6. Rodar o Servidor de Desenvolvimento

```bash
python manage.py runserver
```

Acesse o sistema no navegador pelo endereço:

👉 http://127.0.0.1:8000/