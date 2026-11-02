import streamlit as st
import json
import random
import os
from openai import OpenAI


# Инициализация клиента Groq
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1" 
)

# --- УМНАЯ ФУНКЦИЯ CRM ---
def create_crm_ticket(name: str, phone: str, niche: str, client_answers: str):
    ticket_id = f"LEAD-{random.randint(1000, 9999)}"
    print(f"\n[CRM] НОВЫЙ ЛИД: {ticket_id} | Ниша: {niche} | Клиент: {name} | Тел: {phone}")
    return json.dumps({"status": "success", "ticket_id": ticket_id})

tools = [
    {
        "type": "function",
        "function": {
            "name": "create_crm_ticket",
            "description": "Создает заявку в CRM. Вызывать ТОЛЬКО если клиент УЖЕ написал ФИО и телефон.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}, "phone": {"type": "string"},
                    "niche": {"type": "string"}, "client_answers": {"type": "string"}
                }
            }
        }
    }
]

SYSTEM_PROMPT = """Ты — СУПЕР-АГЕНТ (Универсальный ИИ-Менеджер). Твоя задача — консультировать и собирать заявки в АБСОЛЮТНО ЛЮБОЙ нише.
АЛГОРИТМ РАБОТЫ:
ШАГ 1. ПОДСТРОЙКА: Из сообщения пойми нишу (ресторан, логистика и т.д.) и стань менеджером этой сферы.
ШАГ 2. КВАЛИФИКАЦИЯ: Задай 1-2 логичных уточняющих вопроса. НЕ ПРОСИ контакты на этом шаге!
ШАГ 3. СБОР КОНТАКТОВ: Когда детали ясны, скажи: "Отлично. Пожалуйста, укажите ваши ФИО и номер телефона для оформления."
ШАГ 4. ФУНКЦИЯ CRM: Как только клиент написал ФИО и телефон, вызови create_crm_ticket.

СТРОГИЕ ПРАВИЛА:
1. Задавай ТОЛЬКО ОДИН вопрос за раз.
2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать внутренние мысли в скобках."""

# --- ИНТЕРФЕЙС WEB ---
st.set_page_config(page_title="Универсальный ИИ-Агент ONYX", page_icon="🤖")
st.title("🤖 Универсальный B2B Агент ONYX")

# Инициализация памяти диалога
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.messages.append({"role": "assistant", "content": "Здравствуйте! Я ИИ-менеджер. Опишите, какая услуга вам нужна."})

# Отрисовка истории (скрываем системные промпты и вызовы функций)
for msg in st.session_state.messages:
    if msg["role"] in ["user", "assistant"] and msg.get("content"):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Обработка ввода пользователя
if prompt := st.chat_input("Напишите ваш запрос..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Анализирую..."):
            MODEL = "openai/gpt-oss-120b"
            try:
                response = client.chat.completions.create(
                    model=MODEL, 
                    messages=st.session_state.messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2, 
                    max_tokens=150
                )
                
                response_message = response.choices[0].message
                
                assistant_msg = {
                    "role": "assistant",
                    "content": response_message.content if response_message.content else ""
                }
                
                if response_message.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}}
                        for t in response_message.tool_calls
                    ]
                    
                st.session_state.messages.append(assistant_msg)
                
                if response_message.tool_calls:
                    crm_ticket_created = False
                    final_text = ""
                    
                    for tool_call in response_message.tool_calls:
                        try:
                            args = json.loads(tool_call.function.arguments)
                        except Exception:
                            args = {}
                        
                        if tool_call.function.name == "create_crm_ticket":
                            result = create_crm_ticket(
                                args.get("name", ""), args.get("phone", ""), 
                                args.get("niche", ""), args.get("client_answers", "")
                            )
                            crm_ticket_created = True
                            ticket_id = json.loads(result).get("ticket_id")
                            final_text = f"✅ Отлично! Ваша заявка **{ticket_id}** успешно оформлена.\nЯ передал все детали менеджерам, с вами скоро свяжутся."
                        else:
                            result = json.dumps({"status": "error"})
                        
                        st.session_state.messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": result,
                        })
                        
                    if crm_ticket_created:
                        st.session_state.messages.append({"role": "assistant", "content": final_text})
                        st.markdown(final_text)
                    else:
                        final_response = client.chat.completions.create(
                            model=MODEL,
                            messages=st.session_state.messages,
                            temperature=0.2,
                            max_tokens=150
                        )
                        f_text = final_response.choices[0].message.content or "Данные приняты."
                        st.session_state.messages.append({"role": "assistant", "content": f_text})
                        st.markdown(f_text)
                else:
                    out_text = response_message.content or "Уточните детали, пожалуйста."
                    st.markdown(out_text)
                    
            except Exception as e:
                st.error(f"Техническая ошибка: {e}")