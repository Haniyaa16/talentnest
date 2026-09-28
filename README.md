# TalentNest - Student Talent Marketplace Platform

A Flask + SQLite web application connecting students who offer creative
services (cakes, crafts, jewellery, art, etc.) with clients who want to
book them, with an admin panel to manage the platform.

## Tech Stack
- Backend: Python, Flask
- Database: SQLite (talentnest.db)
- Templates: Jinja2
- Frontend: Bootstrap 5 + Bootstrap Icons

## Setup

```bash
pip install flask
python app.py
```

The app runs at http://127.0.0.1:5000

On first run, `app.py` automatically creates `talentnest.db` with:
- 7 starter categories (Cake Making, Craft, Drawing, Crochet, Handmade
  Candles, Jewellery, Gift Making)
- One admin account:
  - Email: admin@gmail.com
  - Password: admin@123

**Change the admin password / secret key before any real deployment.**

## Roles
- **Student** — register, complete profile, add services, manage bookings
  (pending → accept/reject → accepted → delivered).
- **Client** — register, browse categories/students, book services, track
  booking status, leave a review once a booking is Delivered.
- **Admin** — view platform stats, manage students/clients, manage
  categories (add/edit/delete), view all services and bookings.

## Notable Features
- The student profile category dropdown includes an "Other" option. If
  selected, a textbox appears (JS-controlled) and on submit the app checks
  whether that category already exists; if not, it inserts it into
  `categories` and uses it — so it's immediately usable platform-wide.
- All booking status-changing routes (`/accept_booking`, `/reject_booking`,
  `/delivery_done`) verify the booking belongs to the logged-in student
  before making any change — a student cannot act on another student's
  booking by editing the URL.
- Passwords are hashed with Werkzeug's `generate_password_hash`.
- Uploaded images are restricted to jpg/jpeg/png and saved with
  `secure_filename()` plus a timestamp prefix to avoid collisions.
- 404/403/500 errors render a friendly branded page instead of a raw
  traceback.

## Project Structure

```
TalentNest/
├── app.py
├── talentnest.db
├── templates/
│   └── ... (all pages, extend base.html)
└── static/
    ├── css/style.css
    ├── js/main.js
    └── uploads/
```

## Database Schema

- `users` (id, full_name, email, phone, password_hash, role, created_at)
- `categories` (id, category_name)
- `student_profiles` (id, user_id FK, photo, about, college, branch,
  year_sem, category_id FK, location, starting_price)
- `services` (id, user_id FK, category_id FK, service_name, description,
  price, image, created_at)
- `bookings` (id, service_id FK, student_id FK, client_id FK,
  required_date, college, year, branch, message, status,
  reference_image, created_at)
- `reviews` (id, booking_id FK unique, client_id FK, student_id FK,
  rating, comment, created_at)

Booking `status` is one of: Pending, Accepted, Rejected, Delivered.
