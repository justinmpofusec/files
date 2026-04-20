<?php
session_start();
require 'db.php';

if (!isset($_SESSION["student_db_id"])) {
    header("Location: login.php");
    exit;
}

$studentDbId = $_SESSION["student_db_id"];
$course = $_SESSION["course"];

$rooms = [];
$stmt = $conn->prepare("SELECT rooms.id, rooms.room_name FROM rooms INNER JOIN student_room_access ON rooms.id = student_room_access.room_id WHERE student_room_access.course = ? ORDER BY rooms.room_name");
$stmt->bind_param("s", $course);
$stmt->execute();
$result = $stmt->get_result();
while ($row = $result->fetch_assoc()) {
    $rooms[] = $row;
}

$timetable = [];
$stmt2 = $conn->prepare("SELECT module_name, day, start_time, end_time FROM timetable WHERE student_id = ? ORDER BY day, start_time");
$stmt2->bind_param("i", $studentDbId);
$stmt2->execute();
$result2 = $stmt2->get_result();
while ($row = $result2->fetch_assoc()) {
    $timetable[] = $row;
}
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Dashboard - SHU Lab Booking</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
<header>
    <h1>SHU Lab Booking System</h1>
</header>
<div class="container">
    <h2>Welcome, <?php echo htmlspecialchars($_SESSION["full_name"]); ?></h2>
    <p><strong>Student ID:</strong> <?php echo htmlspecialchars($_SESSION["student_id"]); ?></p>
    <p><strong>Course:</strong> <?php echo htmlspecialchars($_SESSION["course"]); ?></p>

    <div class="nav-links">
        <a class="btn" href="book.php">Book a Cabinet</a>
        <a class="btn" href="my_bookings.php">View My Bookings</a>
        <a class="btn" href="logout.php">Logout</a>
    </div>

    <h3>Rooms available to you</h3>
    <ul>
        <?php foreach ($rooms as $room): ?>
            <li>Room <?php echo htmlspecialchars($room["room_name"]); ?></li>
        <?php endforeach; ?>
    </ul>

    <h3>Your timetable</h3>
    <?php if (count($timetable) > 0): ?>
        <table>
            <tr>
                <th>Module</th>
                <th>Day</th>
                <th>Start</th>
                <th>End</th>
            </tr>
            <?php foreach ($timetable as $item): ?>
                <tr>
                    <td><?php echo htmlspecialchars($item["module_name"]); ?></td>
                    <td><?php echo htmlspecialchars($item["day"]); ?></td>
                    <td><?php echo htmlspecialchars(substr($item["start_time"], 0, 5)); ?></td>
                    <td><?php echo htmlspecialchars(substr($item["end_time"], 0, 5)); ?></td>
                </tr>
            <?php endforeach; ?>
        </table>
    <?php else: ?>
        <p>No timetable events found.</p>
    <?php endif; ?>
</div>
</body>
</html>
