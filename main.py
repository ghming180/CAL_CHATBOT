# main.py

import streamlit as st
import os
from openai_chatbot import handle_chat, UserState
import time

st.title("📅 AI Meeting Assistant")

# 初始化会话状态
if "chat_history" not in st.session_state:
    st.session_state.chat_history = {
        "messages": [],
        "user_state": UserState()
    }

# 显示聊天历史
for msg in st.session_state.chat_history["messages"]:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    elif msg["role"] == "assistant":
        st.chat_message("assistant").write(msg["content"])
    elif msg["role"] == "function":
        st.chat_message("assistant").write(f"System: {msg['content']}")

# 用户输入
user_input = st.chat_input("Type your message here...")

if user_input:
    # 添加用户消息到UI
    with st.chat_message("user"):
        st.write(user_input)
    
    # 添加到聊天历史
    st.session_state.chat_history["messages"].append({"role": "user", "content": user_input})
    
    # 处理聊天
    response = handle_chat(user_input, st.session_state.chat_history)
    
    # 添加助手响应到UI
    with st.chat_message("assistant"):
        st.write(response)
    
    # 更新聊天历史
    st.session_state.chat_history["messages"].append({"role": "assistant", "content": response})
    
    # 添加延迟确保状态更新
    time.sleep(0.5)  # 等待0.5秒确保操作完成
    
    # 强制刷新UI
    st.rerun()






