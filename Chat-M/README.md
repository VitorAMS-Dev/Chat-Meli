# Meli

Este diretório contém a API do chat Meli. O serviço usa Flask para expor o chat
e consultas ao banco SQLite `base_chatbot2.db`.

## Requisitos

- Python 3.10 ou mais recente
- Flask

## Execução local

```powershell
python -m pip install flask
python app.py
```

Teste a disponibilidade:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
```

## Uso do chat

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/chat `
  -ContentType 'application/json' `
  -Body '{"message":"oi"}'
```

O Meli conduz a conversa por categoria, material e estado e retorna os três
fornecedores mais baratos encontrados. A sessão do Flask mantém o estado de cada
conversa. Para proteger a API, defina `API_KEY` e envie o valor no cabeçalho
`X-API-KEY`.

## Endpoints de consulta

- `GET /categorias`
- `GET /materiais?categoria=<categoria>`
- `GET /fornecedores?material=<material>&estado=<estado>`
- `GET /health`
- `POST /chat`
