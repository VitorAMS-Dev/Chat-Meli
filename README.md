# Meli

API em Python para o chat Meli, que consulta categorias, materiais e os melhores
fornecedores por estado usando Flask e SQLite.

## Executar

```powershell
cd Chat-M
python -m pip install flask
python app.py
```

A API ficará disponível em `http://127.0.0.1:5000`.

## Rotas

- `GET /health`: verifica se a API está disponível.
- `GET /categorias`: lista as categorias cadastradas.
- `GET /materiais?categoria=...`: lista materiais de uma categoria.
- `GET /fornecedores?material=...&estado=...`: retorna até três fornecedores.
- `POST /chat`: conduz a consulta conversacional do Meli.

O endpoint `/chat` recebe `{ "message": "texto" }`. Se `API_KEY` estiver
configurada, envie também o cabeçalho `X-API-KEY`.
