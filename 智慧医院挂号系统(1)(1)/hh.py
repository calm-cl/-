import json
import hashlib
import datetime
import re
from typing import List, Dict, Optional

# ===================== 配置常量 =====================
DATA_FILE = "hospital_system_data.json"  # 数据持久化文件
PATIENT_ID_REGEX = r"^\d{17}[\dXx]$"  # 身份证号正则
DOCTOR_ID_REGEX = r"^\d{6}$"  # 医生工号正则（6位数字）
VALID_APPOINTMENT_HOURS = [8, 9, 10, 11, 14, 15, 16, 17]  # 有效预约小时段


# ===================== 数据模型 =====================
class BaseModel:
    """基础模型类，提供序列化/反序列化能力"""

    def to_dict(self) -> Dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict):
        obj = cls.__new__(cls)
        obj.__dict__.update(data)
        return obj


class User(BaseModel):
    """用户基类"""

    def __init__(self, username: str, password_hash: str, role: str):
        self.username = username  # 登录账号
        self.password_hash = password_hash  # 密码哈希（非明文）
        self.role = role  # patient/doctor/admin


class Patient(User):
    """患者模型"""

    def __init__(self, username: str, password_hash: str, real_name: str, id_card: str):
        super().__init__(username, password_hash, "patient")
        self.real_name = real_name  # 真实姓名
        self.id_card = id_card  # 身份证号
        self.appointments: List[str] = []  # 预约ID列表


class Doctor(User):
    """医生模型"""

    def __init__(self, username: str, password_hash: str, real_name: str, doctor_id: str, department_id: str):
        super().__init__(username, password_hash, "doctor")
        self.real_name = real_name  # 真实姓名
        self.doctor_id = doctor_id  # 医生工号
        self.department_id = department_id  # 所属科室ID
        self.working_days: List[str] = []  # 出诊日期列表（格式：2025-12-16）
        self.appointments: List[str] = []  # 预约ID列表


class Admin(User):
    """管理员模型"""

    def __init__(self, username: str, password_hash: str, real_name: str):
        super().__init__(username, password_hash, "admin")
        self.real_name = real_name  # 真实姓名


class Department(BaseModel):
    """科室模型"""

    def __init__(self, dept_id: str, dept_name: str):
        self.dept_id = dept_id  # 科室ID
        self.dept_name = dept_name  # 科室名称
        self.doctors: List[str] = []  # 科室下医生账号列表


class Appointment(BaseModel):
    """预约模型"""

    def __init__(self, appt_id: str, patient_username: str, doctor_username: str,
                 appt_time: str, status: str = "pending"):
        self.appt_id = appt_id  # 预约ID
        self.patient_username = patient_username  # 患者账号
        self.doctor_username = doctor_username  # 医生账号
        self.appt_time = appt_time  # 预约时间（格式：2025-12-16 09:00）
        self.status = status  # pending/completed/canceled


class MedicalRecord(BaseModel):
    """病历模型"""

    def __init__(self, record_id: str, appt_id: str, patient_username: str,
                 doctor_username: str, diagnosis: str, prescriptions: List[Dict]):
        self.record_id = record_id  # 病历ID
        self.appt_id = appt_id  # 关联预约ID
        self.patient_username = patient_username
        self.doctor_username = doctor_username
        self.diagnosis = diagnosis  # 诊断结果
        self.prescriptions = prescriptions  # 处方列表：[{"drug": "xxx", "dose": "xxx"}]


# ===================== 数据持久化工具 =====================
def load_data() -> Dict:
    """加载本地数据文件"""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 初始化空数据结构
        return {
            "users": {},  # {username: 模型字典}
            "departments": {},  # {dept_id: 模型字典}
            "appointments": {},  # {appt_id: 模型字典}
            "medical_records": {}  # {record_id: 模型字典}
        }


