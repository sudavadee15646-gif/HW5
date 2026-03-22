import os
from typing import List
from google.adk.core import Agent, SequentialAgent, ParallelAgent, LoopAgent, ToolContext
from google.adk.models import Gemini
from google.adk.tools import exit_loop

# สมมติว่ามีการดึง LangChain Wikipedia Tool มาใช้ (ตามที่เรียนใน Lab ก่อนหน้า)
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

# ตั้งค่า Model (ปรับเปลี่ยน model_id ตามสภาพแวดล้อมของคุณ)
model_name = os.getenv("MODEL", "gemini-2.5-flash")
RETRY_OPTIONS = {"max_retries": 3}

# ==========================================
# 1. TOOLS (ฟังก์ชันเครื่องมือสำหรับ Agents)
# ==========================================

# Tool สำหรับค้นหา Wikipedia
api_wrapper = WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=1500)
wikipedia_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

def set_topic_to_state(tool_context: ToolContext, topic: str) -> dict:
    """บันทึกหัวข้อประวัติศาสตร์ที่ User ต้องการค้นหาลงใน State"""
    tool_context.state["topic"] = topic
    return {"status": f"Topic '{topic}' saved to state."}

def append_pos_data_to_state(tool_context: ToolContext, data: str) -> dict:
    """บันทึกข้อมูลด้านบวก (ความสำเร็จ) ลงใน State key: pos_data"""
    existing_data = tool_context.state.get("pos_data", "")
    tool_context.state["pos_data"] = existing_data + "\n- " + data
    return {"status": "Positive data appended successfully"}

def append_neg_data_to_state(tool_context: ToolContext, data: str) -> dict:
    """บันทึกข้อมูลด้านลบ (ข้อผิดพลาด/ข้อโต้แย้ง) ลงใน State key: neg_data"""
    existing_data = tool_context.state.get("neg_data", "")
    tool_context.state["neg_data"] = existing_data + "\n- " + data
    return {"status": "Negative data appended successfully"}

def write_verdict_file(tool_context: ToolContext, filename: str, content: str) -> dict:
    """บันทึกรายงานสรุปเป็นไฟล์ .txt"""
    os.makedirs("historical_verdicts", exist_ok=True)
    filepath = os.path.join("historical_verdicts", f"{filename}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": f"Verdict saved to {filepath}"}

# ==========================================
# 2. AGENTS DEFINITION
# ==========================================

# --- The Investigation (Parallel) ---
admirer = Agent(
    name="the_admirer",
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    description="ค้นหาข้อมูลด้านบวก ความสำเร็จ และผลงานที่น่ายกย่องของบุคคลหรือเหตุการณ์",
    instruction="""
    INSTRUCTIONS:
    คุณคือ The Admirer (ฝ่ายสนับสนุน) หน้าที่ของคุณคือสืบค้นข้อมูลด้านบวกเกี่ยวกับหัวข้อ: { topic? }
    
    1. ใช้ Tool 'wikipedia_tool' ค้นหาโดยเติม Keyword เช่น "{ topic? } achievements", "{ topic? } positive impact", "{ topic? } contributions"
    2. นำข้อเท็จจริงที่พบมาสรุปให้กระชับ
    3. ใช้ Tool 'append_pos_data_to_state' เพื่อบันทึกข้อมูลด้านบวกลงใน State
    
    คำวิจารณ์จากศาล (ถ้ามี): { judge_feedback? }
    (หากศาลบอกว่าข้อมูลน้อยไป ให้เปลี่ยน Keyword ค้นหาให้ลึกขึ้น)
    """,
    tools=[wikipedia_tool, append_pos_data_to_state]
)

critic = Agent(
    name="the_critic",
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    description="ค้นหาข้อมูลด้านลบ ข้อผิดพลาด และข้อขัดแย้งของบุคคลหรือเหตุการณ์",
    instruction="""
    INSTRUCTIONS:
    คุณคือ The Critic (ฝ่ายค้าน) หน้าที่ของคุณคือสืบค้นข้อมูลด้านลบ ข้อผิดพลาด หรือข้อโต้แย้งเกี่ยวกับ: { topic? }
    
    1. ใช้ Tool 'wikipedia_tool' ค้นหาโดยเติม Keyword เช่น "{ topic? } controversy", "{ topic? } criticism", "{ topic? } mistakes", "{ topic? } atrocities"
    2. นำข้อเท็จจริงที่พบมาสรุปให้กระชับ
    3. ใช้ Tool 'append_neg_data_to_state' เพื่อบันทึกข้อมูลด้านลบลงใน State
    
    คำวิจารณ์จากศาล (ถ้ามี): { judge_feedback? }
    (หากศาลบอกว่าข้อมูลน้อยไป ให้เปลี่ยน Keyword ค้นหาให้เจาะจงหรือรุนแรงขึ้น)
    """,
    tools=[wikipedia_tool, append_neg_data_to_state]
)

