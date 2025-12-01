{{/*
Expand the name of the chart.
*/}}
{{- define "minio.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "minio.fullname" -}}
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
{{- define "minio.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "minio.labels" -}}
helm.sh/chart: {{ include "minio.chart" . }}
{{ include "minio.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "minio.selectorLabels" -}}
app.kubernetes.io/name: {{ include "minio.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
MinIO tenant name
*/}}
{{- define "minio.tenantName" -}}
{{- .Values.tenant.name }}
{{- end }}

{{/*
MinIO API endpoint (internal)
*/}}
{{- define "minio.apiEndpoint" -}}
{{- printf "http://minio.%s.svc.cluster.local" .Values.tenant.namespace }}
{{- end }}

{{/*
MinIO API endpoint (external)
*/}}
{{- define "minio.apiEndpointExternal" -}}
{{- .Values.minio.endpoint }}
{{- end }}

{{/*
MinIO Console endpoint (internal)
*/}}
{{- define "minio.consoleEndpoint" -}}
{{- printf "http://%s-console.%s.svc.cluster.local:9090" .Values.tenant.name .Values.tenant.namespace }}
{{- end }}

{{/*
Namespace
*/}}
{{- define "minio.namespace" -}}
{{- .Values.tenant.namespace | default .Values.global.namespace | default "minio-tenant" }}
{{- end }}

{{/*
Storage class name
*/}}
{{- define "minio.storageClassName" -}}
{{- .Values.minio.storage.storageClassName | default .Values.storageClass.name }}
{{- end }}
