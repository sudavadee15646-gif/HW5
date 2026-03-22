# ⚖️ The Historical Court (Multi-Agent System)

โปรเจกต์นี้เป็นการจำลอง "ศาลประวัติศาสตร์" โดยใช้เทคโนโลยี Multi-Agent System พัฒนาบน **Google Agent Development Kit (ADK)** ระบบจะทำการวิเคราะห์บุคคลหรือเหตุการณ์ในประวัติศาสตร์แบบรอบด้าน (ทั้งแง่บวกและแง่ลบ) เพื่อความสร้างรายงานสรุป (Verdict) ที่มีความเป็นกลางที่สุด

## 🏗️ โครงสร้างของระบบ (System Architecture)

ระบบประกอบด้วย Agent จำนวน 6 ตัว จัดเรียงแบบ Hierarchical Tree ดังนี้:

1. **Greeter (Root Agent)**: ทำหน้าที่ทักทายและรับชื่อหัวข้อ (Topic) จากผู้ใช้งาน จากนั้นบันทึกลง Session State
2. **Court System (Sequential Agent)**: เป็นตัวควบคุมลำดับเหตุการณ์ทั้งหมด
   3. **Trial Loop (Loop Agent)**: ลูปสำหรับการหาข้อมูลและตรวจสอบความถูกต้อง
      4. **Investigation Team (Parallel Agent)**: กระจายงานค้นหาข้อมูลพร้อมกัน 2 สาขา
         - **The Admirer**: ค้นหาข้อมูลด้านบวก (Achievements) บันทึกลง State `pos_data`
         - **The Critic**: ค้นหาข้อมูลด้านลบ (Controversies) บันทึกลง State `neg_data`
      5. **The Judge**: อ่าน `pos_data` และ `neg_data` หากข้อมูลไม่เพียงพอหรือเอนเอียง จะสั่งให้กลับไปหาใหม่ (พร้อมระบุประเด็น) หากข้อมูลครบถ้วนจะใช้เครื่องมือ `exit_loop`
   6. **Verdict Writer**: อ่านข้อมูลจาก State ทั้งหมด นำมาเขียนรายงานแบบเป็นกลาง และบันทึกเป็นไฟล์ `.txt`

## ⚙️ เทคนิคทางโปรแกรมมิ่งที่นำมาใช้ (Technical Highlights)

*   **State Management & Templating**: 
    มีการสร้างเครื่องมือ (Tools) พิเศษเพื่อแยกเก็บข้อมูล `pos_data` และ `neg_data` ออกจากกันอย่างชัดเจน และใช้ Templating `{ key? }` เพื่อดึงบริบทจาก State มาป้อนให้ Agent ตัวอื่นโดยตรง (เช่น `{ topic? }` หรือ `{ judge_feedback? }`)
*   **Targeted Wikipedia Research**: 
    ใช้ Prompt Injection ป้องกันปัญหา Agent ค้นหาข้อมูลทับซ้อนกัน โดยสั่งให้ The Admirer เติมคำว่า *"achievements"* ต่อท้ายคำค้นหาเสมอ และให้ The Critic เติมคำว่า *"controversy"* หรือ *"mistakes"* เสมอ
*   **Deterministic Loop Control**:
    The Judge ไม่ได้ใช้แค่ Prompt ในการจบลูป แต่บังคับให้ตัดสินใจเรียกฟังก์ชัน `exit_loop()` ผ่านระบบ Tool Calling ทำให้ Flow ของโปรแกรมมีความน่าเชื่อถือและทำงานได้จริงตามหลักการของ ADK

## 🚀 วิธีการรันโปรแกรม

1. สร้าง Environment และติดตั้ง Dependency: `pip install google-adk langchain-community wikipedia`
2. รันคำสั่งเปิด ADK Web UI: `adk web --reload_agents`
3. เปิด Browser ไปที่ `http://127.0.0.1:8000` เลือก Agent แล้วเริ่มแชทได้เลย
4. รายงานจะถูกบันทึกในโฟลเดอร์ `historical_verdicts/`
