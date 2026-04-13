# MedMarket — Python/Flask

Versão Python do projeto MedMarket (originalmente criado no Lovable com React/TypeScript).

## Pré-requisitos

- Python 3.9+
- pip

## Como rodar no VS Code

### 1. Abra a pasta do projeto

```
Arquivo → Abrir Pasta → selecione a pasta `medconnect-hub`
```

### 2. Crie e ative o ambiente virtual

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Rode a aplicação

```bash
python app.py
```

Abra o navegador em: **http://localhost:5000**

---

## Estrutura do projeto

```
medconnect-hub/
├── app.py                  # Flask — rotas principais
├── requirements.txt        # Dependências Python
├── data/
│   └── mock_data.py        # Dados mockados (listings, chat, categorias)
├── templates/
│   ├── base.html           # Layout base (header, chat panel)
│   ├── index.html          # Página inicial
│   ├── listing_detail.html # Detalhe do anúncio
│   ├── auth.html           # Login / Cadastro
│   └── 404.html            # Página não encontrada
└── static/
    ├── css/
    │   └── style.css       # Estilos (tema escuro, idêntico ao original)
    └── js/
        └── main.js         # Interações (chat, menu mobile, busca)
```

## Funcionalidades

- ✅ Listagem de produtos e serviços médicos
- ✅ Filtro por categoria (barra superior)
- ✅ Busca em tempo real por título/descrição
- ✅ Página de detalhe do anúncio
- ✅ Chat global com envio de mensagens via API
- ✅ Login / Cadastro mockado (sessão Flask)
- ✅ Tema escuro fiel ao design original
- ✅ Layout responsivo (mobile + desktop)

## Próximos passos sugeridos

- Conectar a um banco de dados (SQLite com SQLAlchemy ou PostgreSQL)
- Implementar autenticação real (Flask-Login + bcrypt)
- Adicionar upload de imagens para os anúncios
- Criar painel do vendedor para gerenciar anúncios
