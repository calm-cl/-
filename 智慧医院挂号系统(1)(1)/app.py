import json
import hashlib
import datetime
import re
from typing import List, Dict, Optional
from flask import Flask, render_template, request, redirect, url_for, session, flash

# ===================== 初始化Flask应用 =====================
app = Flask(__name__)
app.secret_key = "hospital_2025_secret_key"  # 会话加密密钥（生产环境需改为随机字符串）

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
    """检查预约冲突"""
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


def login_required(f):
    """登录验证装饰器"""

    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("请先登录！")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


def role_required(roles):
    """角色验证装饰器"""

    def decorator(f):
        def wrapper(*args, **kwargs):
            if "role" not in session or session["role"] not in roles:
                flash("无权限访问！")
                return redirect(url_for("index"))
            return f(*args, **kwargs)

        wrapper.__name__ = f.__name__
        return wrapper

    return decorator


# ===================== 路由定义 =====================
@app.route("/")
def index():
    """首页"""
    return render_template("index.html", user=session.get("username"), role=session.get("role"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """登录页面"""
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        data = load_data()

        # 验证账号密码
        if username not in data["users"]:
            flash("账号不存在！")
            return render_template("login.html")

        user = data["users"][username]
        if user["password_hash"] != hash_password(password):
            flash("密码错误！")
            return render_template("login.html")

        # 保存登录态
        session["username"] = username
        session["role"] = user["role"]
        session["real_name"] = user["real_name"]
        flash(f"登录成功！欢迎{user['real_name']}")

        # 根据角色跳转
        if user["role"] == "patient":
            return redirect(url_for("patient"))
        elif user["role"] == "doctor":
            return redirect(url_for("doctor"))
        elif user["role"] == "admin":
            return redirect(url_for("admin"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """注册页面"""
    data = load_data()
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        role = request.form.get("role").lower().strip()
        real_name = request.form.get("real_name").strip()

        # 基础验证
        if not re.match(r"^[a-zA-Z0-9]{4,20}$", username):
            flash("账号格式错误！需4-20位字母+数字组合")
            return render_template("register.html", departments=data["departments"])
        if username in data["users"]:
            flash("该账号已存在！")
            return render_template("register.html", departments=data["departments"])
        if len(password) < 6:
            flash("密码长度需至少6位！")
            return render_template("register.html", departments=data["departments"])
        if role not in ["patient", "doctor", "admin"]:
            flash("无效角色！")
            return render_template("register.html", departments=data["departments"])

        password_hash = hash_password(password)

        # 按角色处理
        if role == "patient":
            id_card = request.form.get("id_card").strip()
            if not re.match(PATIENT_ID_REGEX, id_card):
                flash("身份证号格式错误！")
                return render_template("register.html", departments=data["departments"])
            # 检查身份证号唯一性
            for u in data["users"].values():
                if u["role"] == "patient" and u["id_card"] == id_card:
                    flash("该身份证号已注册！")
                    return render_template("register.html", departments=data["departments"])
            user = Patient(username, password_hash, real_name, id_card)

        elif role == "doctor":
            doctor_id = request.form.get("doctor_id").strip()
            dept_id = request.form.get("department_id").strip()
            if not re.match(DOCTOR_ID_REGEX, doctor_id):
                flash("医生工号格式错误（需6位数字）！")
                return render_template("register.html", departments=data["departments"])
            # 检查工号唯一性
            for u in data["users"].values():
                if u["role"] == "doctor" and u["doctor_id"] == doctor_id:
                    flash("该医生工号已注册！")
                    return render_template("register.html", departments=data["departments"])
            if dept_id not in data["departments"]:
                flash("科室ID不存在！")
                return render_template("register.html", departments=data["departments"])
            user = Doctor(username, password_hash, real_name, doctor_id, dept_id)
            # 医生加入科室
            data["departments"][dept_id]["doctors"].append(username)

        else:  # admin
            user = Admin(username, password_hash, real_name)

        # 保存用户
        data["users"][username] = user.to_dict()
        save_data(data)
        flash("注册成功！请登录")
        return redirect(url_for("login"))

    return render_template("register.html", departments=data["departments"])


@app.route("/logout")
def logout():
    """退出登录"""
    session.clear()
    flash("已退出登录！")
    return redirect(url_for("index"))


@app.route("/patient")
@login_required
@role_required(["patient"])
def patient():
    """患者中心"""
    data = load_data()
    username = session["username"]
    patient = data["users"][username]

    # 获取患者的预约和病历
    appointments = []
    for appt_id in patient["appointments"]:
        appt = data["appointments"].get(appt_id)
        if appt:
            doctor = data["users"][appt["doctor_username"]]
            appointments.append({
                "id": appt_id,
                "doctor_name": doctor["real_name"],
                "time": appt["appt_time"],
                "status": appt["status"]
            })

    medical_records = []
    for record in data["medical_records"].values():
        if record["patient_username"] == username:
            doctor = data["users"][record["doctor_username"]]
            medical_records.append({
                "id": record["record_id"],
                "doctor_name": doctor["real_name"],
                "diagnosis": record["diagnosis"],
                "prescriptions": record["prescriptions"]
            })

    # 获取科室和医生列表（用于预约）
    departments = list(data["departments"].items())
    doctors_by_dept = {}
    for dept_id, dept in data["departments"].items():
        doctors = []
        for doc_username in dept["doctors"]:
            doc = data["users"][doc_username]
            doctors.append({
                "username": doc_username,
                "name": doc["real_name"],
                "id": doc["doctor_id"],
                "working_days": doc["working_days"]
            })
        doctors_by_dept[dept_id] = doctors

    return render_template(
        "patient.html",
        real_name=session["real_name"],
        departments=departments,
        doctors_by_dept=doctors_by_dept,
        valid_hours=VALID_APPOINTMENT_HOURS,
        appointments=appointments,
        medical_records=medical_records
    )


@app.route("/patient/appointment", methods=["POST"])
@login_required
@role_required(["patient"])
def patient_appointment():
    """患者预约挂号"""
    data = load_data()
    username = session["username"]
    dept_id = request.form.get("dept_id")
    doc_username = request.form.get("doc_username")
    appt_date = request.form.get("appt_date")
    appt_hour = request.form.get("appt_hour")

    # 验证参数
    appt_time = f"{appt_date} {appt_hour}:00"
    if not validate_time_format(appt_time):
        flash("预约时间格式错误或不在有效时段！")
        return redirect(url_for("patient"))

    # 检查医生出诊日期
    working_days = get_doctor_working_days(data, doc_username)
    if appt_date not in working_days:
        flash("该日期医生不出诊！")
        return redirect(url_for("patient"))

    # 检查预约冲突
    if check_appointment_conflict(data, username, appt_time, "patient"):
        flash("您已在该时间有其他预约！")
        return redirect(url_for("patient"))
    if check_appointment_conflict(data, doc_username, appt_time, "doctor"):
        flash("该医生在该时间已有预约！")
        return redirect(url_for("patient"))

    # 创建预约
    appt_id = generate_id("APPT")
    appointment = Appointment(
        appt_id=appt_id,
        patient_username=username,
        doctor_username=doc_username,
        appt_time=appt_time
    )
    # 更新数据
    data["appointments"][appt_id] = appointment.to_dict()
    data["users"][username]["appointments"].append(appt_id)
    data["users"][doc_username]["appointments"].append(appt_id)
    save_data(data)

    flash(f"预约成功！预约ID：{appt_id}")
    return redirect(url_for("patient"))


@app.route("/patient/cancel_appointment/<appt_id>")
@login_required
@role_required(["patient"])
def cancel_appointment(appt_id):
    """取消预约"""
    data = load_data()
    appt = data["appointments"].get(appt_id)
    if not appt or appt["patient_username"] != session["username"] or appt["status"] != "pending":
        flash("无法取消该预约！")
        return redirect(url_for("patient"))

    data["appointments"][appt_id]["status"] = "canceled"
    save_data(data)
    flash("预约已取消！")
    return redirect(url_for("patient"))


@app.route("/doctor")
@login_required
@role_required(["doctor"])
def doctor():
    """医生中心"""
    data = load_data()
    username = session["username"]
    doctor = data["users"][username]

    # 获取医生的预约
    appointments = []
    for appt_id in doctor["appointments"]:
        appt = data["appointments"].get(appt_id)
        if appt:
            patient = data["users"][appt["patient_username"]]
            appointments.append({
                "id": appt_id,
                "patient_name": patient["real_name"],
                "patient_id_card": patient["id_card"],
                "time": appt["appt_time"],
                "status": appt["status"]
            })

    # 获取接诊记录
    consult_records = []
    for record in data["medical_records"].values():
        if record["doctor_username"] == username:
            patient = data["users"][record["patient_username"]]
            consult_records.append({
                "id": record["record_id"],
                "patient_name": patient["real_name"],
                "patient_id_card": patient["id_card"],
                "diagnosis": record["diagnosis"]
            })

    return render_template(
        "doctor.html",
        real_name=session["real_name"],
        appointments=appointments,
        consult_records=consult_records
    )


@app.route("/doctor/consult/<appt_id>", methods=["POST"])
@login_required
@role_required(["doctor"])
def doctor_consult(appt_id):
    """接诊患者生成病历"""
    data = load_data()
    appt = data["appointments"].get(appt_id)
    doctor_username = session["username"]

    # 验证预约
    if not appt or appt["doctor_username"] != doctor_username or appt["status"] != "pending":
        flash("无效的预约记录！")
        return redirect(url_for("doctor"))

    # 获取表单数据
    diagnosis = request.form.get("diagnosis").strip()
    drugs = request.form.getlist("drug[]")
    doses = request.form.getlist("dose[]")

    # 构建处方列表
    prescriptions = []
    for drug, dose in zip(drugs, doses):
        if drug and dose:
            prescriptions.append({"drug": drug.strip(), "dose": dose.strip()})

    # 创建病历
    record_id = generate_id("REC")
    record = MedicalRecord(
        record_id=record_id,
        appt_id=appt_id,
        patient_username=appt["patient_username"],
        doctor_username=doctor_username,
        diagnosis=diagnosis,
        prescriptions=prescriptions
    )

    # 更新数据
    data["medical_records"][record_id] = record.to_dict()
    data["appointments"][appt_id]["status"] = "completed"
    save_data(data)

    flash(f"接诊完成！病历ID：{record_id}")
    return redirect(url_for("doctor"))


@app.route("/admin")
@login_required
@role_required(["admin"])
def admin():
    """管理员中心"""
    data = load_data()

    # 统计数据
    total_users = len(data["users"])
    patient_count = len([u for u in data["users"].values() if u["role"] == "patient"])
    doctor_count = len([u for u in data["users"].values() if u["role"] == "doctor"])
    admin_count = len([u for u in data["users"].values() if u["role"] == "admin"])
    total_appts = len(data["appointments"])
    pending_appts = len([a for a in data["appointments"].values() if a["status"] == "pending"])
    completed_appts = len([a for a in data["appointments"].values() if a["status"] == "completed"])
    canceled_appts = len([a for a in data["appointments"].values() if a["status"] == "canceled"])
    total_records = len(data["medical_records"])

    # 科室列表
    departments = list(data["departments"].items())

    # 医生列表
    doctors = []
    for uname, user in data["users"].items():
        if user["role"] == "doctor":
            dept = data["departments"].get(user["department_id"], {"dept_name": "未知科室"})
            doctors.append({
                "username": uname,
                "name": user["real_name"],
                "id": user["doctor_id"],
                "dept_name": dept["dept_name"],
                "working_days": user["working_days"]
            })

    return render_template(
        "admin.html",
        real_name=session["real_name"],
        stats={
            "total_users": total_users,
            "patient_count": patient_count,
            "doctor_count": doctor_count,
            "admin_count": admin_count,
            "dept_count": len(departments),
            "total_appts": total_appts,
            "pending_appts": pending_appts,
            "completed_appts": completed_appts,
            "canceled_appts": canceled_appts,
            "total_records": total_records
        },
        departments=departments,
        doctors=doctors
    )


@app.route("/admin/add_dept", methods=["POST"])
@login_required
@role_required(["admin"])
def add_dept():
    """添加科室"""
    data = load_data()
    dept_id = request.form.get("dept_id").strip()
    dept_name = request.form.get("dept_name").strip()

    if dept_id in data["departments"]:
        flash("该科室ID已存在！")
        return redirect(url_for("admin"))

    dept = Department(dept_id, dept_name)
    data["departments"][dept_id] = dept.to_dict()
    save_data(data)

    flash(f"科室 {dept_name} 添加成功！")
    return redirect(url_for("admin"))


@app.route("/admin/delete_dept/<dept_id>")
@login_required
@role_required(["admin"])
def delete_dept(dept_id):
    """删除科室"""
    data = load_data()
    dept = data["departments"].get(dept_id)
    if not dept:
        flash("科室不存在！")
        return redirect(url_for("admin"))
    if dept["doctors"]:
        flash("该科室下还有医生，无法删除！")
        return redirect(url_for("admin"))

    del data["departments"][dept_id]
    save_data(data)
    flash("科室删除成功！")
    return redirect(url_for("admin"))


@app.route("/admin/set_working_days", methods=["POST"])
@login_required
@role_required(["admin"])
def set_working_days():
    """设置医生出诊日期"""
    data = load_data()
    doc_username = request.form.get("doc_username")
    dates_str = request.form.get("working_days").strip()

    doctor = data["users"].get(doc_username)
    if not doctor or doctor["role"] != "doctor":
        flash("医生不存在！")
        return redirect(url_for("admin"))

    # 解析日期
    dates = [d.strip() for d in dates_str.split(",")]
    valid_dates = []
    for d in dates:
        try:
            datetime.datetime.strptime(d, "%Y-%m-%d")
            valid_dates.append(d)
        except ValueError:
            flash(f"日期 {d} 格式错误，已忽略")

    if not valid_dates:
        flash("无有效日期！")
        return redirect(url_for("admin"))

    # 更新出诊日期（去重）
    doctor["working_days"] = list(set(doctor["working_days"] + valid_dates))
    data["users"][doc_username] = doctor
    save_data(data)

    flash(f"{doctor['real_name']} 出诊日期已更新！")
    return redirect(url_for("admin"))


# ========== 新增：删除医生路由 ==========
@app.route("/admin/delete_doctor/<doc_username>")
@login_required
@role_required(["admin"])
def delete_doctor(doc_username):
    """删除医生"""
    data = load_data()
    doctor = data["users"].get(doc_username)

    # 1. 验证医生是否存在
    if not doctor or doctor["role"] != "doctor":
        flash("医生账号不存在！")
        return redirect(url_for("admin"))

    # 2. 从所属科室中移除该医生
    dept_id = doctor["department_id"]
    if dept_id in data["departments"]:
        dept = data["departments"][dept_id]
        if doc_username in dept["doctors"]:
            dept["doctors"].remove(doc_username)

    # 3. 处理该医生的关联预约（待接诊的标记为取消，已完成/取消的保留）
    canceled_appts = []
    for appt_id, appt in data["appointments"].items():
        if appt["doctor_username"] == doc_username and appt["status"] == "pending":
            data["appointments"][appt_id]["status"] = "canceled"
            canceled_appts.append(appt_id)

    # 4. 删除医生用户记录
    del data["users"][doc_username]
    save_data(data)

    # 提示信息
    flash(f"医生 {doctor['real_name']}（账号：{doc_username}）已成功删除！")
    if canceled_appts:
        flash(f"自动取消该医生的待接诊预约：{','.join(canceled_appts)}")

    return redirect(url_for("admin"))


# ========== 新增结束 ==========

# ===================== 启动程序 =====================
if __name__ == "__main__":
    # 初始化默认管理员（首次运行）
    data = load_data()
    if not any(u["role"] == "admin" for u in data["users"].values()):
        admin_uname = "admin"
        admin_pwd = hash_password("admin123456")
        default_admin = Admin(admin_uname, admin_pwd, "系统管理员")
        data["users"][admin_uname] = default_admin.to_dict()
        save_data(data)
        print("默认管理员已创建：账号admin，密码admin123456")

    app.run(debug=True, host="0.0.0.0", port=5000)