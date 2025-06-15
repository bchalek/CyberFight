#!/bin/bash
dpkg -i splunkforwarder-9.4.3-237ebbd22314-linux-amd64.deb
mkdir /opt/logs
chmod 777 /opt/logs
cp ./splunkclouduf.spl /tmp/
/opt/splunkforwarder/bin/splunk install app /tmp/splunkclouduf.spl

cat << EOF >/opt/splunkforwarder/etc/system/local/input.conf
[monitor:/opt/logs/*]
disabled=false
followTail=0
initCrcLenght=65535
index=mods
source=mods
EOF
/opt/splunkforwarder/bin/splunkd