investigation_team = ParallelAgent(
    name="investigation_team",
    description="ทำงานคู่ขนานเพื่อหาข้อมูลทั้งด้านบวกและลบ",
    sub_agents=[admirer, critic]
)

# --- The Trial & Review (Loop Judge) ---
judge = Agent(
    name="the_judge",
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    description="ตรวจสอบข้อมูลว่าสมดุลและเพียงพอหรือไม่",
    instruction="""
    INSTRUCTIONS:
    คุณคือ The Judge (ศาล) หน้าที่ของคุณคือพิจารณาหลักฐานจากทั้งสองฝ่าย:
    
    ข้อมูลฝ่ายสนับสนุน (Positive):
    { pos_data? }
    
    ข้อมูลฝ่ายค้าน (Negative):
    { neg_data? }
    
    1. ตรวจสอบว่ามีข้อมูลทั้งสองฝ่ายอย่างน้อยฝ่ายละ 2-3 ประเด็นหลักหรือไม่ และเนื้อหามีความสมดุลกันหรือไม่
    2. หากข้อมูลเพียงพอและสมดุลแล้ว ให้ใช้ Tool 'exit_loop' เพื่อจบการไต่สวน
    3. หากข้อมูลฝั่งใดยังน้อยเกินไป หรือยังขาดน้ำหนัก ห้ามใช้ exit_loop เด็ดขาด! ให้ตอบกลับเป็น Feedback ระบุชัดเจนว่าฝ่ายใดต้องไปหาข้อมูลเรื่องอะไรเพิ่ม (เช่น "The Critic ต้องไปหาข้อมูลเกี่ยวกับคดีความเพิ่มเติม") ข้อความของคุณจะถูกนำไปเก็บใน State เพื่อให้ทีมค้นหาในรอบต่อไป
    """,
    tools=[exit_loop],
    output_key="judge_feedback" # เก็บคำสั่งของศาลไว้ให้ Admirer/Critic อ่านในรอบถัดไป
)

trial_loop = LoopAgent(
    name="trial_loop",
    description="วนลูปหาข้อมูลและตรวจสอบจนกว่าศาลจะพอใจ",
    sub_agents=[investigation_team, judge],
    max_iterations=4 # ป้องกันการลูปไม่รู้จบ
)

# --- The Verdict (Output) ---
verdict_writer = Agent(
    name="verdict_writer",
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    description="สรุปรายงานเปรียบเทียบข้อเท็จจริงและบันทึกเป็นไฟล์ .txt",
    instruction="""
    INSTRUCTIONS:
    เขียนรายงาน "Historical Court Verdict" ที่มีความเป็นกลางที่สุด สำหรับหัวข้อ: { topic? }
    
    วิเคราะห์ข้อมูลต่อไปนี้:
    [Positive Aspects]: { pos_data? }
    [Negative Aspects]: { neg_data? }
    
    โครงสร้างรายงาน:
    1. Introduction (แนะนำบุคคล/เหตุการณ์)
    2. The Achievements (สรุปข้อดี)
    3. The Controversies (สรุปข้อเสีย)
    4. Final Verdict (บทสรุปที่รอบด้านและเป็นกลาง)
    
    จากนั้น ใช้ Tool 'write_verdict_file' เพื่อบันทึกไฟล์:
    - filename: ใช้ชื่อหัวข้อ (เช่น "Genghis_Khan_Verdict")
    - content: รายงานทั้งหมดที่คุณเขียน
    """,
    tools=[write_verdict_file]
)

# --- Main Sequence & Greeter ---
court_system = SequentialAgent(
    name="court_system",
    description="รันกระบวนการศาล: ไต่สวน (ลูป) -> ตัดสิน",
    sub_agents=[trial_loop, verdict_writer]
)

# Root Agent
greeter = Agent(
    name="greeter",
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    description="ทักทาย User และรับหัวข้อประวัติศาสตร์",
    instruction="""
    INSTRUCTIONS:
    คุณคือพนักงานต้อนรับของ The Historical Court
    1. ทักทาย User และถามว่าพวกเขาต้องการนำบุคคลหรือเหตุการณ์ประวัติศาสตร์ใดมาขึ้นศาลจำลอง
    2. เมื่อ User ตอบกลับ ให้ใช้ Tool 'set_topic_to_state' เพื่อบันทึกชื่อหัวข้อนั้น
    3. ส่งต่อให้ 'court_system' ดำเนินการไต่สวนต่อไป
    """,
    tools=[set_topic_to_state],
    sub_agents=[court_system]
)

# ต้องกำหนด Root Agent สำหรับนำไปรันใน ADK Web / CLI
root_agent = greeter
