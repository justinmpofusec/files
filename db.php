<?php
$host = "localhost";
$dbname = "shu_cabinet_booking";
$username = "root";
$password = "CHANGE_ME";

$conn = new mysqli($host, $username, $password, $dbname);

if ($conn->connect_error) {
    die("Database connection failed: " . $conn->connect_error);
}

$conn->set_charset("utf8mb4");
?>
