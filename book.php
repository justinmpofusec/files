<?php
session_start();
require 'db.php';

if (!isset($_SESSION["student_db_id"])) {
    header("Location: login.php");
    exit;
}

$course = $_SESSION["course"];
$rooms = [];
$stmt = $conn->prepare("SELECT rooms.id, rooms.room_name FROM rooms INNER JOIN student_room_access ON rooms.id = student_room_access.room_id WHERE student_room_access.course = ? ORDER BY rooms.room_name");
$stmt->bind_param("s", $course);
$stmt->execute();
$result = $stmt->get_result();
while ($row = $result->fetch_assoc()) {
    $rooms[] = $row;
}

$cabinets = $conn->query("SELECT cabinets.id, cabinets.cabinet_name, rooms.room_name, rooms.id AS room_id FROM cabinets INNER JOIN rooms ON cabinets.room_id = rooms.id ORDER BY rooms.room_name, cabinets.cabinet_name");
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Book a Cabinet</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
<header>
    <h1>SHU Lab Booking System</h1>
</header>
<div class="container">
    <h2>Book a Cabinet</h2>
    <p>Rules: 08:30–19:00 only, maximum 2 hours, no booking during fixed teaching blockouts.</p>

    <form method="POST" action="submit_booking.php">
        <label>Room</label>
        <select name="room_id" required>
            <option value="">Select a room</option>
            <?php foreach ($rooms as $room): ?>
                <option value="<?php echo $room['id']; ?>"><?php echo htmlspecialchars($room['room_name']); ?></option>
            <?php endforeach; ?>
        </select>

        <label>Cabinet</label>
        <select name="cabinet_id" required>
            <option value="">Select a cabinet</option>
            <?php while ($cab = $cabinets->fetch_assoc()): ?>
                <option value="<?php echo $cab['id']; ?>">Room <?php echo htmlspecialchars($cab['room_name']); ?> - <?php echo htmlspecialchars($cab['cabinet_name']); ?></option>
            <?php endwhile; ?>
        </select>

        <label>Date</label>
        <input type="date" name="booking_date" required>

        <label>Start time</label>
        <input type="time" name="start_time" required>

        <label>Duration</label>
        <select name="duration" required>
            <option value="1">1 hour</option>
            <option value="2">2 hours</option>
        </select>

        <button type="submit">Check and Continue</button>
    </form>

    <p><a class="btn" href="dashboard.php">Back to Dashboard</a></p>
</div>
</body>
</html>
