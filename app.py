from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

DATA_FILE = "attendance_data.json"


def empty_data():
    return {
        "semester_start": "",
        "semester_end": "",
        "subjects": [],
        "timetable": {},
        "holidays": [],
        "attendance": {}
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        return empty_data()

    with open(DATA_FILE, "r") as f:
        content = f.read().strip()
        if not content:
            return empty_data()
        return json.loads(content)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def is_ambiguous_lab(subject):
    if not subject:
        return False
    upper = str(subject).upper()
    return "NL" in upper and "MP" in upper


def normalize_actual_subject(base_subject, actual_subject):
    if not actual_subject:
        return None

    actual_subject = str(actual_subject).strip()

    if not actual_subject:
        return None

    if is_ambiguous_lab(base_subject):
        if actual_subject in ["NL", "MP"]:
            return actual_subject
        return None

    return actual_subject


def normalize_actual_subjects(periods, saved_actual_subjects):
    normalized = []

    for i in range(7):
        base_subject = periods[i] if i < len(periods) else None
        actual_subject = saved_actual_subjects[i] if i < len(saved_actual_subjects) else None
        normalized.append(normalize_actual_subject(base_subject, actual_subject))

    return normalized


def get_row_for_date(current, timetable, attendance_data):
    day_name = current.strftime("%A")
    date_key = current.strftime("%Y-%m-%d")

    saved = attendance_data.get(date_key, {})
    saved_holiday = saved.get("holiday", False)
    saved_timetable_used = saved.get("timetable_used", "")
    saved_periods = saved.get("periods", [])
    saved_actual_subjects = saved.get("actual_subjects", [])

    is_sunday = day_name == "Sunday"
    is_saturday = day_name == "Saturday"

    if is_sunday:
        periods = []
    elif is_saturday:
        if saved_timetable_used in timetable:
            periods = timetable.get(saved_timetable_used, [])
        else:
            periods = []
    else:
        periods = timetable.get(day_name, [])

    normalized_actual_subjects = normalize_actual_subjects(periods, saved_actual_subjects)

    return {
        "date": date_key,
        "display_date": current.strftime("%d/%m/%Y"),
        "day": day_name,
        "periods": periods,
        "saved_periods": saved_periods,
        "saved_actual_subjects": normalized_actual_subjects,
        "holiday": saved_holiday or is_sunday,
        "timetable_used": saved_timetable_used if is_saturday else day_name,
        "is_sunday": is_sunday,
        "is_saturday": is_saturday
    }


@app.route("/", methods=["GET", "POST"])
def index():
    data = load_data()

    if request.method == "POST":
        semester_start = request.form.get("semester_start", "")
        semester_end = request.form.get("semester_end", "")
        subjects_raw = request.form.get("subjects", "")

        subjects = [s.strip() for s in subjects_raw.split(",") if s.strip()]

        data["semester_start"] = semester_start
        data["semester_end"] = semester_end
        data["subjects"] = subjects

        save_data(data)
        return redirect(url_for("timetable"))

    return render_template("index.html", data=data)


@app.route("/timetable", methods=["GET", "POST"])
def timetable():
    data = load_data()

    if request.method == "POST":
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        timetable = {}

        for day in days:
            periods = []
            for i in range(7):
                key = f"{day}_{i}"
                value = request.form.get(key, "").strip()
                periods.append(value if value else None)

            timetable[day] = periods

        data["timetable"] = timetable
        save_data(data)

        return redirect(url_for("dashboard"))

    return render_template("timetable.html", data=data)


@app.route("/dashboard")
def dashboard():
    data = load_data()
    timetable = data.get("timetable", {})
    attendance_data = data.get("attendance", {})

    semester_start = data.get("semester_start")
    semester_end = data.get("semester_end")

    if not semester_start or not semester_end:
        return "Please set semester dates first"

    sem_start = datetime.strptime(semester_start, "%Y-%m-%d")
    sem_end = datetime.strptime(semester_end, "%Y-%m-%d")

    month_str = request.args.get("month")

    if month_str:
        year, month = map(int, month_str.split("-"))
        month_start = datetime(year, month, 1)
    else:
        month_start = datetime(sem_start.year, sem_start.month, 1)
        month_str = month_start.strftime("%Y-%m")

    visible_rows = []
    for i in range(31):
        current = month_start + timedelta(days=i)

        if current.month != month_start.month:
            break

        if current < sem_start:
            continue

        if current > sem_end:
            break

        visible_rows.append(get_row_for_date(current, timetable, attendance_data))

    semester_rows = []
    current = sem_start
    while current <= sem_end:
        semester_rows.append(get_row_for_date(current, timetable, attendance_data))
        current += timedelta(days=1)

    return render_template(
        "dashboard.html",
        rows=visible_rows,
        semester_rows=semester_rows,
        selected_month=month_str
    )


@app.route("/get_timetable/<day>")
def get_timetable(day):
    data = load_data()
    timetable = data.get("timetable", {})
    return jsonify(timetable.get(day, []))


@app.route("/save_attendance", methods=["POST"])
def save_attendance():
    data = load_data()

    date = request.form.get("date")
    timetable_used = request.form.get("timetable_used", "")
    holiday = request.form.get("holiday") == "on"

    periods = []
    actual_subjects = []

    for i in range(7):
        status_val = request.form.get(f"period_{i}")
        subject_val = request.form.get(f"subject_actual_{i}")

        periods.append(status_val if status_val else None)
        actual_subjects.append(subject_val if subject_val else None)

    if "attendance" not in data:
        data["attendance"] = {}

    data["attendance"][date] = {
        "periods": periods,
        "actual_subjects": actual_subjects,
        "timetable_used": timetable_used,
        "holiday": holiday
    }

    save_data(data)

    month = request.form.get("month")
    return redirect(url_for("dashboard", month=month))


if __name__ == "__main__":
    app.run(debug=True)