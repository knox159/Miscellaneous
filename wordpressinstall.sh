#!/bin/bash

echo "Starting WordPress With Nginx..."

#Prompt for DB credentials 
read -p "Enter MySQL database name [wordpress]: " DB_NAME
DB_NAME${DB_NAME:-wordpress}

read -p "Enter MySQL user [wpuser]: " DB_USER
DB_USER${DB_USER:-wpuser}

read -s -p "Enter MySQL password: " DB_PASS
echo ""
read -s -p "Confirm MySQL password: " DB_PASS_CONFIRM
echo ""

if [ "$DB_PASS" ! "$DB_PASS_CONFIRM" ]; then
  echo "❌ Passwords do not match. Aborting."
  exit 1
fi

#Detect PHP version dynamically 
PHP_VERSION$(apt-cache search php | grep -Eo 'php[0-9]+\.[0-9]+' | sort -Vr | uniq | head -n 1 | grep -Eo '[0-9]+\.[0-9]+')
PHP_SOCKET"php${PHP_VERSION}-fpm.sock"
WP_DIR"/var/www/html/wordpress"

#Install Packages 
apt update && apt upgrade -y
apt install nginx mysql-server php${PHP_VERSION}-fpm php${PHP_VERSION}-{mysql,curl,gd,xml,mbstring,zip,soap,intl} unzip curl -y

#Secure MySQL 
echo "Securing MySQL..."
mysql_secure_installation <<EOF

y
$DB_PASS
$DB_PASS
y
y
y
y
EOF

#Create DB and User
echo "Creating MySQL database and user..."
mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOF

#WordPress Setup
cd /tmp
curl -O https://wordpress.org/latest.tar.gz
tar -xzf latest.tar.gz
mv wordpress $WP_DIR

chown -R www-data:www-data $WP_DIR
find $WP_DIR -type d -exec chmod 755 {} \;
find $WP_DIR -type f -exec chmod 644 {} \;

cp $WP_DIR/wp-config-sample.php $WP_DIR/wp-config.php
sed -i "s/database_name_here/${DB_NAME}/" $WP_DIR/wp-config.php
sed -i "s/username_here/${DB_USER}/" $WP_DIR/wp-config.php
sed -i "s/password_here/${DB_PASS}/" $WP_DIR/wp-config.php

#NGINX Config 
cat > /etc/nginx/sites-available/wordpress <<EOF
server {
    listen 80;
    server_name _;

    root ${WP_DIR};
    index index.php index.html;

    location / {
        try_files \$uri \$uri/ /index.php?\$args;
    }

    location ~ \.php\$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/${PHP_SOCKET};
    }

    location ~ /\.ht {
        deny all;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/wordpress /etc/nginx/sites-enabled/wordpress

#Final Reload 
nginx -t && systemctl reload nginx
systemctl enable nginx
systemctl enable mysql
systemctl restart php${PHP_VERSION}-fpm

echo ""
echo "WordPress is installed!"
echo "👉 Visit: http://<your-server-ip>/"