#!/bin/bash
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
#
# https://github.com/github/gitignore/blob/main/Python.gitignore
#
# Byte-compiled / optimized / DLL files


printf "Starting Pipeline" | jq -MRcs \
    --arg logger "$0" \
    --arg dvc_data_path "${DVC_DATA_PATH}" \
    --arg dvc_path "${DVC_PATH}" \
    --arg dvc_file "${DVC_FILE}" \
    --arg wurzel_pipeline "${WURZEL_PIPELINE}" \
    '{message: ., level: "INFO", logger: $logger, args: {dvc_data_path: $dvc_data_path, dvc_path: $dvc_path, dvc_file: $dvc_file, wurzel_pipeline: $wurzel_pipeline}}'

jq_run () { # Usage: jq_run cmd [args...] [noexit]
    local noexit=false
    local -a cmd=("$@")
    # Strip trailing 'noexit' sentinel if present
    if [[ "${cmd[-1]}" == "noexit" ]]; then
        noexit=true
        cmd=("${cmd[@]:0:${#cmd[@]}-1}")
    fi
    local cmd_name="${cmd[0]}"
    local cmd_args="${cmd[*]:1}"
    local result rc
    if result=$("${cmd[@]}" 2>&1); then
        if [[ -n "$result" ]]; then
            printf "%s" "$result" | jq -MRcs \
                --arg logger "$0/${cmd_name}" \
                --arg args "${cmd_args}" \
                '{message: ., level: "INFO", logger: $logger, args: $args}'
        fi
    else
        rc=$?
        if $noexit; then
            printf "%s" "$result" | jq -MRcs \
                --arg logger "$0/${cmd_name}" \
                --arg args "${cmd_args}" \
                '{message: ., level: "WARNING", logger: $logger, args: $args}'
            return $rc
        else
            printf "%s" "$result" | jq -MRcs \
                --arg logger "$0/${cmd_name}" \
                --arg args "${cmd_args}" \
                '{message: ., level: "ERROR", logger: $logger, args: $args}'
            exit $rc
        fi
    fi
}
jq_run git init
jq_run git config --global --add safe.directory /usr/app
jq_run git config --global user.email "${GIT_MAIL:-wurzel@example.com}"
jq_run git config --global user.name "${GIT_USER:-wurzel}"
if [ -d ".dvc" ]; then
    echo "DVC already initialized" | jq -MRcs \
        --arg logger "$0/dvc" \
        '{message: ., level: "INFO", logger: $logger, args: "init"}'
else
    jq_run dvc init
fi
wurzel generate "${WURZEL_PIPELINE}" > "${DVC_FILE}" || exit 1
mkdir -p "${DVC_DATA_PATH}"
dvc repro -q || exit 1

jq_run git status noexit
jq_run dvc status noexit
jq_run git commit -m "savepoint $(date +%F_%T)" noexit
jq_run dvc gc -n "${DVC_CACHE_HISTORY_NUMBER:-5}" -f --rev HEAD noexit
EXT=$?
if [ -n "$PROMETHEUS__GATEWAY" ]; then
   sleep 15
   jq_run curl -X DELETE --connect-timeout 5 "${PROMETHEUS__GATEWAY}/metrics/job/${QDRANTSTEP__COLLECTION}" noexit
fi
exit $EXT
