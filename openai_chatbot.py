# openai_chatbot.py
import os
from openai import OpenAI
from dotenv import load_dotenv
import json
import cal_api
import re
import logging
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class UserState:
    def __init__(self):
        self.email = None
        self.timezone = "America/Los_Angeles"  # 默认时区
        self.name = None
        self.last_interaction = datetime.now()
    
    def update_from_message(self, message):
        """从消息中提取用户信息"""
        # 提取邮箱
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
        if email_match:
            self.email = email_match.group(0)
            logger.info(f"📧 Extracted email: {self.email}")
        
        # 提取时区
        if "timezone" in message.lower():
            tz_match = re.search(r'timezone:\s*(\S+)', message, re.IGNORECASE)
            if tz_match:
                self.timezone = tz_match.group(1)
                logger.info(f"🌍 Extracted timezone: {self.timezone}")
        
        # 提取姓名
        if "name" in message.lower():
            name_match = re.search(r'name:\s*([\w\s]+)', message, re.IGNORECASE)
            if name_match:
                self.name = name_match.group(1).strip()
                logger.info(f"👤 Extracted name: {self.name}")
        
        # 更新最后交互时间
        self.last_interaction = datetime.now()

def parse_relative_date(user_message, user_state):
    """解析相对日期（如tomorrow）为具体日期"""
    today = datetime.now()
    
    if "today" in user_message.lower():
        return today.strftime("%Y-%m-%d")
    elif "tomorrow" in user_message.lower():
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "next week" in user_message.lower():
        return (today + timedelta(weeks=1)).strftime("%Y-%m-%d")
    
    # 默认返回今天
    return today.strftime("%Y-%m-%d")

def format_slot_times(slots, date):
    """格式化可用时间段为友好的时间列表"""
    formatted_slots = []
    for slot in slots.get(date, []):
        try:
            # 解析ISO时间字符串
            slot_time = datetime.fromisoformat(slot["start"])
            # 格式化为HH:MM
            formatted_slots.append(slot_time.strftime("%H:%M"))
        except Exception as e:
            logger.warning(f"⚠️ Error formatting slot time: {str(e)}")
    
    # 去重并排序
    return sorted(set(formatted_slots))

