# Reading the YANG push telemetry stream

Connect to several devices over RESTCONF, and listen for YANG push updates.
Specific notification endpoint is currently hardcoded, and so are the XPaths of
the data of interest. Stream the result via something that is hopefully
[OpenMetrics](https://tools.ietf.org/html/draft-richih-opsawg-openmetrics-00),
so that the result can be processed via Prometheus or VictoriaMetrics.
