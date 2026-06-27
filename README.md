
### 🛠 Technology Stack

This project is structured as a full-stack system with a centralized backend, a web application frontend, and a cross-platform mobile/desktop client.

**1. Backend (Server)**
*   **Framework:** **Python & FastAPI** (providing high-performance, asynchronous REST APIs).
*   **Database:** **SQLite** (lightweight relational database, `attendance.db`).
*   **Authentication:** JWT (JSON Web Tokens) using `python-jose` and password hashing with `passlib`.
*   **Key Libraries:** `pydantic` (for data validation), `twilio` (for SMS integration, likely for notifications).

**2. Web Frontend (`/web`)**
*   **Framework:** **React 19** with **Vite** (for fast local development and bundling).
*   **Language:** **TypeScript**.
*   **Routing:** `react-router-dom` for single-page application navigation.
*   **Styling & UI:** `lucide-react` for iconography. Vanilla CSS or a custom styling framework.
*   **Data Visualization:** `recharts` for displaying attendance statistics on dashboards.
*   **Features:** `html5-qrcode` and `qrcode.react` (for web-based QR interactions), `axios` for API queries, and `nepali-date-converter` for localized dates.

**3. Mobile/Desktop App (`/src/attendance` & `pyproject.toml`)**
*   **Framework:** **BeeWare (Toga)**, which allows writing native mobile (Android/iOS) and desktop (macOS/Windows/Linux) applications purely in Python.
*   **Networking:** `httpx` for making API requests to the FastAPI backend.
*   **QR Features:** `pyzbar`, `Pillow`, and `qrcode` for reading and generating QR codes natively using device cameras.
*   **Localization:** `nepali-datetime` for handling localized calendar logic.

---

### 📋 Tasks That Can Be Done

Based on the structure of your backend and database schemas, the project manages three distinct user scopes: **Admin**, **Teacher**, and **Student**.

#### Core Functional Tasks (Already Supported)
**Admin Tasks:**
*   **User Management:** Create, read, update, and delete (CRUD) students, teachers, and other administrators.
*   **Academic Structure Management:** Manage semesters, courses, sessions, subjects, and periods.
*   **Timetable Optimization:** Schedule classes assigning specific subjects, teachers, periods, days, and rooms. Archive old timetables.
*   **Leave Management:** Review, approve, or reject student leave requests.
*   **Geofencing & Rules:** Configure geofenced rules for campus boundaries (lat/long mapping) and SMS notification parameters via Twilio.
*   **Exporting Data:** Generate HTML/PDF tabular timetable exports.

**Teacher Tasks:**
*   **Attendance Tracking:** Mark student attendance (supported via manual overrides or scanning QR codes in the mobile app).
*   **Roster Administration:** View assigned subject rosters, add, or remove students from subjects they teach.
*   **Lessons:** Draft and save lesson plans.
*   **Review Daily Statistics:** Check total records, present vs. absent students for the day.
*   **Attendance Corrections:** Rectify mistakes in previous attendance records.

**Student Tasks:**
*   **View Schedule:** Access their individualized daily or weekly timetable based on enrollments.
*   **Leave Requests:** Apply for excused leaves and monitor their approval status.
*   **Mark Attendance:** Utilize the mobile app to scan classroom QR codes (likely validated using geofence data).

#### Potential Future Tasks or Enhancements (To Be Built)
If you are looking for new features or improvements to add to this repository, here are tasks you could do next:
1.  **Bulk Import System:** Adding a feature to upload `.csv` or `.xlsx` files to batch create students or insert large timetables at the beginning of a semester.
2.  **Mobile Push Notifications:** Supplementing the Twilio SMS integration with mobile push notifications using Firebase Cloud Messaging (FCM) via the BeeWare app.
3.  **Advanced Filtering & Exporting:** Allowing Teachers, not just Admins, to export monthly attendance grids for their specific classes to CSV format.
4.  **Password Reset Flow:** Implementing a "forgot password" flow with email/SMS verification, as authentication currently relies on passwords but lacks dynamic resets.
5.  **Dark Mode UI:** Upgrading the web UI to support a toggleable dark mode theme depending on user preference. 
6.  **CI/CD Pipeline:** Assisting in setting up GitHub actions to automatically build the Vite frontend and compile the Beeware Android APK.

Let me know if you would like me to assist with fleshing out any of the current features or begin working on one of the potential future tasks!
