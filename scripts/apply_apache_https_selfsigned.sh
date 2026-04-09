#!/bin/bash
# اجرا روی سرور (ریشه): گواهی self-signed با SAN + VirtualHostهای 443 + هدایت HTTP→HTTPS
# برای قفل سبز مرورگر بعداً: certbot یا گواهی دستی جایگزین فایل‌های crt/key شود.
set -euo pipefail

OPENSSL_CNF=/tmp/anistito-openssl.cnf
cat >"$OPENSSL_CNF" <<'EOF'
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = lms.psychoanalysis.ir

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = lms.psychoanalysis.ir
DNS.2 = ims.psychoanalysis.ir
EOF

openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout /etc/ssl/private/anistito-lms-ims.key \
  -out /etc/ssl/certs/anistito-lms-ims.crt \
  -config "$OPENSSL_CNF" -extensions v3_req

chown root:ssl-cert /etc/ssl/private/anistito-lms-ims.key
chmod 640 /etc/ssl/private/anistito-lms-ims.key

install -d -m0755 /var/www/html/.well-known/acme-challenge

cat >/etc/apache2/sites-available/lms-psychoanalysis.conf <<'HTTP_LMS'
<VirtualHost *:80>
    ServerName lms.psychoanalysis.ir
    ServerAdmin webmaster@psychoanalysis.ir

    RewriteEngine on
    RewriteCond %{REQUEST_URI} !^/\.well-known/acme-challenge/
    RewriteCond %{HTTPS} !=on
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]

    Alias /.well-known/acme-challenge/ /var/www/html/.well-known/acme-challenge/
    <Directory /var/www/html/.well-known/acme-challenge>
        Require all granted
    </Directory>

    RedirectMatch ^/$ /anistito/

    ProxyPreserveHost On
    ProxyPass /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPass /anistito/ http://127.0.0.1:3000/
    ProxyPassReverse /anistito/ http://127.0.0.1:3000/

    ErrorLog ${APACHE_LOG_DIR}/lms-psycho-error.log
    CustomLog ${APACHE_LOG_DIR}/lms-psycho-access.log combined
</VirtualHost>
HTTP_LMS

cat >/etc/apache2/sites-available/ims-psychoanalysis.conf <<'HTTP_IMS'
<VirtualHost *:80>
    ServerName ims.psychoanalysis.ir
    ServerAdmin webmaster@psychoanalysis.ir

    RewriteEngine on
    RewriteCond %{REQUEST_URI} !^/\.well-known/acme-challenge/
    RewriteCond %{HTTPS} !=on
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]

    Alias /.well-known/acme-challenge/ /var/www/html/.well-known/acme-challenge/
    <Directory /var/www/html/.well-known/acme-challenge>
        Require all granted
    </Directory>

    RedirectMatch ^/$ /anistito/

    ProxyPreserveHost On
    ProxyPass /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPass /anistito/ http://127.0.0.1:3000/
    ProxyPassReverse /anistito/ http://127.0.0.1:3000/

    ErrorLog ${APACHE_LOG_DIR}/ims-psycho-error.log
    CustomLog ${APACHE_LOG_DIR}/ims-psycho-access.log combined
</VirtualHost>
HTTP_IMS

cat >/etc/apache2/sites-available/psychosites-ssl.conf <<'APACHE_EOF'
<VirtualHost *:443>
    ServerName lms.psychoanalysis.ir
    ServerAdmin webmaster@psychoanalysis.ir

    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/anistito-lms-ims.crt
    SSLCertificateKeyFile /etc/ssl/private/anistito-lms-ims.key

    RedirectMatch ^/$ /anistito/

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    ProxyPass /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPass /anistito/ http://127.0.0.1:3000/
    ProxyPassReverse /anistito/ http://127.0.0.1:3000/

    ErrorLog ${APACHE_LOG_DIR}/lms-psycho-ssl-error.log
    CustomLog ${APACHE_LOG_DIR}/lms-psycho-ssl-access.log combined
</VirtualHost>

<VirtualHost *:443>
    ServerName ims.psychoanalysis.ir
    ServerAdmin webmaster@psychoanalysis.ir

    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/anistito-lms-ims.crt
    SSLCertificateKeyFile /etc/ssl/private/anistito-lms-ims.key

    RedirectMatch ^/$ /anistito/

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    ProxyPass /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPass /anistito/ http://127.0.0.1:3000/
    ProxyPassReverse /anistito/ http://127.0.0.1:3000/

    ErrorLog ${APACHE_LOG_DIR}/ims-psycho-ssl-error.log
    CustomLog ${APACHE_LOG_DIR}/ims-psycho-ssl-access.log combined
</VirtualHost>
APACHE_EOF

a2enmod ssl rewrite headers proxy proxy_http
a2ensite psychosites-ssl
a2dissite default-ssl 2>/dev/null || true

apache2ctl configtest
systemctl reload apache2

echo "OK: https://lms.psychoanalysis.ir/anistito/ (گواهی موقت؛ مرورگر هشدار می‌دهد تا LE نصب شود)"
