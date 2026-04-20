USE shu_cabinet_booking;

INSERT INTO rooms (room_name) VALUES
('9301'), ('9302'), ('9303'), ('9304');

INSERT INTO cabinets (room_id, cabinet_name) VALUES
(1,'Cabinet 1'), (1,'Cabinet 2'), (1,'Cabinet 3'), (1,'Cabinet 4'), (1,'Cabinet 5'),
(2,'Cabinet 1'), (2,'Cabinet 2'), (2,'Cabinet 3'), (2,'Cabinet 4'), (2,'Cabinet 5'),
(3,'Cabinet 1'), (3,'Cabinet 2'), (3,'Cabinet 3'), (3,'Cabinet 4'), (3,'Cabinet 5'),
(4,'Cabinet 1'), (4,'Cabinet 2'), (4,'Cabinet 3'), (4,'Cabinet 4'), (4,'Cabinet 5');

INSERT INTO students (student_id, full_name, email, password, course) VALUES
('12345', 'Jay Student', 'jay@example.com', 'password123', 'Cyber Security');

INSERT INTO timetable (student_id, module_name, day, start_time, end_time) VALUES
(1, 'Networking', 'Tuesday', '15:00:00', '17:00:00');

INSERT INTO student_room_access (course, room_id) VALUES
('Cyber Security', 1),
('Cyber Security', 2),
('Cyber Security', 3),
('Cyber Security', 4),
('Computer Science', 1),
('Computer Science', 2),
('Computer Science', 3),
('Computer Science', 4);

INSERT INTO room_blockouts (room_id, day_name, start_time, end_time, reason) VALUES
(1, 'Monday', '12:00:00', '14:00:00', 'Lesson'),
(1, 'Wednesday', '12:00:00', '14:00:00', 'Lesson'),
(1, 'Thursday', '12:00:00', '14:00:00', 'Lesson'),
(2, 'Monday', '12:00:00', '14:00:00', 'Lesson'),
(2, 'Wednesday', '12:00:00', '14:00:00', 'Lesson'),
(2, 'Thursday', '12:00:00', '14:00:00', 'Lesson'),
(3, 'Monday', '12:00:00', '14:00:00', 'Lesson'),
(3, 'Wednesday', '12:00:00', '14:00:00', 'Lesson'),
(3, 'Thursday', '12:00:00', '14:00:00', 'Lesson'),
(4, 'Monday', '12:00:00', '14:00:00', 'Lesson'),
(4, 'Wednesday', '12:00:00', '14:00:00', 'Lesson'),
(4, 'Thursday', '12:00:00', '14:00:00', 'Lesson');
