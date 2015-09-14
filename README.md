# Carbon Black - Wildfire Connector

## Installation Quickstart

As root on your Carbon Black or other RPM based 64-bit Linux distribution server:
```
cd /etc/yum.repos.d
curl -O https://opensource.carbonblack.com/release/x86_64/CbOpenSource.repo
yum install python-cb-wildfire-connector
```

Once the software is installed via YUM, copy the `/etc/cb/integrations/wildfire/connector.conf.example` file to
`/etc/cb/integrations/wildfire/connector.conf`. Edit this file and place your Carbon Black API key into the
`carbonblack_server_token` variable and your Carbon Black server's base URL into the `carbonblack_server_url` variable.

Any errors will be logged into `/var/log/cb/integrations/wildfire/wildfire.log`.

## Troubleshooting

If you suspect a problem, please first look at the Wildfire connector logs found here:
`/var/log/cb/integrations/wildfire/wildfire.log`
(There might be multiple files as the logger "rolls over" when the log file hits a certain size).

If you want to re-run the analysis across your binaries:

1. Stop the service: `service cb-wildfire-connector stop`
2. Remove the database file: `rm /usr/share/cb/integrations/wildfire/db/sqlite.db`
3. Remove the feed from your Cb server's Threat Intelligence page
4. Restart the service: `service cb-wildfire-connector start`

## Contacting Bit9 Developer Relations Support

Web: https://community.bit9.com/groups/developer-relations
E-mail: dev-support@bit9.com

### Reporting Problems

When you contact Bit9 Developer Relations Technical Support with an issue, please provide the following:

* Your name, company name, telephone number, and e-mail address
* Product name/version, CB Server version, CB Sensor version
* Hardware configuration of the Carbon Black Server or computer (processor, memory, and RAM)
* For documentation issues, specify the version of the manual you are using.
* Action causing the problem, error message returned, and event log output (as appropriate)
* Problem severity
