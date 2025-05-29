import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client, Client
import pandas as pd

# Replace with your own values
url = "https://nlbifkmfeutevzgecpwo.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5sYmlma21mZXV0ZXZ6Z2VjcHdvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0OTIzNjEsImV4cCI6MjA2NDA2ODM2MX0.ZMA5u7qPPtuS1GlaaeWNRXQdQZQjqg4UqD9gOL9Qi1k"

supabase: Client = create_client(url, key)


# --- Database ---
def get_connection():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS leaves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        start_date TEXT,
        end_date TEXT,
        FOREIGN KEY(employee_id) REFERENCES employees(id))''')
   

    conn.commit()

# Fetch all leave records with employee names
response = supabase.table("leaves").select("*, employees(name)").execute()

# Check for errors
if response.error:
    st.error(f"Error fetching data: {response.error.message}")
else:
    df = pd.DataFrame(response.data)
    st.dataframe(df)


# --- Helper Functions ---
def get_employees():
    response = supabase.table("employees").select("*").execute()
employees = response.data


def get_leaves():
   response = supabase.table("leaves").select("*, employees(name)").execute()
leave_data = pd.DataFrame(response.data)


def add_employee(name):
    supabase.table("employees").insert({"name": name}).execute()

def add_leave(employee_id, start_date, end_date):
    supabase.table("leaves").insert({
    "employee_id": employee_id,
    "start_date": str(start_date),
    "end_date": str(end_date),
    "leave_type": leave_type
}).execute()


def delete_leave(leave_id):
    conn.execute("DELETE FROM leaves WHERE id = ?", (leave_id,))
    conn.commit()

def get_leave_days(start_date, end_date):
    days = pd.date_range(start=start_date, end=end_date, freq='B')  # 'B' = business days (excludes weekends)
    return len(days)


# --- App UI ---
st.set_page_config(layout="wide")

from PIL import Image

# Layout: Title on the left, logo on the right
logo = Image.open("Allfreight.png")
col1, col2 = st.columns([6, 1])

with col1:
    st.title("📅 Employee Leave Calendar")

with col2:
    st.image(logo, use_container_width=True)

conn = get_connection()
init_db()
# Fetch employees from Supabase
response = supabase.table("employees").select("*").execute()
if response.error:
    st.error("Failed to load employees")
else:
    employee_list = response.data

    # Create a name → id mapping
    employee_dict = {emp["name"]: emp["id"] for emp in employee_list}

    # Dropdown for employee names
    selected_employee_name = st.selectbox("Select Employee", list(employee_dict.keys()))

    # Get the ID from the selected name
    employee_id = employee_dict[selected_employee_name]

# Add new employee
with st.sidebar:
    st.header("👤 Add Employee")
    new_employee = st.text_input("Name")
    if st.button("Add Employee") and new_employee:
        add_employee(new_employee)
        st.success("Employee added!")

st.sidebar.markdown("<hr style='border: 1px solid #bbb;'>", unsafe_allow_html=True)


# Add new leave
st.sidebar.header("📌 Add Leave")
employee_list = get_employees()
employee_dict = {name: eid for eid, name in employee_list}
employee_name = st.sidebar.selectbox("Select Employee", employee_dict.keys())
leave_start = st.sidebar.date_input("Start Date")
leave_end = st.sidebar.date_input("End Date")
leave_type = st.sidebar.selectbox(
    "Leave Type",
    ["Annual Leave", "Personal Leave", "Unpaid Leave", "Sick Leave", "Other"]
)
if st.sidebar.button("Add Leave"):
    if leave_end < leave_start:
        st.sidebar.error("End date must be after start date.")
    else:
        add_leave(employee_dict[employee_name], leave_start.isoformat(), leave_end.isoformat())
        st.sidebar.success("Leave added!")



st.sidebar.markdown("<hr style='border: 1px solid #bbb;'>", unsafe_allow_html=True) 




# Search Records
st.sidebar.header("🔍 Search Leave Records")
search_employees = ["All"] + list(employee_dict.keys())
search_name = st.sidebar.selectbox("Filter by Employee", search_employees)
search_start = st.sidebar.date_input("Start Date (Search)", value=None, key="search_start")
search_end = st.sidebar.date_input("End Date (Search)", value=None, key="search_end")

if st.sidebar.button("Search"):
    query = """
        SELECT l.id, e.name, l.start_date, l.end_date
        FROM leaves l
        JOIN employees e ON l.employee_id = e.id
        WHERE 1=1
    """
    params = []

    if search_name != "All":
        query += " AND e.name = ?"
        params.append(search_name)

    if search_start:
        query += " AND date(l.start_date) >= date(?)"
        params.append(search_start.isoformat())

    if search_end:
        query += " AND date(l.end_date) <= date(?)"
        params.append(search_end.isoformat())

    filtered_leaves = pd.read_sql_query(query, conn, params=params)
    st.subheader("🔍 Search Results")
    if not filtered_leaves.empty:
        filtered_leaves['start_date'] = pd.to_datetime(filtered_leaves['start_date']).dt.date
        filtered_leaves['end_date'] = pd.to_datetime(filtered_leaves['end_date']).dt.date
        st.dataframe(filtered_leaves, use_container_width=True)
    else:
        st.info("No records match your search.")
st.sidebar.markdown("<hr style='border: 1px solid #bbb;'>", unsafe_allow_html=True)

# =======================
# 📋 LEAVE REPORT SECTION
# =======================
st.sidebar.subheader("📋 Leave Report")

# Sidebar date inputs
report_start = st.sidebar.date_input("Start Date", key="report_start")
report_end = st.sidebar.date_input("End Date", key="report_end")

# Leave report trigger button
generate_report = st.sidebar.button("Generate Report")

if generate_report:
    if report_start and report_end and report_start <= report_end:
        # Query leave records within range
        query = """
            SELECT e.name AS employee_name, l.leave_type, l.start_date, l.end_date
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.start_date <= ? AND l.end_date >= ?
            ORDER BY l.start_date
        """
        leave_df = pd.read_sql_query(query, conn, params=(report_end, report_start))

        st.subheader("📄 Leave Report Results")
        if leave_df.empty:
            st.info("No leave found in the selected date range.")
        else:
            st.dataframe(leave_df)

            # Optional download
            csv = leave_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Report as CSV",
                data=csv,
                file_name='leave_report.csv',
                mime='text/csv',
            )
    else:
        st.warning("Please select a valid start and end date.")


st.sidebar.markdown("<hr style='border: 1px solid #bbb;'>", unsafe_allow_html=True)
# Remove employee
st.sidebar.header("❌ Remove Employee")

# Get the latest employee list
employee_df = pd.read_sql_query("SELECT id, name FROM employees ORDER BY name", conn)
employee_dict = dict(zip(employee_df['name'], employee_df['id']))

if employee_dict:
    remove_name = st.sidebar.selectbox("Select Employee to Remove", list(employee_dict.keys()), key="remove_employee")
    confirm = st.sidebar.checkbox("⚠️ Confirm removal")

    if st.sidebar.button("Remove Employee"):
        if confirm:
            emp_id = employee_dict[remove_name]
            conn.execute("DELETE FROM leaves WHERE employee_id = ?", (emp_id,))
            supabase.table("employees").delete().eq("id", employee_id).execute()

            conn.commit()

            st.sidebar.success(f"Removed employee: {remove_name}")
            st.rerun()  # ✅ NEW: refresh the app to reflect removal
        else:
            st.sidebar.warning("Please confirm before deleting.")
else:
    st.sidebar.info("No employees to remove.")

# Monthly View
current_month = datetime.today().month
current_year = datetime.today().year
month_start = datetime(current_year, current_month, 1)
month_end = (month_start + pd.offsets.MonthEnd()).date()

st.subheader(f"📆 Leave Calendar - {month_start.strftime('%B %Y')}")
leaves = pd.read_sql_query("SELECT l.id, e.name, l.start_date, l.end_date FROM leaves l JOIN employees e ON l.employee_id = e.id", conn)
leaves['start_date'] = pd.to_datetime(leaves['start_date'])
leaves['end_date'] = pd.to_datetime(leaves['end_date'])

employees = pd.read_sql_query("SELECT * FROM employees", conn)
calendar = {}

# Generate leave ranges
for _, row in employees.iterrows():
    name = row['name']
    calendar[name] = ['' for _ in range(1, month_end.day + 1)]
    emp_leaves = leaves[leaves['name'] == name]
    total_days = 0

    for _, l in emp_leaves.iterrows():
        # Leave within this month
        for single_date in pd.date_range(start=l['start_date'], end=l['end_date']):
            if single_date.month == current_month and single_date.weekday() < 5:  # Weekday only
                calendar[name][single_date.day - 1] = '🌴'
        total_days += get_leave_days(l['start_date'], l['end_date'])

    calendar[name].append(total_days)  # Add total leave days at the end

# Display Calendar
days = [str(d) for d in range(1, month_end.day + 1)]
table_header = days + ['Total Days']
table_data = [[name] + calendar[name] for name in calendar]

df = pd.DataFrame(table_data, columns=["Employee"] + table_header)
st.dataframe(df, use_container_width=True)

# Manage Leaves
st.subheader("🗂️ Manage Leave")
if not leaves.empty:
    for idx, row in leaves.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
        col1.write(row['name'])
        col2.write(row['start_date'].date())
        col3.write(row['end_date'].date())
        if col4.button("🗑️ Delete", key=f"del_{row['id']}"):
            delete_leave(row['id'])
            st.rerun()
else:
    st.info("No leave entries yet.")

   

#python -m streamlit run app.py