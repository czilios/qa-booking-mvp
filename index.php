<?php

declare(strict_types=1);

echo '<h1>Wrzosowo 159 Booking System</h1>';

echo '<h2>Environment check</h2>';

echo '<ul>';

echo '<li>PHP version: ' . PHP_VERSION . '</li>';

echo '<li>PDO: ' . (extension_loaded('pdo') ? 'OK' : 'MISSING') . '</li>';

echo '<li>PDO MySQL: ' . (extension_loaded('pdo_mysql') ? 'OK' : 'MISSING') . '</li>';

echo '<li>cURL: ' . (extension_loaded('curl') ? 'OK' : 'MISSING') . '</li>';

echo '<li>JSON: ' . (extension_loaded('json') ? 'OK' : 'MISSING') . '</li>';

echo '<li>mbstring: ' . (extension_loaded('mbstring') ? 'OK' : 'MISSING') . '</li>';

echo '<li>Sessions: ' . (extension_loaded('session') ? 'OK' : 'MISSING') . '</li>';

echo '</ul>';

echo '<hr>';

echo '<p><strong>Environment test completed.</strong></p>';