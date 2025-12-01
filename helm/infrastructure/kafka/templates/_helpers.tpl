{{/*
Expand the name of the chart.
*/}}
{{- define "kafka.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "kafka.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "kafka.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "kafka.labels" -}}
helm.sh/chart: {{ include "kafka.chart" . }}
{{ include "kafka.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "kafka.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kafka.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Kafka cluster name
*/}}
{{- define "kafka.clusterName" -}}
{{- .Values.cluster.name }}
{{- end }}

{{/*
Kafka bootstrap servers (internal)
*/}}
{{- define "kafka.bootstrapServers" -}}
{{- printf "%s-kafka-bootstrap.%s.svc.cluster.local:%d" .Values.cluster.name .Values.cluster.namespace (int .Values.kafka.listeners.plain.port) }}
{{- end }}

{{/*
Kafka bootstrap servers (external via NodePort)
*/}}
{{- define "kafka.bootstrapServersExternal" -}}
{{- if .Values.kafka.listeners.external.enabled }}
{{- printf "%s:%d" .Values.kafka.listeners.external.advertisedHost (int .Values.kafka.listeners.external.nodePort) }}
{{- else }}
{{- include "kafka.bootstrapServers" . }}
{{- end }}
{{- end }}

{{/*
Namespace
*/}}
{{- define "kafka.namespace" -}}
{{- .Values.cluster.namespace | default .Values.global.namespace | default "kafka" }}
{{- end }}
