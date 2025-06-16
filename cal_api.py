# cal_api.py
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import logging
import pytz

# 设置详细的日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

BASE_URL = "https://api.cal.com/v1"
CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_USERNAME = os.getenv("CAL_USERNAME")  # cal.com用户名

# 详细的调试日志
logger.info(f"🔐 CAL_API_KEY: {CAL_API_KEY[:5]}...{CAL_API_KEY[-5:]}")
logger.info(f"👤 CAL_USERNAME: {CAL_USERNAME}")

# 使用双重认证机制
HEADERS = {
    "Content-Type": "application/json"
}

def make_request(method, endpoint, params=None, data=None):
    """统一处理API请求"""
    # 在查询参数中添加API密钥
    params = params or {}
    if "apiKey" not in params:
        params["apiKey"] = CAL_API_KEY
    
    url = f"{BASE_URL}/{endpoint}"
    logger.info(f"🌐 Making {method} request to {url}")
    logger.info(f"🔑 Parameters: {params}")
    if data:
        logger.info(f"📦 Payload: {json.dumps(data, indent=2)}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS, params=params)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json=data, params=params)
        elif method == "DELETE":
            response = requests.delete(url, headers=HEADERS, params=params)
        
        logger.info(f"🔧 Response status: {response.status_code}")
        logger.info(f"📄 Response content: {response.text[:500]}")  # 只记录前500个字符
        
        # 处理响应
        if response.status_code in [200, 201]:
            return response.json()
        else:
            error_msg = {
                "error": f"API request failed: {response.status_code}",
                "url": url,
                "params": params,
                "response": response.text
            }
            logger.error(f"❌ Error: {json.dumps(error_msg, indent=2)}")
            return error_msg
    except Exception as e:
        error_msg = {"error": f"Request exception: {str(e)}"}
        logger.exception(f"❌ Exception during request")
        return error_msg

def get_current_user():
    """获取当前用户信息（验证API密钥）"""
    logger.info("🔍 Getting current user info...")
    return make_request("GET", "me")

def get_event_types():
    """获取用户的所有事件类型"""
    logger.info("🔍 Getting event types...")
    return make_request("GET", "event-types", {"username": CAL_USERNAME})


def get_first_event_type():
    """获取第一个事件类型及其时长"""
    data = get_event_types()
    if "error" in data:
        return None, None
    
    event_types = data.get("event_types", [])
    logger.info(f"🔍 Found {len(event_types)} event types")
    
    # 返回第一个事件类型ID和时长
    if event_types:
        event = event_types[0]
        return event["id"], event.get("length", 30)  # 默认30分钟
    
#     return None, None

def get_most_suitable_event_type(duration=30):
    """根据时长选择最合适的事件类型"""
    data = get_event_types()
    if "error" in data:
        return None
    
    event_types = data.get("event_types", [])
    logger.info(f"🔍 Found {len(event_types)} event types")
    
    if not event_types:
        return None
    
    # 找到时长最接近的事件类型
    return min(event_types, key=lambda x: abs(x.get("length", 0) - duration))["id"]

def get_event_length(event_type_id):
    """获取事件类型的时长"""
    event_types = get_event_types().get("event_types", [])
    for event in event_types:
        if event["id"] == event_type_id:
            return event.get("length", 30)
    return 30

def create_default_event_type():
    """创建默认事件类型"""
    logger.info("⚠️ No event types found, creating default...")
    payload = {
        "title": "30 Minute Meeting",
        "slug": "30min",
        "length": 30,
        "hidden": False
    }
    response = make_request("POST", "event-types", data=payload)
    if "event_type" in response:
        return response["event_type"]["id"]
    return None

def get_default_schedule():
    """获取默认的时间表ID"""
    logger.info("📅 Getting default schedule")
    schedules = make_request("GET", "schedules")
    if "error" in schedules or not schedules.get("schedules"):
        return None
    
    # 返回第一个时间表ID
    return schedules["schedules"][0]["id"]



def list_events(email, timezone="UTC"):
    """根据邮箱列出事件，并按指定时区转换时间，过滤已取消事件"""
    logger.info(f"📋 Listing events for {email}")
    response = make_request("GET", "bookings", {"email": email})
    
    if "error" in response:
        return response

    # 过滤掉已取消的事件
    active_bookings = [b for b in response.get("bookings", []) 
                      if b.get("status") != "CANCELLED"]

    # 转换时区
    user_tz = pytz.timezone(timezone)
    for booking in active_bookings:
        if "startTime" in booking:
            try:
                # 解析UTC时间
                start_utc = datetime.fromisoformat(booking["startTime"].replace("Z", "+00:00"))
                end_utc = datetime.fromisoformat(booking["endTime"].replace("Z", "+00:00"))
                
                # 转换为用户时区
                booking["local_start"] = start_utc.astimezone(user_tz).strftime("%Y-%m-%d %H:%M")
                booking["local_end"] = end_utc.astimezone(user_tz).strftime("%H:%M")
                
                # 添加可读性更好的显示字段
                booking["display_time"] = f"{booking['local_start']} - {booking['local_end']}"
            except Exception as e:
                logger.error(f"❌ Error converting time: {str(e)}")
                booking["local_start"] = booking["startTime"]
                booking["local_end"] = booking["endTime"]
                booking["display_time"] = f"{booking['startTime']} - {booking['endTime']}"
    
    return {"bookings": active_bookings}  # 只返回有效事件



def cancel_event(booking_id):
    """取消事件"""
    logger.info(f"❌ Canceling booking {booking_id}")
    return make_request("DELETE", f"bookings/{booking_id}")


def get_available_slots(date, timezone="UTC", event_type_id=None):
    """获取指定日期的可用时隙"""
    logger.info(f"⏱️ Getting available slots for {date} in {timezone}")
    
    # 设置时间范围（当天00:00到23:59）
    start_time = f"{date}T00:00:00"
    end_time = f"{date}T23:59:59"
    
    params = {
        "username": CAL_USERNAME,
        "startTime": start_time,  # 使用正确的参数名
        "endTime": end_time,      # 使用正确的参数名
        "timeZone": timezone,
    }
    
    # 如果指定了事件类型ID，添加到参数中
    if event_type_id:
        params["eventTypeId"] = event_type_id
    
    return make_request("GET", "slots", params=params)

def parse_slot_time(slot_time):
    """解析时间槽字符串为datetime对象"""
    try:
        # 尝试解析ISO格式时间
        return datetime.fromisoformat(slot_time)
    except ValueError:
        # 尝试解析其他常见格式
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M%z"]:
            try:
                return datetime.strptime(slot_time, fmt)
            except ValueError:
                continue
    return None

def is_slot_available(date, time, duration, timezone="UTC", event_type_id=None):
    """检查特定时间段是否可用"""
    slots = get_available_slots(date, timezone, event_type_id)
    
    # 检查是否有错误或没有时隙
    if "error" in slots or "slots" not in slots or not slots["slots"].get(date):
        logger.warning(f"⚠️ No available slots found for {date}")
        return False
    
    # 创建目标开始时间（本地时间）
    target_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    
    # 创建目标结束时间
    target_end = target_start + timedelta(minutes=duration)
    
    # 获取用户时区
    user_tz = pytz.timezone(timezone)
    
    # 转换目标时间为用户时区
    target_start_tz = user_tz.localize(target_start)
    target_end_tz = user_tz.localize(target_end)
    
    logger.info(f"🔍 Checking availability for {target_start_tz} to {target_end_tz}")
    
    # 查找匹配的时隙
    for slot in slots["slots"].get(date, []):
        if "time" not in slot:
            continue
            
        slot_time = slot["time"]
        slot_dt = parse_slot_time(slot_time)
        
        if not slot_dt:
            logger.warning(f"⚠️ Could not parse slot time: {slot_time}")
            continue
        
        # 确保时间对象有时区信息
        if slot_dt.tzinfo is None:
            slot_dt = slot_dt.replace(tzinfo=pytz.utc)
        
        # 转换为用户时区
        slot_dt_user = slot_dt.astimezone(user_tz)
        
        # 检查是否在目标时间范围内
        if slot_dt_user == target_start_tz:
            logger.info(f"✅ Found matching slot: {slot_dt_user}")
            return True
    
    return False

def book_event(email, date, time, reason, timezone="UTC"):
    """预订新事件"""
    # 尝试获取事件类型ID和时长
    event_type_id, event_length = get_first_event_type()
    
    # 如果没有事件类型，创建默认
    if not event_type_id:
        event_type_id = create_default_event_type()
        if not event_type_id:
            return {"error": "Failed to create default event type"}
        # 默认时长为30分钟
        event_length = 30
    
    # 如果没有获取到时长，使用默认30分钟
    if not event_length:
        event_length = 30
    
    # 检查时隙是否可用（使用事件类型ID）
    if not is_slot_available(date, time, event_length, timezone, event_type_id):
        return {"error": "Time slot not available"}
    
    try:
        # 创建带时区的时间对象
        user_tz = pytz.timezone(timezone)
        naive_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        start_dt = user_tz.localize(naive_start)
        
        # 根据事件类型时长计算结束时间
        end_dt = start_dt + timedelta(minutes=event_length)
        
        # 转换为UTC
        utc_start = start_dt.astimezone(pytz.utc).isoformat()
        utc_end = end_dt.astimezone(pytz.utc).isoformat()
        
        payload = {
            "eventTypeId": event_type_id,
            "start": utc_start,
            "end": utc_end,
            "responses": {
                "name": email.split('@')[0],
                "email": email,
                "notes": reason
            },
            "timeZone": timezone,
            "language": "en",
            "metadata": {}
        }
        
        logger.info(f"📅 Booking {event_length}min event for {email} on {date} at {time} ({timezone})")
        logger.info(f"📦 Payload: {json.dumps(payload, indent=2)}")
        
        return make_request("POST", "bookings", data=payload)
    except ValueError as ve:
        logger.error(f"❌ Value error: {str(ve)}")
        return {"error": "Invalid date/time format"}
    except Exception as e:
        logger.error(f"❌ General error: {str(e)}")
        return {"error": f"Booking failed: {str(e)}"}





def find_booking_id(email, date, time, timezone="UTC"):
    """根据邮箱、日期和时间查找预约ID"""
    logger.info(f"🔍 Finding booking for {email} on {date} at {time}")
    bookings = list_events(email, timezone)
    if "error" in bookings:
        return None
    
    for booking in bookings.get("bookings", []):
        if booking.get("status") == "CANCELLED":
            continue
        if "local_start" in booking:
            try:
                # 解析本地时间
                booking_time = datetime.strptime(booking["local_start"], "%Y-%m-%d %H:%M")
                target_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
                
                # 比较时间
                if booking_time == target_time:
                    return booking["id"]
            except Exception as e:
                logger.warning(f"⚠️ Error parsing date: {str(e)}")
    return None

# 测试当前用户信息
if __name__ == "__main__":
    logger.info("🧪 Running API tests...")
    print("🧑 User Info:", get_current_user())
    print("📅 Event Types:", get_event_types())
    
    # 测试获取可用时段
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    print("⏱️ Available slots:", get_available_slots(tomorrow, "America/Los_Angeles"))
    
    # 测试预订
    print("📅 Test Booking:", book_event(
        "test@example.com", 
        tomorrow,
        "11:00", 
        "Test Meeting",
        "America/Los_Angeles"
    ))















