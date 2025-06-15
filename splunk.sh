#!/bin/bash
echo "################Instalacja git, curl####"
apt-get update
apt-get install git curl -y
echo "##############Instalacja#################"
dpkg -i splunkforwarder-9.4.3-237ebbd22314-linux-amd64.deb
echo "######Utworzenie katalogu /opt/logs######"
mkdir /opt/logs
echo "#####Nadanie uprawnien###################"
chmod 777 /opt/logs
echo "############Przekopiowanie spl do tmp####"
cp ./splunkclouduf.spl /tmp/
echo "#######Start splunk######################"
/opt/splunkforwarder/bin/splunk start
echo "#######Utworzenie local.conf#############"
cat << EOF >/opt/splunkforwarder/etc/system/local/input.conf
[monitor:/opt/logs/*]
disabled=false
followTail=0
initCrcLenght=65535
index=mods
source=mods
EOF

echo "###########Instalacja spki###############"
/opt/splunkforwarder/bin/splunk install app /tmp/splunkclouduf.spl
echo " ######Restart splunk ###################"
/opt/splunkforwarder/bin/splunk restart
/opt/splunkforwarder/bin/splunk list forward-server
