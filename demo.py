import os
import json
import random
import telebot
from telebot import types
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1" 
)
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))
user_sessions = {}

# --- 1. УМНАЯ ФУНКЦИЯ CRM ---
def create_crm_ticket(name: str, phone: str, niche: str, client_answers: str):
    ticket_id = f"LEAD-{random.randint(1000, 9999)}"
    print(f"\n[CRM] НОВЫЙ ЛИД: {ticket_id}")
    print(f"Ниша: {niche}\nКлиент: {name}\nТелефон: {phone}\nДетали заказа: {client_answers}\n")
    return json.dumps({"status": "success", "ticket_id": ticket_id})

# --- 2. ИНСТРУМЕНТЫ (TOOLS) ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "create_crm_ticket",
            "description": "Создает заявку в CRM. Вызывать ТОЛЬКО если клиент УЖЕ написал свои ФИО и телефон в чат.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "ФИО"},
                    "phone": {"type": "string", "description": "Телефон"},
                    "niche": {"type": "string", "description": "Сфера бизнеса"},
                    "client_answers": {"type": "string", "description": "Все детали заказа"}
                }
            }
        }
    }
]

# --- 3. АДАПТИВНЫЙ СИСТЕМНЫЙ ПРОМПТ ---
SYSTEM_PROMPT = """Ты — СУПЕР-АГЕНТ (Универсальный ИИ-Менеджер). Твоя задача — консультировать и собирать заявки в АБСОЛЮТНО ЛЮБОЙ нише.

АЛГОРИТМ РАБОТЫ:
ШАГ 1. ПОДСТРОЙКА: Из сообщения пойми нишу (ресторан, логистика и т.д.) и стань менеджером этой сферы.
ШАГ 2. КВАЛИФИКАЦИЯ: Задай 1-2 логичных уточняющих вопроса. НЕ ПРОСИ контакты на этом шаге!
ШАГ 3. СБОР КОНТАКТОВ: Когда детали ясны, скажи: "Отлично. Пожалуйста, укажите ваши ФИО и номер телефона для оформления."
ШАГ 4. ФУНКЦИЯ CRM: Как только клиент написал ФИО и телефон, вызови create_crm_ticket.

СТРОГИЕ ПРАВИЛА:
1. Задавай ТОЛЬКО ОДИН вопрос за раз.
2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать внутренние мысли в скобках.
3. При грубости отвечай: "Диалог завершен. Звоните +7 (800) 000-00-00"."""

# --- 4. МЕНЮ И ПАМЯТЬ ---
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📝 Оставить заявку"), types.KeyboardButton("❓ Задать вопрос"))
    markup.add(types.KeyboardButton("🔄 Сбросить диалог"))
    return markup

def reset_chat_history(chat_id):
    user_sessions[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

def get_chat_history(chat_id):
    if chat_id not in user_sessions:
        reset_chat_history(chat_id)
    return user_sessions[chat_id]

# --- 5. КОМАНДЫ ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    reset_chat_history(chat_id)
    bot.send_message(chat_id, "Здравствуйте! Я ИИ-менеджер. Опишите, какая услуга вам нужна.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: msg.text.lower() in ['выход', 'сбросить диалог', 'сброс', 'exit', '🔄 сбросить диалог'])
def handle_exit_reset(message):
    chat_id = message.chat.id
    reset_chat_history(chat_id)
    bot.send_message(chat_id, "Контекст очищен. Какой заказ обсудим теперь?", reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: msg.text == "❓ Задать вопрос")
def handle_faq(message):
    bot.send_message(message.chat.id, "Напишите ваш вопрос, и я постараюсь помочь!")

# --- 6. БРОНЕБОЙНЫЙ LLM ОБРАБОТЧИК ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_text = message.text
    chat_history = get_chat_history(chat_id)
    
    bot.send_chat_action(chat_id, 'typing')
    chat_history.append({"role": "user", "content": user_text})
    MODEL = "openai/gpt-oss-120b" 

    try:
        response = client.chat.completions.create(
            model=MODEL, 
            messages=chat_history,
            tools=tools,
            tool_choice="auto",
            temperature=0.2, # Снизили креативность для максимальной стабильности
            max_tokens=150
        )
        
        response_message = response.choices[0].message
        
        # Упаковка ответа в историю
        assistant_msg = {
            "role": "assistant",
            "content": response_message.content if response_message.content is not None else ""
        }
        
        if response_message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": t.id, 
                    "type": "function", 
                    "function": {"name": t.function.name, "arguments": t.function.arguments}
                } for t in response_message.tool_calls
            ]
            
        chat_history.append(assistant_msg)
        
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
                        args.get("name", "Не указано"), 
                        args.get("phone", "Не указано"), 
                        args.get("niche", "Не указано"), 
                        args.get("client_answers", "Не указано")
                    )
                    crm_ticket_created = True
                    ticket_id = json.loads(result).get("ticket_id", "LEAD-0000")
                    
                    # ПЕРЕХВАТ УПРАВЛЕНИЯ: Генерируем идеальный ответ скриптом, без участия нейросети!
                    final_text = f"✅ Отлично! Ваша заявка **{ticket_id}** успешно оформлена.\nЯ передал все детали менеджерам, с вами скоро свяжутся.\n\nЧем я могу помочь вам еще?"
                else:
                    result = json.dumps({"status": "error"})
                
                chat_history.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": result,
                })
            
            # Если заявка создана, выдаем наш жестко заданный текст (никакой каши из букв)
            if crm_ticket_created:
                chat_history.append({"role": "assistant", "content": final_text})
                bot.send_message(chat_id, final_text, reply_markup=get_main_menu())
            else:
                # Если была вызвана другая функция, возвращаем управление нейросети
                final_response = client.chat.completions.create(
                    model=MODEL,
                    messages=chat_history,
                    temperature=0.2,
                    max_tokens=150
                )
                final_text = final_response.choices[0].message.content
                if not final_text: final_text = "Данные приняты."
                chat_history.append({"role": "assistant", "content": final_text})
                bot.send_message(chat_id, final_text, reply_markup=get_main_menu())
            
        else:
            out_text = response_message.content
            if not out_text: out_text = "Я вас понял. Уточните детали, пожалуйста."
            bot.send_message(chat_id, out_text, reply_markup=get_main_menu())
            
    except Exception as e:
        bot.send_message(chat_id, "Извините, произошла техническая заминка. Пожалуйста, повторите запрос.")
        print(f"Ошибка API: {e}")

if __name__ == "__main__":
    print("=== УНИВЕРСАЛЬНЫЙ B2B БОТ ЗАПУЩЕН ===")
    bot.infinity_polling()