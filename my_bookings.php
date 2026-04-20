<?php
session_start();
require 'db.php';

if (!isset($_SESSION["student_db_id"])) {
    header("Location: login.php");
    exit;
}

$studentDbId = $_SESSION["student_db_id"];
$stmt = $conn->prepare("SELECT bookings.booking_date, bookings.start_time, bookings.end_time, rooms.room_name, cabinets.cabinet_name FROM bookings INNER JOIN rooms ON bookings.room_id = rooms.id INNER JOIN cabinets ON bookings.cabinet_id = cabinets.id WHERE bookings.student_id = ? ORDER BY bookings.booking_date, bookings.start_time");
$stmt->bind_param("i", $studentDbId);
$stmt->execute();
$result = $stmt->get_result();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>My Bookings</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
<header>
    <h1>SHU Lab Booking System</h1>
</header>
<div class="container">
    <h2>My Bookings</h2>
    <?php if ($result->num_rows > 0): ?>
        <table>
            <tr>
                <th>Date</th>
                <th>Room</th>
                <th>Cabinet</th>
                <th>Start</th>
                <th>End</th>
            </tr>
            <?php while ($row = $result->fetch_assoc()): ?>
                <tr>
                    <td><?php echo htmlspecialchars($row['booking_date']); ?></td>
                    <td><?php echo htmlspecialchars($row['room_name']); ?></td>
                    <td><?php echo htmlspecialchars($row['cabinet_name']); ?></td>
                    <td><?php echo htmlspecialchars(substr($row['start_time'], 0, 5)); ?></td>
                    <td><?php echo htmlspecialchars(substr($row['end_time'], 0, 5)); ?></td>
                </tr>
            <?php endwhile; ?>
        </table>
    <?php else: ?>
        <p>No bookings found.</p>
    <?php endif; ?>
    <p><a class="btn" href="dashboard.php">Back to Dashboard</a></p>
</div>
</body>
</html>