def handle_chat(user_message, chat_history):
    from functions import get_openai_function_definitions
    functions = get_openai_function_definitions()
    user_state = chat_history.get("user_state", UserState())
    
    # 更新用户状态
    user_state.update_from_message(user_message)
    
    # 获取当前日期作为上下文
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # 构建系统提示词 - 包含当前日期信息
    system_prompt = (
        f"You are a helpful meeting assistant. Today is {current_date}. "
        "When the user says 'tomorrow', calculate it as the day after today. "
        "If the user provides a relative time (like 'tomorrow'), use the current date to calculate the actual date. "
        "Only ask for confirmation if absolutely necessary."
    )
    
    # 构建消息历史
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history.get("messages", []))
    messages.append({"role": "user", "content": user_message})
    
    logger.info(f"💬 User message: {user_message}")
    
    # 调用OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            functions=functions,
            function_call="auto"
        )

        message = response.choices[0].message
        logger.info(f"🤖 AI response: {message.content or 'Function call'}")
        
        # 保存用户状态
        chat_history["user_state"] = user_state
        chat_history["messages"] = messages
        
        if message.function_call:
            func_name = message.function_call.name
            logger.info(f"🔧 Function call: {func_name}")
            
            try:
                args = json.loads(message.function_call.arguments)
                logger.info(f"⚙️ Function arguments: {json.dumps(args, indent=2)}")
                
                # 自动填充用户邮箱
                if "email" not in args and user_state.email:
                    args["email"] = user_state.email
                    logger.info(f"📧 Using stored email: {user_state.email}")
                
                # 特殊处理取消事件
                if func_name == "cancel_event":
                    if "email" not in args:
                        return "Please provide your email address to cancel a meeting."
                    if "date" not in args or "time" not in args:
                        return "Please specify the date and time of the meeting to cancel."
                    
                    booking_id = cal_api.find_booking_id(
                        args["email"], 
                        args["date"], 
                        args["time"]
                    )
                    if booking_id:
                        result = cal_api.cancel_event(booking_id)
                        if result and "error" not in result:
                            response_text = f"✅ Your event on {args['date']} at {args['time']} has been canceled."
                        else:
                            response_text = "❌ Failed to cancel event. Please try again later."
                    else:
                        response_text = "❌ No matching event found."
                
                # 处理预订事件
                elif func_name == "book_event":
                    # 确保所有参数都存在
                    if "email" not in args:
                        return "Please provide your email address to book a meeting."
                    if "date" not in args:
                        # 尝试从用户消息中解析日期
                        args["date"] = parse_relative_date(user_message, user_state)
                        logger.info(f"📅 Auto-filled date: {args['date']}")
                    if "time" not in args:
                        return "Please specify the time for the meeting."
                    if "reason" not in args:
                        args["reason"] = "Meeting"  # 默认原因
                    
                    # 使用用户时区（如果已设置）
                    timezone = user_state.timezone
                    logger.info(f"⏰ Using timezone: {timezone}")
                    
                    result = cal_api.book_event(
                        email=args["email"],
                        date=args["date"],
                        time=args["time"],
                        reason=args["reason"],
                        timezone=timezone
                    )
                    
                    if "error" in result:
                        error_msg = result["error"]
                        
                        # 处理时间不可用的情况
                        if "Time slot not available" in error_msg:
                            # 获取备选时间建议
                            available_slots = cal_api.get_available_slots(args["date"], timezone)
                            
                            if "slots" in available_slots and args["date"] in available_slots["slots"]:
                                slots = available_slots["slots"][args["date"]]
                                # 格式化备选时间
                                time_options = format_slot_times(available_slots["slots"], args["date"])
                                
                                if time_options:
                                    # 只显示前5个选项
                                    time_list = "\n".join([f"- {t}" for t in time_options[:5]])
                                    response_text = (
                                        f"❌ The requested time ({args['time']}) is not available. "
                                        f"Here are some available times on {args['date']}:\n"
                                        f"{time_list}\n"
                                        f"Please choose one of these times."
                                    )
                                else:
                                    response_text = "❌ The requested time is not available. Please choose a different time."
                            else:
                                response_text = "❌ The requested time is not available. Please choose a different time."
                        
                        # 处理其他错误
                        else:
                            response_text = f"❌ Booking failed: {error_msg}"
                    else:
                        booking = result.get("booking", {})
                        if booking:
                            response_text = (
                                f"✅ Meeting booked!\n"
                                f"Title: {booking.get('title', args['reason'])}\n"
                                f"Date: {args['date']}\n"
                                f"Time: {args['time']}"
                            )
                        else:
                            response_text = "✅ Meeting booked! Details will be confirmed shortly."
                
                # 处理列出事件
                elif func_name == "list_events":
                    if "email" not in args and user_state.email:
                        args["email"] = user_state.email
                    
                    if "email" not in args:
                        return "Please provide your email address to view your events."
                    
                    result = cal_api.list_events(**args)
                    if "error" in result:
                        response_text = f"❌ Error: {result['error']}"
                    else:
                        events = result.get("bookings", [])
                        if events:
                            event_list = "\n".join([
                                f"- {e['title']} on {e['startTime'].split('T')[0]} at {e['startTime'].split('T')[1][:5]}"
                                for e in events
                            ])
                            response_text = f"📅 Your upcoming events:\n{event_list}"
                        else:
                            response_text = "📅 You have no upcoming events."
                else:
                    response_text = "❌ Unknown function requested"
                
                return response_text
            
            except Exception as e:
                logger.exception(f"❌ Error during function execution")
                return f"❌ Error: {str(e)}"
        else:
            return message.content
    
    except Exception as e:
        logger.exception(f"❌ Error during OpenAI call")
        return f"❌ Sorry, I encountered an error. Please try again."










