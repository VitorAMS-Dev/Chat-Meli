import sqlite3
import os

def conectar_db():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "base_chatbot2.db")
    return sqlite3.connect(db_path)

def listar_categorias(cursor):
    cursor.execute("SELECT DISTINCT categoria FROM materiais")
    return [linha[0] for linha in cursor.fetchall()]

def listar_materiais_por_categoria(cursor, categoria):
    cursor.execute("SELECT nome FROM materiais WHERE LOWER(categoria) = LOWER(?)", (categoria,))
    return [linha[0] for linha in cursor.fetchall()]

def consultar_fornecedores(cursor, material, estado):
    query = """
    SELECT f.nome, f.estado, f.codigo, m.nome, m.codigo, p.valor
    FROM precos p
    JOIN fornecedores f ON f.id = p.fornecedor_id
    JOIN materiais m ON m.id = p.material_id
    WHERE LOWER(m.nome) = LOWER(?) AND LOWER(f.estado) = LOWER(?)
    ORDER BY p.valor ASC
    LIMIT 3
    """
    cursor.execute(query, (material, estado))
    return cursor.fetchall()

# Função Principal para a Lógica do Bot 
def processar_mensagem_chatbot(mensagem_usuario, chat_state):
    conn = conectar_db()
    cursor = conn.cursor()

    resposta_bot = ""
    mensagem_usuario_lower = mensagem_usuario.lower().strip()

    current_stage = chat_state.get('stage', 'aguardando_categoria')
    selected_category = chat_state.get('selected_category')
    selected_material = chat_state.get('selected_material')
    selected_state = chat_state.get('selected_state') 
    available_materials = chat_state.get('available_materials', [])
    available_categories = chat_state.get('available_categories', [])
    
    mg_subdivisions = ["minas gerais (betim)", "minas gerais (extrema)"]
    chat_state['mg_subdivisions'] = mg_subdivisions

    # Mapeamento de estados
    mapeamento_estados = {
        "sp": "são paulo", "são paulo": "são paulo",
        "ba": "bahia", "bahia": "bahia",
        "rj": "rio de janeiro", "rio de janeiro": "rio de janeiro",
        "mg": "minas gerais", # Genérico para desambiguação
        "minas gerais": "minas gerais", # Genérico para desambiguação
        "minas gerais (extrema)": "minas gerais (extrema)",
        "extrema": "minas gerais (extrema)",
        "minas gerais (betim)": "minas gerais (betim)",
        "betim": "minas gerais (betim)",
        "rs": "rio grande do sul", "rio grande do sul": "rio grande do sul",
        "sc": "santa catarina", "santa catarina": "santa catarina",
        "df": "distrito federal", "distrito federal": "distrito federal",
        "pe": "pernambuco", "pernambuco": "pernambuco",
        "ce": "ceará", "ceara": "ceará",
    }
    
    estados_conhecidos_db = [s[0].lower() for s in cursor.execute("SELECT DISTINCT estado FROM fornecedores").fetchall()]
    for estado_db in estados_conhecidos_db:
        if estado_db not in mapeamento_estados:
            mapeamento_estados[estado_db] = estado_db

    if current_stage == 'fim':
        conn.close()
        return chat_state.get('last_reply', "Até logo!"), chat_state

    # Lógica para reiniciar a conversa a qualquer momento
    if "reiniciar" in mensagem_usuario_lower or "começar de novo" in mensagem_usuario_lower:
        resposta_bot = "Entendido! Vamos reiniciar a conversa."
        chat_state['stage'] = 'aguardando_categoria'
        chat_state['selected_category'] = None
        chat_state['selected_material'] = None
        chat_state['selected_state'] = None
        chat_state['available_materials'] = []
        chat_state['available_categories'] = []
        chat_state['initial_greeting_sent'] = True # para evitar saudação duplicada
        
        categorias_atuais = listar_categorias(cursor)
        if categorias_atuais:
            resposta_bot += "\n\nPor favor, escolha uma categoria:"
            resposta_bot += "\n"
            for i, cat in enumerate(categorias_atuais):
                resposta_bot += f"\n{i+1}. {cat.capitalize()}"
            chat_state['available_categories'] = [c.lower() for c in categorias_atuais]
        else:
            resposta_bot += "\n\nNão encontrei categorias disponíveis no momento."
        conn.close()
        return resposta_bot, chat_state

    if current_stage == 'finalizou_consulta':
        if "sim" in mensagem_usuario_lower:
            chat_state['stage'] = 'aguardando_categoria'
            chat_state['selected_category'] = None
            chat_state['selected_material'] = None
            chat_state['selected_state'] = None
            chat_state['available_materials'] = []
            chat_state['available_categories'] = []
            chat_state['initial_greeting_sent'] = True # para evitar saudação duplicada
            
            # A resposta para "sim" será apenas a instrução para a nova consulta
            resposta_bot = "Certo! Vamos começar uma nova consulta."
            categorias = listar_categorias(cursor)
            if categorias:
                resposta_bot += "\n\nPor favor, escolha uma categoria:"
                resposta_bot += "\n"
                for i, cat in enumerate(categorias):
                    resposta_bot += f"\n{i+1}. {cat.capitalize()}"
                chat_state['available_categories'] = [c.lower() for c in categorias]
            else:
                resposta_bot += "\n\nNão encontrei categorias disponíveis no momento."
            
            conn.close()
            return resposta_bot, chat_state 

        elif "não" in mensagem_usuario_lower:
            resposta_bot = "Obrigado por usar o Meli! Até mais 👋"
            chat_state['stage'] = 'fim'
            chat_state['last_reply'] = resposta_bot
            conn.close()
            return resposta_bot, chat_state

        else:
            resposta_bot = "Não entendi sua resposta. Por favor, digite 'sim' para nova consulta ou 'não' para encerrar."
            conn.close()
            return resposta_bot, chat_state

    # Lógica para especificação de Minas Gerais Betim/Extrema
    elif current_stage == 'aguardando_especificacao_mg':
        especificacao_encontrada = None
        if "betim" in mensagem_usuario_lower:
            especificacao_encontrada = "minas gerais (betim)"
        elif "extrema" in mensagem_usuario_lower:
            especificacao_encontrada = "minas gerais (extrema)"
        
        if especificacao_encontrada:
            chat_state['selected_state'] = especificacao_encontrada
            
            material_encontrado = chat_state.get('selected_material')
            if material_encontrado:
                resultados = consultar_fornecedores(cursor, material_encontrado, especificacao_encontrada)
                if resultados:
                    resposta_bot = "Aqui estão os melhores fornecedores:\n\n"
                    for i, r in enumerate(resultados, 1):
                        resposta_bot += f"{i}. {r[0]} – R$ {r[5]:.4f} (Cod Forn: {r[2]}, Cod Mat: {r[4]})\n"
                    resposta_bot += "\n\n🎯 Deseja fazer outra consulta? Digite 'sim' ou 'não'."
                    chat_state['stage'] = 'finalizou_consulta'
                else:
                    resposta_bot = "Nenhum fornecedor encontrado para esse insumo em " + especificacao_encontrada.capitalize() + "."
                    resposta_bot += "\n\nPor favor, tente outro estado ou diga 'reiniciar' para uma nova consulta."
                    chat_state['stage'] = 'aguardando_estado'
            else:
                resposta_bot = "Houve um erro. Por favor, reinicie a conversa."
                chat_state['stage'] = 'aguardando_categoria'
        else:
            resposta_bot = "Não entendi a sua especificação. Por favor, digite 'Betim' ou 'Extrema'."
            chat_state['stage'] = 'aguardando_especificacao_mg' 

    # Lógica principal baseada nos demais estágios da conversa
    elif current_stage == 'aguardando_categoria': # Responsável em apresentar a lista de categorias
        if chat_state.get('initial_greeting_sent', False) == False:
            resposta_bot = "Olá! Sou o Meli, vou te ajudar a encontrar o melhor fornecedor para sua negociação."
            chat_state['initial_greeting_sent'] = True
        
        elif "olá" in mensagem_usuario_lower or "oi" in mensagem_usuario_lower or "ola" in mensagem_usuario_lower:
             resposta_bot = "Olá! Sou o Meli, vou te ajudar a encontrar o melhor fornecedor para sua negociação."
  
        if "escolha uma categoria" not in resposta_bot.lower():
            resposta_bot += "\n\nPara começar, por favor, escolha uma categoria:"
            resposta_bot += "\n" # Quebra de linha
            
        categorias = listar_categorias(cursor)
        if categorias:
            for i, cat in enumerate(categorias):
                resposta_bot += f"\n{i+1}. {cat.capitalize()}"
            chat_state['stage'] = 'aguardando_escolha_categoria'
            chat_state['available_categories'] = [c.lower() for c in categorias]
        else:
            resposta_bot = "Não encontrei categorias disponíveis no momento. Por favor, tente novamente mais tarde."
            chat_state['stage'] = 'aguardando_categoria'
    
    elif current_stage == 'aguardando_escolha_categoria': # Responsável pela lógica do input categoria do user
        categorias = chat_state.get('available_categories', [])
        
        categoria_encontrada = None
        if mensagem_usuario_lower.isdigit():
            indice = int(mensagem_usuario_lower) - 1
            if 0 <= indice < len(categorias):
                categoria_encontrada = categorias[indice]
        else:
            for cat in categorias:
                if mensagem_usuario_lower in cat:
                    categoria_encontrada = cat
                    break
        
        if categoria_encontrada:
            selected_category = categoria_encontrada
            chat_state['selected_category'] = selected_category
            
            materiais = listar_materiais_por_categoria(cursor, selected_category)
            if materiais:
                available_materials = [m.lower() for m in materiais]
                chat_state['available_materials'] = available_materials
                resposta_bot = f"Ótimo! Você escolheu a categoria '{selected_category.capitalize()}'. Agora, qual insumo você procura?"
                resposta_bot += "\n"
                for i, mat in enumerate(materiais):
                    resposta_bot += f"\n{i+1}. {mat.capitalize()}"
                chat_state['stage'] = 'aguardando_escolha_material'
            else:
                resposta_bot = f"Não encontrei insumos para a categoria '{selected_category.capitalize()}'. Por favor, escolha outra categoria."
                chat_state['stage'] = 'aguardando_categoria'
                categorias_atuais = listar_categorias(cursor)
                if categorias_atuais:
                    resposta_bot += "\n\nPor favor, escolha uma categoria:"
                    resposta_bot += "\n"
                    for i, cat in enumerate(categorias_atuais):
                        resposta_bot += f"\n{i+1}. {cat.capitalize()}"
                    chat_state['available_categories'] = [c.lower() for c in categorias_atuais]
                else:
                    resposta_bot += "\n\nNão encontrei categorias disponíveis no momento."
        else:
            resposta_bot = "Não entendi sua escolha de categoria. Por favor, digite o número ou o nome da categoria que deseja."
            chat_state['stage'] = 'aguardando_escolha_categoria' 

    elif current_stage == 'aguardando_escolha_material': # Responsável pela lógica do input material do user
        materiais = chat_state.get('available_materials', [])
        material_encontrado = None

        if mensagem_usuario_lower.isdigit():
            indice = int(mensagem_usuario_lower) - 1
            if 0 <= indice < len(materiais):
                material_encontrado = materiais[indice]
        else:
            for mat in materiais:
                if mensagem_usuario_lower in mat:
                    material_encontrado = mat
                    break

        if material_encontrado:
            chat_state['selected_material'] = material_encontrado
            resposta_bot = f"Você escolheu '{material_encontrado.capitalize()}'. Agora, para qual estado você precisa consultar?"
            resposta_bot += "\nEx: SP, São Paulo, BA, Bahia, etc."
            chat_state['stage'] = 'aguardando_estado'
        else:
            resposta_bot = "Não entendi o insumo que você escolheu. Por favor, digite o número ou o nome do insumo na lista."
            chat_state['stage'] = 'aguardando_escolha_material' 

    elif current_stage == 'aguardando_estado': # Responsável pela lógica do input estado do user
        material_encontrado = chat_state.get('selected_material')
        estado_encontrado = None

        if "betim" in mensagem_usuario_lower:
            estado_encontrado = "minas gerais (betim)"
        elif "extrema" in mensagem_usuario_lower:
            estado_encontrado = "minas gerais (extrema)"
        else:
            for est_key, est_full in mapeamento_estados.items():
                if est_key in mensagem_usuario_lower:
                    estado_encontrado = est_full
                    break
        
        if estado_encontrado == "minas gerais":
            has_betim = "minas gerais (betim)" in estados_conhecidos_db
            has_extrema = "minas gerais (extrema)" in estados_conhecidos_db

            if has_betim and has_extrema:
                resposta_bot = "Para Minas Gerais, você se refere a Betim ou Extrema?"
                chat_state['stage'] = 'aguardando_especificacao_mg'
                conn.close()
                return resposta_bot, chat_state
            elif has_betim:
                estado_encontrado = "minas gerais (betim)"
            elif has_extrema:
                estado_encontrado = "minas gerais (extrema)"

        if material_encontrado and estado_encontrado:
            resultados = consultar_fornecedores(cursor, material_encontrado, estado_encontrado)
            if resultados:
                resposta_bot = "Aqui estão os melhores fornecedores:\n\n"
                for i, r in enumerate(resultados, 1):
                    resposta_bot += f"{i}. {r[0]} – R$ {r[5]:.4f} (Cod Forn: {r[2]}, Cod Mat: {r[4]})\n"
                resposta_bot += "\n\n🎯 Deseja fazer outra consulta? Digite 'sim' ou 'não'."
                chat_state['stage'] = 'finalizou_consulta'
            else:
                resposta_bot = "Nenhum fornecedor encontrado para esse insumo em " + estado_encontrado.capitalize() + "."
                resposta_bot += "\n\nPor favor, tente outro estado ou diga 'reiniciar' para uma nova consulta."
                chat_state['stage'] = 'aguardando_estado'
        else:
            resposta_bot = "Não consegui identificar o estado. Por favor, digite o nome completo ou a sigla do estado (Ex: SP, São Paulo)."
            chat_state['stage'] = 'aguardando_estado' 
            
    conn.close()
    return resposta_bot, chat_state