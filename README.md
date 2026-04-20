# SHU Cabinet Booking Starter

This is a starter PHP/MySQL project for a LAMP-based lab room and cabinet booking system.

## Included files
- `db.php` - database connection
- `index.php` - redirects to login
- `login.php` - simple student login
- `dashboard.php` - student dashboard
- `book.php` - booking form
- `submit_booking.php` - booking validation and insert logic
- `my_bookings.php` - student booking list
- `logout.php` - logout
- `style.css` - basic styling
- `schema.sql` - database schema
- `sample_data.sql` - sample data

## Before use
1. Copy the project folder into your web root, for example `/var/www/html/shu-booking`.
2. Create the database and tables using `schema.sql`.
3. Insert sample data using `sample_data.sql`.
4. Edit `db.php` and set your real MySQL password.
5. Restart Apache.

## Open in browser
`http://YOUR-IP/shu-booking/login.php`

## Sample login
- Student ID: `12345`
- Password: `password123`

## Notes
- This is a starter build intended for coursework and further manual improvement.
- Passwords are currently plain text for simplicity in the prototype. You can upgrade later to `password_hash()` and `password_verify()`.
