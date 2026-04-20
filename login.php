<?php
session_start();
require 'db.php';

$error = "";

if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $student_id = trim($_POST["student_id"] ?? "");
    $password = trim($_POST["password"] ?? "");

    $stmt = $conn->prepare("SELECT id, student_id, full_name, email, password, course FROM students WHERE student_id = ?");
    $stmt->bind_param("s", $student_id);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($row = $result->fetch_assoc()) {
        if ($password === $row["password"]) {
            $_SESSION["student_db_id"] = $row["id"];
            $_SESSION["student_id"] = $row["student_id"];
            $_SESSION["full_name"] = $row["full_name"];
            $_SESSION["email"] = $row["email"];
            $_SESSION["course"] = $row["course"];
            header("Location: dashboard.php");
            exit;
        } else {
            $error = "Invalid password.";
        }
    } else {
        $error = "Student ID not found.";
    }
}
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SHU Lab Booking Login</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
<header>
    <h1>SHU Lab Booking System</h1>
</header>
<div class="container">
    <h2>Student Login</h2>
    <p>Login using your student ID and password.</p>

    <?php if ($error): ?>
        <div class="alert alert-error"><?php echo htmlspecialchars($error); ?></div>
    <?php endif; ?>

    <form method="POST">
        <label>Student ID</label>
        <input type="text" name="student_id" required>

        <label>Password</label>
        <input type="password" name="password" required>

        <button type="submit">Login</button>
    </form>

    <p><strong>Test login:</strong> 12345 / password123</p>
</div>
</body>
</html>
