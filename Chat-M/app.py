import os
from functools import wraps

from flask import Flask, request, jsonify, session

from bot_logica import (
    processar_mensagem_chatbot,
    conectar_db,
    listar_categorias,
    listar_materiais_por_categoria,
    consultar_fornecedores,
)

# -----------------------------------------------------------------------------
# Configuração básica do Flask
# -----------------------------------------------------------------------------
app = Flask(__name__)

# SECRET_KEY: use variável de ambiente em produção (Fury). Ex.: SECRET_KEY=<valor forte>
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-only-secret-change-me"  # fallback para ambiente local
)

# API_KEY opcional para proteger os endpoints da API.
API_KEY = os.environ.get("API_KEY", "").strip()


def require_api_key(f):
    """Decorator simples para exigir X-API-KEY quando API_KEY estiver configurada."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if API_KEY:
            if request.headers.get("X-API-KEY") != API_KEY:
                return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# -----------------------------------------------------------------------------
# Rotas utilitárias / UI (opcional)
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    """
    Rota opcional para servir uma página simples.
    Se você não tiver templates, pode remover esta rota sem problemas.
    """
    # se o chat finalizou, limpa estado para não "travar" na próxima visita
    if session.get("chat_state", {}).get("stage") == "fim":
        session.pop("chat_state", None)
    return jsonify({
        "service": "Meli",
        "status": "ok",
        "message": "API do Meli online",
        "endpoints": ["/health", "/chat", "/categorias", "/materiais", "/fornecedores"],
    })


@app.route("/health")
def health():
    """Healthcheck para liveness/readiness do Fury."""
    return jsonify({"status": "ok"}), 200


# -----------------------------------------------------------------------------
# Endpoints de consulta (HTTP GET)
# -----------------------------------------------------------------------------
@app.route("/categorias", methods=["GET"])
@require_api_key
def categorias():
    """
    Retorna lista de categorias distintas.
    Resposta:
      { "categorias": ["elétricos", "ferramentas", ...] }
    """
    conn = conectar_db()
    cur = conn.cursor()
    try:
        cats = listar_categorias(cur)
        return jsonify({"categorias": cats})
    finally:
        conn.close()


@app.route("/materiais", methods=["GET"])
@require_api_key
def materiais():
    """
    Retorna materiais de uma categoria.
    Parâmetros:
      - categoria (querystring)
    Resposta:
      { "materiais": ["cabo 2.5mm", "tomada 10A", ...] }
    """
    categoria = (request.args.get("categoria") or "").strip()
    if not categoria:
        return jsonify({"error": "parametro 'categoria' é obrigatório"}), 400

    conn = conectar_db()
    cur = conn.cursor()
    try:
        mats = listar_materiais_por_categoria(cur, categoria)
        return jsonify({"materiais": mats})
    finally:
        conn.close()


@app.route("/fornecedores", methods=["GET"])
@require_api_key
def fornecedores():
    """
    Retorna top 3 fornecedores mais baratos para (material, estado).
    Parâmetros:
      - material (querystring)
      - estado  (querystring)  -> use nomes/UF esperados pela base
    Resposta:
      {
        "resultados": [
          {
            "fornecedor": "...",
            "estado": "...",
            "codigo_fornecedor": "...",
            "material": "...",
            "codigo_material": "...",
            "preco": 12.34
          },
          ...
        ]
      }
    """
    material = (request.args.get("material") or "").strip()
    estado = (request.args.get("estado") or "").strip()

    if not material or not estado:
        return jsonify({"error": "parametros 'material' e 'estado' são obrigatórios"}), 400

    conn = conectar_db()
    cur = conn.cursor()
    try:
        rows = consultar_fornecedores(cur, material, estado)
        resultados = [
            {
                "fornecedor": r[0],
                "estado": r[1],
                "codigo_fornecedor": r[2],
                "material": r[3],
                "codigo_material": r[4],
                "preco": float(r[5]),
            }
            for r in rows
        ]
        return jsonify({"resultados": resultados})
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Endpoint conversacional (mantém estado na sessão do Flask)
# -----------------------------------------------------------------------------
@app.route("/chat", methods=["POST"])
@require_api_key
def chat():
    """
    Endpoint conversacional único.
    Entrada: JSON { "message": "texto do usuario" }
    Saída:   { "reply": "...", "fim": true|false }
    - Mantém um dicionário 'chat_state' na sessão para conduzir o fluxo.
    - A lógica de estados/etapas está em processar_mensagem_chatbot().
    """
    data = request.get_json(silent=True) or {}
    mensagem = (data.get("message") or "").strip()

    if not mensagem:
        return jsonify({"error": "campo 'message' é obrigatório no corpo JSON"}), 400

    # Inicializa estado de chat se não existir
    if "chat_state" not in session or not isinstance(session.get("chat_state"), dict):
        session["chat_state"] = {
            "stage": "aguardando_categoria",
            "selected_category": None,
            "selected_material": None,
            "selected_state": None,
            "available_materials": [],
            "available_categories": [],
            "initial_greeting_sent": False,
        }

    # Se a conversa anterior marcou 'fim', reinicia estado ao receber nova mensagem
    if session["chat_state"].get("stage") == "fim":
        session["chat_state"] = {
            "stage": "aguardando_categoria",
            "selected_category": None,
            "selected_material": None,
            "selected_state": None,
            "available_materials": [],
            "available_categories": [],
            "initial_greeting_sent": False,
        }

    # Chama a lógica do bot
    reply, novo_estado = processar_mensagem_chatbot(mensagem, session["chat_state"])

    # Atualiza estado em sessão
    session["chat_state"] = novo_estado

    is_fim = (novo_estado.get("stage") == "fim")
    return jsonify({"reply": reply, "fim": is_fim})


# -----------------------------------------------------------------------------
# Execução local
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Para rodar localmente: python app.py
    port = int(os.environ.get("PORT", 5000))
    # Em produção (Fury), rode via gunicorn conforme o Dockerfile sugerido.
    app.run(host="0.0.0.0", port=port, debug=False)