def save_data(data: Dict) -> None:
    """保存数据到本地文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ===================== 工具函数 =====================
def hash_password(password: str) -> str:
    """密码哈希（SHA256）"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_id(prefix: str) -> str:
    """生成唯一ID（前缀+时间戳）"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{timestamp}"


def validate_time_format(time_str: str) -> bool:
    """验证时间格式：YYYY-MM-DD HH:MM"""
    try:
        datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        # 检查小时是否在有效时段
        hour = int(time_str.split()[1].split(":")[0])
        return hour in VALID_APPOINTMENT_HOURS
    except ValueError:
        return False


def check_appointment_conflict(data: Dict, username: str, appt_time: str, role: str) -> bool:
    """
    检查预约冲突
    :param data: 系统数据
    :param username: 患者/医生账号
    :param appt_time: 预约时间
    :param role: patient/doctor
    :return: True=冲突，False=无冲突
    """
    for appt in data["appointments"].values():
        if appt["status"] != "pending":
            continue
        if role == "patient" and appt["patient_username"] == username and appt["appt_time"] == appt_time:
            return True
        if role == "doctor" and appt["doctor_username"] == username and appt["appt_time"] == appt_time:
            return True
    return False


def get_doctor_working_days(data: Dict, doctor_username: str) -> List[str]:
    """获取医生出诊日期"""
    doctor = data["users"].get(doctor_username)
    if not doctor or doctor["role"] != "doctor":
        return []
    return doctor["working_days"]


# ===================== 登录/注册功能 =====================
def register(data: Dict) -> None:
    """用户注册"""
    print("\n===== 注册界面 =====")
    username = input("请输入登录账号（字母+数字）：").strip()
    if not re.match(r"^[a-zA-Z0-9]{4,20}$", username):
        print("账号格式错误！需4-20位字母+数字组合")
        return
    if username in data["users"]:
        print("该账号已存在！")
        return

    password = input("请输入密码（至少6位）：").strip()
    if len(password) < 6:
        print("密码长度需至少6位！")
        return
    password_hash = hash_password(password)

    role = input("请选择角色（patient/doctor/admin）：").lower().strip()
    if role not in ["patient", "doctor", "admin"]:
        print("无效角色！")
        return

    # 按角色补充信息
    if role == "patient":
        real_name = input("请输入真实姓名：").strip()
        id_card = input("请输入身份证号：").strip()
        if not re.match(PATIENT_ID_REGEX, id_card):
            print("身份证号格式错误！")
            return
        # 检查身份证号是否已注册
        for user in data["users"].values():
            if user["role"] == "patient" and user["id_card"] == id_card:
                print("该身份证号已注册！")
                return
        user = Patient(username, password_hash, real_name, id_card)

    elif role == "doctor":
        real_name = input("请输入真实姓名：").strip()
        doctor_id = input("请输入医生工号（6位数字）：").strip()
        if not re.match(DOCTOR_ID_REGEX, doctor_id):
            print("医生工号格式错误（需6位数字）！")
            return
        # 检查工号是否已注册
        for user in data["users"].values():
            if user["role"] == "doctor" and user["doctor_id"] == doctor_id:
                print("该医生工号已注册！")
                return
        # 选择科室
        if not data["departments"]:
            print("暂无科室！请联系管理员创建科室后再注册")
            return
        print("\n当前科室列表：")
        for dept_id, dept in data["departments"].items():
            print(f"ID：{dept_id} | 名称：{dept['dept_name']}")
        dept_id = input("请输入所属科室ID：").strip()
        if dept_id not in data["departments"]:
            print("科室ID不存在！")
            return
        user = Doctor(username, password_hash, real_name, doctor_id, dept_id)
        # 将医生加入科室
        data["departments"][dept_id]["doctors"].append(username)

    else:  # admin
        real_name = input("请输入管理员真实姓名：").strip()
        user = Admin(username, password_hash, real_name)

    # 保存用户
    data["users"][username] = user.to_dict()
    save_data(data)
    print("注册成功！")


def login(data: Dict) -> Optional[Dict]:
    """用户登录"""
    print("\n===== 登录界面 =====")
    username = input("请输入账号：").strip()
    if username not in data["users"]:
        print("账号不存在！")
        return None

    password = input("请输入密码：").strip()
    user = data["users"][username]
    if user["password_hash"] != hash_password(password):
        print("密码错误！")
        return None

    print(f"\n登录成功！欢迎 {user['real_name']}（{user['role']}）")
    return user


# ===================== 角色功能菜单 =====================
def patient_menu(data: Dict, patient: Dict) -> None:
    """患者功能菜单"""
    while True:
        print("\n===== 患者中心 =====")
        print("1. 预约挂号")
        print("2. 查看我的预约")
        print("3. 取消预约")
        print("4. 查看我的病历")
        print("5. 退出")
        choice = input("请选择操作（1-5）：").strip()

        if choice == "1":
            # 预约挂号
            if not data["departments"]:
                print("暂无科室可预约！")
                continue
            # 选择科室
            print("\n科室列表：")
            dept_list = list(data["departments"].items())
            for i, (dept_id, dept) in enumerate(dept_list, 1):
                print(f"{i}. ID：{dept_id} | 名称：{dept['dept_name']}")
            try:
                dept_idx = int(input("请选择科室序号：").strip()) - 1
                if dept_idx < 0 or dept_idx >= len(dept_list):
                    print("无效序号！")
                    continue
                dept_id, dept = dept_list[dept_idx]
            except ValueError:
                print("请输入数字！")
                continue

            # 选择医生
            if not dept["doctors"]:
                print("该科室暂无医生！")
                continue
            print(f"\n{dept['dept_name']} 医生列表：")
            doctor_list = []
            for doc_username in dept["doctors"]:
                doc = data["users"][doc_username]
                doctor_list.append((doc_username, doc))
                print(f"{len(doctor_list)}. 姓名：{doc['real_name']} | 工号：{doc['doctor_id']}")
            try:
                doc_idx = int(input("请选择医生序号：").strip()) - 1
                if doc_idx < 0 or doc_idx >= len(doctor_list):
                    print("无效序号！")
                    continue
                doc_username, doctor = doctor_list[doc_idx]
            except ValueError:
                print("请输入数字！")
                continue

            # 选择预约时间
            working_days = get_doctor_working_days(data, doc_username)
            if not working_days:
                print("该医生暂无出诊时间！请联系管理员设置")
                continue
            print(f"\n{doctor['real_name']} 出诊日期：{', '.join(working_days)}")
            appt_date = input("请输入预约日期（YYYY-MM-DD）：").strip()
            if appt_date not in working_days:
                print("该日期医生不出诊！")
                continue
            appt_hour = input(f"请输入预约小时（可选：{VALID_APPOINTMENT_HOURS}）：").strip()
            try:
                appt_hour = int(appt_hour)
                if appt_hour not in VALID_APPOINTMENT_HOURS:
                    print("无效小时段！")
                    continue
            except ValueError:
                print("请输入数字！")
                continue
            appt_time = f"{appt_date} {appt_hour}:00"

            # 检查预约冲突
            if check_appointment_conflict(data, patient["username"], appt_time, "patient"):
                print("您已在该时间有其他预约！")
                continue
            if check_appointment_conflict(data, doc_username, appt_time, "doctor"):
                print("该医生在该时间已有预约！")
                continue

            # 创建预约
            appt_id = generate_id("APPT")
            appointment = Appointment(
                appt_id=appt_id,
                patient_username=patient["username"],
                doctor_username=doc_username,
                appt_time=appt_time
            )
            # 更新数据
            data["appointments"][appt_id] = appointment.to_dict()
            data["users"][patient["username"]]["appointments"].append(appt_id)
            data["users"][doc_username]["appointments"].append(appt_id)
            save_data(data)
            print(f"预约成功！预约ID：{appt_id}")

        elif choice == "2":
            # 查看我的预约
            appt_ids = patient["appointments"]
            if not appt_ids:
                print("暂无预约记录！")
                continue
            print("\n===== 我的预约 =====")
            for appt_id in appt_ids:
                appt = data["appointments"].get(appt_id)
                if not appt:
                    continue
                doctor = data["users"][appt["doctor_username"]]
                print(f"预约ID：{appt_id}")
                print(f"医生：{doctor['real_name']}")
                print(f"时间：{appt['appt_time']}")
                print(f"状态：{appt['status']}")
                print("-" * 30)

        elif choice == "3":
            # 取消预约
            appt_ids = [aid for aid in patient["appointments"]
                        if data["appointments"].get(aid, {}).get("status") == "pending"]
            if not appt_ids:
                print("暂无可取消的预约（仅待接诊预约可取消）！")
                continue
            print("\n可取消的预约：")
            for i, appt_id in enumerate(appt_ids, 1):
                appt = data["appointments"][appt_id]
                doctor = data["users"][appt["doctor_username"]]
                print(f"{i}. 预约ID：{appt_id} | 医生：{doctor['real_name']} | 时间：{appt['appt_time']}")
            try:
                cancel_idx = int(input("请选择要取消的预约序号：").strip()) - 1
                if cancel_idx < 0 or cancel_idx >= len(appt_ids):
                    print("无效序号！")
                    continue
                appt_id = appt_ids[cancel_idx]
                data["appointments"][appt_id]["status"] = "canceled"
                save_data(data)
                print("预约已取消！")
            except ValueError:
                print("请输入数字！")
                continue

        elif choice == "4":
            # 查看我的病历
            records = [r for r in data["medical_records"].values()
                       if r["patient_username"] == patient["username"]]
            if not records:
                print("暂无病历记录！")
                continue
            print("\n===== 我的病历 =====")
            for record in records:
                doctor = data["users"][record["doctor_username"]]
                print(f"病历ID：{record['record_id']}")
                print(f"接诊医生：{doctor['real_name']}")
                print(f"诊断结果：{record['diagnosis']}")
                print("处方：")
                for pres in record["prescriptions"]:
                    print(f"  - {pres['drug']} | 剂量：{pres['dose']}")
                print("-" * 30)

        elif choice == "5":
            print("退出患者中心！")
            break

        else:
            print("无效选择！")


def doctor_menu(data: Dict, doctor: Dict) -> None:
    """医生功能菜单"""
    while True:
        print("\n===== 医生中心 =====")
        print("1. 查看我的预约")
        print("2. 接诊患者（生成病历）")
        print("3. 查看我的接诊记录")
        print("4. 退出")
        choice = input("请选择操作（1-4）：").strip()

        if choice == "1":
            # 查看我的预约
            appt_ids = doctor["appointments"]
            if not appt_ids:
                print("暂无预约记录！")
                continue
            print("\n===== 我的预约 =====")
            for appt_id in appt_ids:
                appt = data["appointments"].get(appt_id)
                if not appt:
                    continue
                patient = data["users"][appt["patient_username"]]
                print(f"预约ID：{appt_id}")
                print(f"患者：{patient['real_name']} | 身份证号：{patient['id_card']}")
                print(f"时间：{appt['appt_time']}")
                print(f"状态：{appt['status']}")
                print("-" * 30)

        elif choice == "2":
            # 接诊患者
            pending_appts = [
                (aid, appt) for aid, appt in data["appointments"].items()
                if appt["doctor_username"] == doctor["username"] and appt["status"] == "pending"
            ]
            if not pending_appts:
                print("暂无待接诊预约！")
                continue
            print("\n===== 待接诊列表 =====")
            for i, (appt_id, appt) in enumerate(pending_appts, 1):
                patient = data["users"][appt["patient_username"]]
                print(f"{i}. 预约ID：{appt_id} | 患者：{patient['real_name']} | 时间：{appt['appt_time']}")
            try:
                consult_idx = int(input("请选择要接诊的预约序号：").strip()) - 1
                if consult_idx < 0 or consult_idx >= len(pending_appts):
                    print("无效序号！")
                    continue
                appt_id, appt = pending_appts[consult_idx]
            except ValueError:
                print("请输入数字！")
                continue

            # 生成病历
            print(f"\n===== 接诊 {data['users'][appt['patient_username']]['real_name']} =====")
            diagnosis = input("请输入诊断结果：").strip()
            prescriptions = []
            while True:
                add_pres = input("是否添加处方？（y/n）：").lower().strip()
                if add_pres != "y":
                    break
                drug = input("药品名称：").strip()
                dose = input("剂量/用法：").strip()
                prescriptions.append({"drug": drug, "dose": dose})

            # 创建病历
            record_id = generate_id("REC")
            record = MedicalRecord(
                record_id=record_id,
                appt_id=appt_id,
                patient_username=appt["patient_username"],
                doctor_username=doctor["username"],
                diagnosis=diagnosis,
                prescriptions=prescriptions
            )
            # 更新数据
            data["medical_records"][record_id] = record.to_dict()
            data["appointments"][appt_id]["status"] = "completed"
            save_data(data)
            print(f"接诊完成！病历ID：{record_id}")

        elif choice == "3":
            # 查看我的接诊记录
            records = [r for r in data["medical_records"].values()
                       if r["doctor_username"] == doctor["username"]]
            if not records:
                print("暂无接诊记录！")
                continue
            print("\n===== 我的接诊记录 =====")
            for record in records:
                patient = data["users"][record["patient_username"]]
                print(f"病历ID：{record['record_id']}")
                print(f"患者：{patient['real_name']} | 身份证号：{patient['id_card']}")
                print(f"诊断结果：{record['diagnosis']}")
                print("-" * 30)

        elif choice == "4":
            print("退出医生中心！")
            break

        else:
            print("无效选择！")


def admin_menu(data: Dict, admin: Dict) -> None:
    """管理员功能菜单"""
    while True:
        print("\n===== 管理员中心 =====")
        print("1. 科室管理")
        print("2. 医生出诊时间管理")
        print("3. 系统数据统计")
        print("4. 退出")
        choice = input("请选择操作（1-4）：").strip()

        if choice == "1":
            # 科室管理
            while True:
                print("\n===== 科室管理 =====")
                print("1. 添加科室")
                print("2. 修改科室名称")
                print("3. 删除科室")
                print("4. 查看所有科室")
                print("5. 返回上一级")
                dept_choice = input("请选择操作（1-5）：").strip()

                if dept_choice == "1":
                    # 添加科室
                    dept_id = input("请输入科室ID（字母+数字，如NEIKE）：").strip()
                    if dept_id in data["departments"]:
                        print("该科室ID已存在！")
                        continue
                    dept_name = input("请输入科室名称：").strip()
                    dept = Department(dept_id, dept_name)
                    data["departments"][dept_id] = dept.to_dict()
                    save_data(data)
                    print(f"科室 {dept_name} 添加成功！")

                elif dept_choice == "2":
                    # 修改科室名称
                    if not data["departments"]:
                        print("暂无科室！")
                        continue
                    print("\n当前科室：")
                    for dept_id, dept in data["departments"].items():
                        print(f"ID：{dept_id} | 名称：{dept['dept_name']}")
                    dept_id = input("请输入要修改的科室ID：").strip()
                    if dept_id not in data["departments"]:
                        print("科室ID不存在！")
                        continue
                    new_name = input("请输入新科室名称：").strip()
                    data["departments"][dept_id]["dept_name"] = new_name
                    save_data(data)
                    print("科室名称修改成功！")

                elif dept_choice == "3":
                    # 删除科室
                    if not data["departments"]:
                        print("暂无科室！")
                        continue
                    print("\n当前科室：")
                    for dept_id, dept in data["departments"].items():
                        print(f"ID：{dept_id} | 名称：{dept['dept_name']} | 医生数：{len(dept['doctors'])}")
                    dept_id = input("请输入要删除的科室ID：").strip()
                    if dept_id not in data["departments"]:
                        print("科室ID不存在！")
                        continue
                    if data["departments"][dept_id]["doctors"]:
                        print("该科室下还有医生，无法删除！")
                        continue
                    del data["departments"][dept_id]
                    save_data(data)
                    print("科室删除成功！")

                elif dept_choice == "4":
                    # 查看所有科室
                    if not data["departments"]:
                        print("暂无科室！")
                        continue
                    print("\n===== 所有科室 =====")
                    for dept_id, dept in data["departments"].items():
                        print(f"ID：{dept_id}")
                        print(f"名称：{dept['dept_name']}")
                        print(
                            f"医生列表：{', '.join([data['users'][doc]['real_name'] for doc in dept['doctors']]) if dept['doctors'] else '无'}")
                        print("-" * 30)

                elif dept_choice == "5":
                    break

                else:
                    print("无效选择！")

        elif choice == "2":
            # 医生出诊时间管理
            print("\n===== 出诊时间管理 =====")
            print("1. 设置医生出诊日期")
            print("2. 查看医生出诊日期")
            work_choice = input("请选择操作（1-2）：").strip()

            if work_choice == "1":
                # 选择医生
                doctors = [(uname, user) for uname, user in data["users"].items() if user["role"] == "doctor"]
                if not doctors:
                    print("暂无医生！")
                    continue
                print("\n医生列表：")
                for i, (uname, doc) in enumerate(doctors, 1):
                    dept = data["departments"][doc["department_id"]]
                    print(f"{i}. 姓名：{doc['real_name']} | 科室：{dept['dept_name']} | 工号：{doc['doctor_id']}")
                try:
                    doc_idx = int(input("请选择医生序号：").strip()) - 1
                    if doc_idx < 0 or doc_idx >= len(doctors):
                        print("无效序号！")
                        continue
                    doc_username, doctor_obj = doctors[doc_idx]
                except ValueError:
                    print("请输入数字！")
                    continue

                # 设置出诊日期
                date_str = input("请输入出诊日期（YYYY-MM-DD，多个日期用逗号分隔）：").strip()
                dates = [d.strip() for d in date_str.split(",")]
                valid_dates = []
                for d in dates:
                    try:
                        datetime.datetime.strptime(d, "%Y-%m-%d")
                        valid_dates.append(d)
                    except ValueError:
                        print(f"日期 {d} 格式错误，已忽略")
                if not valid_dates:
                    print("无有效日期！")
                    continue
                # 去重并合并
                current_days = doctor_obj["working_days"]
                new_days = list(set(current_days + valid_dates))
                data["users"][doc_username]["working_days"] = new_days
                save_data(data)
                print(f"{doctor_obj['real_name']} 出诊日期已更新：{', '.join(new_days)}")

            elif work_choice == "2":
                # 查看医生出诊日期
                doctors = [(uname, user) for uname, user in data["users"].items() if user["role"] == "doctor"]
                if not doctors:
                    print("暂无医生！")
                    continue
                print("\n医生列表：")
                for i, (uname, doc) in enumerate(doctors, 1):
                    dept = data["departments"][doc["department_id"]]
                    print(f"{i}. 姓名：{doc['real_name']} | 科室：{dept['dept_name']}")
                try:
                    doc_idx = int(input("请选择医生序号：").strip()) - 1
                    if doc_idx < 0 or doc_idx >= len(doctors):
                        print("无效序号！")
                        continue
                    doc_username, doctor_obj = doctors[doc_idx]
                    days = doctor_obj["working_days"]
                    print(f"\n{doctor_obj['real_name']} 出诊日期：{', '.join(days) if days else '暂无'}")
                except ValueError:
                    print("请输入数字！")
                    continue

            else:
                print("无效选择！")

        elif choice == "3":
            # 系统数据统计
            print("\n===== 系统数据统计 =====")
            # 用户统计
            total_users = len(data["users"])
            patient_count = len([u for u in data["users"].values() if u["role"] == "patient"])
            doctor_count = len([u for u in data["users"].values() if u["role"] == "doctor"])
            admin_count = len([u for u in data["users"].values() if u["role"] == "admin"])
            # 预约统计
            total_appts = len(data["appointments"])
            pending_appts = len([a for a in data["appointments"].values() if a["status"] == "pending"])
            completed_appts = len([a for a in data["appointments"].values() if a["status"] == "completed"])
            canceled_appts = len([a for a in data["appointments"].values() if a["status"] == "canceled"])
            # 病历统计
            total_records = len(data["medical_records"])

            print(f"总用户数：{total_users}")
            print(f"  - 患者：{patient_count}")
            print(f"  - 医生：{doctor_count}")
            print(f"  - 管理员：{admin_count}")
            print(f"科室数：{len(data['departments'])}")
            print(f"总预约数：{total_appts}")
            print(f"  - 待接诊：{pending_appts}")
            print(f"  - 已完成：{completed_appts}")
            print(f"  - 已取消：{canceled_appts}")
            print(f"总病历数：{total_records}")

        elif choice == "4":
            print("退出管理员中心！")
            break

        else:
            print("无效选择！")


# ===================== 主程序入口 =====================
def main():
    """系统主入口"""
    print("===== 医院预约挂号系统 =====")
    # 加载数据
    data = load_data()
    # 初始化默认管理员（首次运行时）
    if not any(u["role"] == "admin" for u in data["users"].values()):
        admin_uname = "admin"
        admin_pwd = hash_password("admin123456")
        default_admin = Admin(admin_uname, admin_pwd, "系统管理员")
        data["users"][admin_uname] = default_admin.to_dict()
        save_data(data)
        print(f"\n首次运行，已创建默认管理员：")
        print(f"账号：{admin_uname} | 密码：admin123456")
        print(f"请登录后及时修改密码！")

    # 主循环
    while True:
        print("\n===== 主菜单 =====")
        print("1. 登录")
        print("2. 注册")
        print("3. 退出系统")
        choice = input("请选择操作（1-3）：").strip()

        if choice == "1":
            user = login(data)
            if user:
                if user["role"] == "patient":
                    patient_menu(data, user)
                elif user["role"] == "doctor":
                    doctor_menu(data, user)
                elif user["role"] == "admin":
                    admin_menu(data, user)

        elif choice == "2":
            register(data)

        elif choice == "3":
            print("感谢使用，再见！")
            break

        else:
            print("无效选择！")


if __name__ == "__main__":
    main()