<?php
session_start();
require 'db.php';

if (!isset($_SESSION["student_db_id"])) {
    header("Location: login.php");
    exit;
}

function showMessage($message, $type = "error") {
    $class = $type === "success" ? "alert-success" : ($type === "warning" ? "alert-warning" : "alert-error");
    echo '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Booking Result</title><link rel="stylesheet" href="style.css"></head><body><header><h1>SHU Lab Booking System</h1></header><div class="container"><div class="alert ' . $class . '">' . htmlspecialchars($message) . '</div><p><a class="btn" href="book.php">Back to Booking</a></p><p><a class="btn" href="dashboard.php">Dashboard</a></p></div></body></html>';
    exit;
}

$studentDbId = $_SESSION["student_db_id"];
$course = $_SESSION["course"];

if ($_SERVER["REQUEST_METHOD"] !== "POST") {
    showMessage("Invalid request.");
}

$roomId = (int)($_POST["room_id"] ?? 0);
$cabinetId = (int)($_POST["cabinet_id"] ?? 0);
$bookingDate = $_POST["booking_date"] ?? "";
$startTime = $_POST["start_time"] ?? "";
$duration = (int)($_POST["duration"] ?? 0);
$confirmedWarning = isset($_POST["confirmed_warning"]) ? (int)$_POST["confirmed_warning"] : 0;

if ($roomId <= 0 || $cabinetId <= 0 || !$bookingDate || !$startTime) {
    showMessage("All fields are required.");
}

if (!in_array($duration, [1, 2], true)) {
    showMessage("Bookings can only be 1 or 2 hours.");
}

$startDateTime = strtotime($bookingDate . ' ' . $startTime);
if ($startDateTime === false) {
    showMessage("Invalid date or time.");
}

$endDateTime = strtotime("+{$duration} hour", $startDateTime);
$endTime = date("H:i:s", $endDateTime);
$startTimeFull = date("H:i:s", $startDateTime);
$dayName = date("l", strtotime($bookingDate));

if ($startTimeFull < "08:30:00" || $endTime > "19:00:00") {
    showMessage("Booking must be within opening hours: 08:30 to 19:00.");
}

$stmt = $conn->prepare("SELECT COUNT(*) AS cnt FROM student_room_access WHERE course = ? AND room_id = ?");
$stmt->bind_param("si", $course, $roomId);
$stmt->execute();
$res = $stmt->get_result()->fetch_assoc();
if ((int)$res["cnt"] === 0) {
    showMessage("You are not allowed to book this room.");
}

$stmt = $conn->prepare("SELECT COUNT(*) AS cnt FROM cabinets WHERE id = ? AND room_id = ?");
$stmt->bind_param("ii", $cabinetId, $roomId);
$stmt->execute();
$res = $stmt->get_result()->fetch_assoc();
if ((int)$res["cnt"] === 0) {
    showMessage("Selected cabinet does not belong to the selected room.");
}

$stmt = $conn->prepare("SELECT reason, start_time, end_time FROM room_blockouts WHERE room_id = ? AND day_name = ? AND (? < end_time AND ? > start_time)");
$stmt->bind_param("isss", $roomId, $dayName, $startTimeFull, $endTime);
$stmt->execute();
$blockResult = $stmt->get_result();
if ($blockResult->num_rows > 0) {
    $block = $blockResult->fetch_assoc();
    showMessage("This room is unavailable due to {$block['reason']} between " . substr($block['start_time'], 0, 5) . " and " . substr($block['end_time'], 0, 5) . ".");
}

$stmt = $conn->prepare("SELECT COUNT(*) AS cnt FROM bookings WHERE cabinet_id = ? AND booking_date = ? AND (? < end_time AND ? > start_time)");
$stmt->bind_param("isss", $cabinetId, $bookingDate, $startTimeFull, $endTime);
$stmt->execute();
$res = $stmt->get_result()->fetch_assoc();
if ((int)$res["cnt"] > 0) {
    showMessage("This cabinet is already booked for that time.");
}

$stmt = $conn->prepare("SELECT module_name, day, start_time, end_time FROM timetable WHERE student_id = ? AND day = ? AND ((? < end_time AND ? > start_time) OR ? = start_time OR ? = end_time)");
$stmt->bind_param("isssss", $studentDbId, $dayName, $startTimeFull, $endTime, $endTime, $startTimeFull);
$stmt->execute();
$timeConflict = $stmt->get_result();
if ($timeConflict->num_rows > 0 && $confirmedWarning !== 1) {
    $event = $timeConflict->fetch_assoc();
    ?>
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Timetable Warning</title>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
    <header><h1>SHU Lab Booking System</h1></header>
    <div class="container">
        <div class="alert alert-warning">
            You have a timetable event: <strong><?php echo htmlspecialchars($event["module_name"]); ?></strong>
            on <strong><?php echo htmlspecialchars($event["day"]); ?></strong>
            from <strong><?php echo htmlspecialchars(substr($event["start_time"], 0, 5)); ?></strong>
            to <strong><?php echo htmlspecialchars(substr($event["end_time"], 0, 5)); ?></strong>.
            Do you still want to continue with this booking?
        </div>
        <form method="POST" action="submit_booking.php">
            <input type="hidden" name="room_id" value="<?php echo $roomId; ?>">
            <input type="hidden" name="cabinet_id" value="<?php echo $cabinetId; ?>">
            <input type="hidden" name="booking_date" value="<?php echo htmlspecialchars($bookingDate); ?>">
            <input type="hidden" name="start_time" value="<?php echo htmlspecialchars(substr($startTimeFull, 0, 5)); ?>">
            <input type="hidden" name="duration" value="<?php echo $duration; ?>">
            <input type="hidden" name="confirmed_warning" value="1">
            <button type="submit">Yes, continue anyway</button>
        </form>
        <p><a class="btn" href="book.php">No, go back</a></p>
    </div>
    </body>
    </html>
    <?php
    exit;
}

$stmt = $conn->prepare("INSERT INTO bookings (student_id, room_id, cabinet_id, booking_date, start_time, end_time, duration, confirmed_warning) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
$stmt->bind_param("iiisssii", $studentDbId, $roomId, $cabinetId, $bookingDate, $startTimeFull, $endTime, $duration, $confirmedWarning);
if ($stmt->execute()) {
    showMessage("Booking created successfully.", "success");
} else {
    showMessage("Booking failed. Please try again.");
}
?>
