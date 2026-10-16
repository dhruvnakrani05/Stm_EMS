# Employee Management System (EMS)

A comprehensive, robust, and modern Django-based Employee Management System (EMS) designed to streamline HR operations, attendance tracking, and payroll processing. The payroll module is engineered with ACID transactional properties to ensure absolute financial and data consistency.

---

## 🚀 Key Features

### 📊 Dashboard
- **Real-time Analytics**: Quick insights into total employee strength, today's attendance rate, monthly payroll budget, and status distributions.
- **Activity Log**: View recent administrative and payroll actions at a glance.

### 👥 Employee Directory
- **Profile Management**: Manage complete employee lifecycle information (personal details, department, designation, joining date, and status).
- **Search & Filters**: Easily query and filter employees by department, status, or search terms.

### 📅 Attendance Tracking
- **Daily Attendance**: Track check-in/out times, working hours, and status (Present, Absent, Late, On Leave).
- **Monthly Attendance Sheets**: View comprehensive monthly logs for each employee.
- **Configurable Settings**: Define weekly off-days (e.g., Thursday/Sunday) and default working days directly in the settings.

### 💳 Payroll Module (ACID Compliant)
- **Robust Transaction Management**: Generated using atomic DB transactions to guarantee that salary records, allowances, deductions, and payment records remain completely consistent, with automatic rollbacks if any single step fails.
- **Salary Components**: Supports configurable base pay, custom allowances (e.g., transport, housing), and deductions (e.g., tax, provident fund).
- **Payslip Generation**: Generate and download detailed PDF payslips for employees.
- **Payment Statuses**: Track payment states (Unpaid, Paid, Held) with secure audit trails.

### 📈 Reports & Exports
- **Exports**: Download summaries of payroll, attendance records, and department reports.
- **PDF Generation**: Direct export of print-ready payslips.

---

## 🛠️ Prerequisites

Ensure you have the following installed on your local machine:
- **Python**: Version 3.8 or higher
- **Git**: For version control and cloning the repository
- **web browser**: Any modern browser (Chrome, Firefox, Edge, Safari)

---

## ⚙️ Installation and Setup Guide

Follow these steps to set up and run the project locally on your device:

### Step 1: Clone the Repository
Clone this repository to your local machine:
```bash
git clone https://github.com/YOUR_USERNAME/EMS.git
cd EMS
```
*(Alternatively, you can download the repository as a ZIP file and extract it.)*

### Step 2: Create a Virtual Environment
It is highly recommended to use a virtual environment to manage project dependencies:
- **On Windows**:
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
- **On macOS/Linux**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### Step 3: Install Required Dependencies
With the virtual environment active, run the following command to install the required Python packages:
```bash
pip install -r requirements.txt
```

### Step 4: Perform Database Migrations
Create and configure the local SQLite database by running the Django migration files:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 5: Create a Superuser Account
Create an administrator account to log in to the system and manage records:
```bash
python manage.py createsuperuser
```
Follow the interactive prompts to set a username, email, and password.

### Step 6: Start the Development Server
Run the local server using:
```bash
python manage.py runserver
```
Once the server starts successfully, you will see output indicating that the server is running at:
`http://127.0.0.1:8000/`

---

## 🖥️ Viewing the Project

1. Open your web browser and navigate to: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
2. Log in using the **superuser credentials** you created in Step 5.
3. Access the full suite of tools:
   - Navigate to `/employees/` to start adding employee profiles.
   - Go to `/attendance/` to manage daily check-ins.
   - Go to `/payroll/` to define salary configurations and run monthly payroll.
   - Go to `/admin/` to manage system users and custom models.

---

## 📁 Project Directory Structure

```text
EMS/
├── accounts/         # Authentication and custom roles (CustomUser model)
├── attendance/       # Attendance tracking, check-in logs, and calendars
├── dashboard/        # Dashboard layout, statistics aggregation
├── employees/        # Profile management, department/designation logic
├── ems_project/      # Main project settings, URLs, routing configurations
├── media/            # Uploaded files (profile images, documents)
├── payroll/          # ACID payroll creation, allowances, deductions, payslips
├── reports/          # Report generation, PDF formatting functions
├── static/           # Global static assets (CSS, JS, images)
├── templates/        # Project-level HTML templates and base layout
├── db.sqlite3        # Local SQLite database (excluded from Git)
├── requirements.txt  # Python package dependencies list
└── manage.py         # Django command-line utility
```

---

## 🛡️ License
Distributed under the MIT License. See `LICENSE` for more information.
